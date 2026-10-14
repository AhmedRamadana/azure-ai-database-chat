"""
db_context.py

كل Streamlit Session ليها DBContext خاص بيها فيه:

    engine        -> الاتصال بالداتابيز بتاعة الـ Session دي بس
    schema        -> الـ Schema اللي اتقرت وقت الاتصال
    value_cache   -> كاش الـ Value Resolver (مربوط بالـ Session)
    ...

مفيش أي Global مشترك بين المستخدمين.

الأنواع المدعومة: PostgreSQL و MySQL/MariaDB و SQLite (انظر dialects.py).
كل Session بتختار النوع بتاعها، والاتصال بيمر على 5 فحوصات:

    1. مدخلات الفورم
    2. الاتصال (connect_timeout = 5 ثواني)
    3. نوع السيرفر (Dialect.verify_server)
    4. لازم يكون فيه جدول واحد على الأقل
    5. أي استثناء يتمسك (مفيش Traceback ولا نص Exception للمستخدم)

الرسالة اللي بتظهر للمستخدم في حالة فشل الاتصال ثابتة، لأن نص الـ
Exception ممكن يحتوي على Host أو User.
"""

import ipaddress
import logging
import os
import re
import socket
import tempfile

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

from database import (
    DEFAULT_STATEMENT_TIMEOUT_MS,
    execute_query,
    is_valid_pg_schema_name
)

from dialects import get_dialect

from schema import get_database_schema

from authorization.policy_builder import (
    build_effective_policy,
    summarize_policy
)


logger = logging.getLogger(__name__)


# ============================================================
# Configuration
# ============================================================

GENERIC_CONNECTION_ERROR = (
    "Could not connect. "
    "Please check the connection details and try again."
)

# أقصى حجم لملف SQLite المرفوع (بالـ MB). اتغيّره بـ MAX_SQLITE_UPLOAD_MB.
DEFAULT_MAX_SQLITE_UPLOAD_MB = 100

_SQLITE_HEADER = b"SQLite format 3\x00"

NO_TABLES_ERROR = (
    "Connected, but no tables were found."
)

CONNECT_TIMEOUT_SECONDS = 5

DEMO_CONNECT_TIMEOUT_SECONDS = 10

SSL_MODES = (
    "disable",
    "allow",
    "prefer",
    "require",
    "verify-ca",
    "verify-full"
)

_HOST_RE = re.compile(r"^[A-Za-z0-9._:\-]+$")


# ============================================================
# Errors
# ============================================================

class DBConnectionError(Exception):
    """
    .message  -> نص آمن يتعرض للمستخدم (ثابت، من غير Host أو User)
    .kind     -> "form" | "connect" | "empty"
    """

    def __init__(self, message: str, kind: str = "connect"):

        super().__init__(message)

        self.message = message
        self.kind = kind


# ============================================================
# 1) Form validation
# ============================================================

def validate_connection_form(
    host,
    port,
    database,
    user,
    sslmode=None,
    pg_schema="public",
    dialect=None
):
    """
    بترجّع dict نضيف، أو بترفع DBConnectionError(kind="form").
    الباسورد مش بيتفحص هنا (ممكن يحتوي على أي حرف).

    dialect: مفتاح النوع ("postgresql" | "mysql") أو None (PostgreSQL).
    """

    dialect = (
        dialect
        if hasattr(dialect, "key")
        else get_dialect(dialect)
    )

    if dialect.file_based:

        raise DBConnectionError(
            f"{dialect.label} connects through a file upload.",
            "form"
        )

    host = (host or "").strip()
    database = (database or "").strip()
    user = (user or "").strip()
    pg_schema = (pg_schema or "").strip() or "public"
    sslmode = (
        (sslmode or "").strip()
        or dialect.default_ssl_mode
    )

    if not host:

        raise DBConnectionError(
            "Host is required.",
            "form"
        )

    if "://" in host:

        raise DBConnectionError(
            "Enter only the host name, not a full "
            "connection URL.",
            "form"
        )

    if not _HOST_RE.match(host):

        raise DBConnectionError(
            "Host contains spaces or invalid characters.",
            "form"
        )

    try:

        port_number = int(str(port).strip())

    except (TypeError, ValueError):

        raise DBConnectionError(
            "Port must be a number between 1 and 65535.",
            "form"
        ) from None

    if not 1 <= port_number <= 65535:

        raise DBConnectionError(
            "Port must be a number between 1 and 65535.",
            "form"
        )

    if not database:

        raise DBConnectionError(
            "Database name is required.",
            "form"
        )

    if not user:

        raise DBConnectionError(
            "User is required.",
            "form"
        )

    if sslmode not in dialect.ssl_modes:

        raise DBConnectionError(
            "Invalid SSL mode.",
            "form"
        )

    if dialect.has_schemas and not is_valid_pg_schema_name(pg_schema):

        raise DBConnectionError(
            "Schema name may contain only letters, "
            "digits and underscores.",
            "form"
        )

    return {
        "host": host,
        "port": port_number,
        "database": database,
        "user": user,
        "sslmode": sslmode,
        "pg_schema": pg_schema if dialect.has_schemas else None
    }


# ============================================================
# Optional SSRF guard
#
# لو التطبيق هيتنشر Online، أي حد يقدر يكتب Host، فالسيرفر نفسه
# ممكن يتستخدم لفحص الشبكة الداخلية. فعّل:
#
#     BLOCK_PRIVATE_HOSTS=true
#
# بيرفض أي Host بيتحل لـ IP خاص / loopback / link-local.
# (مقفول افتراضيًا عشان الاستخدام المحلي.)
#
# حد معروف: الفحص بيحصل قبل الاتصال، فمش بيحمي ضد DNS rebinding.
# ============================================================

def _check_host_allowed(host: str):

    flag = os.getenv("BLOCK_PRIVATE_HOSTS", "").strip().lower()

    if flag not in ("1", "true", "yes"):
        return

    try:

        addresses = socket.getaddrinfo(host, None)

    except OSError:

        raise DBConnectionError(
            GENERIC_CONNECTION_ERROR,
            "connect"
        ) from None

    for address in addresses:

        ip = ipaddress.ip_address(
            address[4][0].split("%")[0]
        )

        if ip.version == 6 and ip.ipv4_mapped:

            ip = ip.ipv4_mapped

        if not ip.is_global:

            logger.warning(
                "Blocked connection to a non-public host."
            )

            raise DBConnectionError(
                GENERIC_CONNECTION_ERROR,
                "connect"
            )


# ============================================================
# Internals
# ============================================================

def _normalize_database_url(database_url: str):
    """
    DATABASE_URL ممكن يبدأ بـ postgres:// (صيغة قديمة بيدّيها بعض
    الـ providers) أو postgresql://. بنثبّت الـ driver على psycopg2
    صراحةً، لأن SQLAlchemy 2.1+ بقى بيختار psycopg (v3) افتراضيًا
    ولو مش متسطّب الاتصال بيفشل.
    """

    database_url = database_url.strip()

    if database_url.startswith("postgres://"):

        database_url = (
            "postgresql://"
            + database_url[len("postgres://"):]
        )

    url = make_url(database_url)

    if url.drivername == "postgresql":

        url = url.set(
            drivername="postgresql+psycopg2"
        )

    return url


def _build_engine(
    url,
    connect_timeout: int,
    connect_args: dict = None
):

    return create_engine(
        url,
        connect_args=(
            connect_args
            if connect_args is not None
            else {"connect_timeout": connect_timeout}
        ),
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=True,
        pool_recycle=300
    )


def _safe_dispose(engine):

    if engine is None:
        return

    try:

        engine.dispose()

    except Exception:

        pass


def _log_failure(error: Exception, password: str = None):
    """
    بنسجّل نوع الخطأ وأول سطر منه في Log السيرفر بس (مش للمستخدم)،
    وبنشيل الباسورد لو ظهر فيه.
    """

    detail = str(error).splitlines()[0] if str(error) else ""

    if password:

        detail = detail.replace(password, "***")

    logger.warning(
        "Database connection failed: %s: %s",
        type(error).__name__,
        detail
    )


def _verify_and_load_schema(engine, pg_schema: str, dialect=None):
    """
    الفحوصات 3 و 4.
    """

    dialect = dialect or get_dialect()

    if not dialect.verify_server(engine):

        raise DBConnectionError(
            GENERIC_CONNECTION_ERROR,
            "connect"
        )

    schema = get_database_schema(
        engine,
        dialect.reflection_schema(pg_schema)
    )

    if not schema:

        raise DBConnectionError(
            NO_TABLES_ERROR,
            "empty"
        )

    return schema


def _detect_write_access(
    engine,
    pg_schema: str,
    dialect=None
) -> bool:
    """
    هل اليوزر ده عنده صلاحية كتابة؟ (للتحذير بس: الـ READ ONLY
    transaction بتمنع الكتابة في كل الأحوال.)
    """

    return (dialect or get_dialect()).detect_write_access(
        engine,
        pg_schema
    )


# ============================================================
# DBContext
# ============================================================

class DBContext:

    def __init__(
        self,
        engine,
        schema: dict,
        db_name: str,
        pg_schema: str = "public",
        is_demo: bool = False,
        has_write_access: bool = False,
        statement_timeout_ms: int = DEFAULT_STATEMENT_TIMEOUT_MS,
        policy: dict = None,
        dialect=None,
        temp_path: str = None
    ):

        self.dialect = dialect or get_dialect()

        # ملف SQLite المرفوع (بيتمسح مع الـ Session)
        self.temp_path = temp_path

        self.engine = engine
        self.schema = schema
        self.db_name = db_name
        self.pg_schema = pg_schema
        self.is_demo = is_demo
        self.has_write_access = has_write_access
        self.statement_timeout_ms = statement_timeout_ms

        # سياسة الوصول بتاعة الـ Session (أعمدة RESTRICTED / DENIED).
        # لو متبعتتش، بتتبني تلقائيًا من أسماء الأعمدة.
        self.policy = (
            policy
            if policy is not None
            else build_effective_policy(schema, is_demo=is_demo)
        )

        # كاش مربوط بالـ Session دي بس
        self.value_cache = {}
        self.entity_catalog = None

    @property
    def display_name(self) -> str:

        return "Chinook" if self.is_demo else self.db_name

    @property
    def policy_summary(self) -> dict:
        """
        {"RESTRICTED": ["Customer.Email", ...], "DENIED": [...]}
        """

        return summarize_policy(self.policy)

    def execute(self, query: str):

        return execute_query(
            self.engine,
            query,
            pg_schema=self.pg_schema,
            statement_timeout_ms=self.statement_timeout_ms,
            dialect=self.dialect
        )

    def dispose(self):

        _safe_dispose(self.engine)

        if self.temp_path:

            try:

                os.remove(self.temp_path)

            except OSError:

                pass

            self.temp_path = None

    def __repr__(self):

        # من غير أي بيانات اتصال
        return (
            f"DBContext(type={self.dialect.key!r}, "
            f"db={self.db_name!r}, "
            f"schema={self.pg_schema!r}, "
            f"tables={len(self.schema)})"
        )


# ============================================================
# Entry points
# ============================================================

def connect_custom(
    host,
    port,
    database,
    user,
    password,
    sslmode=None,
    pg_schema="public",
    dialect="postgresql"
) -> DBContext:
    """
    اتصال بسيرفر (PostgreSQL أو MySQL/MariaDB).
    SQLite ليه connect_sqlite (رفع ملف).
    """

    dialect = get_dialect(dialect)

    form = validate_connection_form(
        host,
        port,
        database,
        user,
        sslmode,
        pg_schema,
        dialect
    )

    engine = None

    try:

        _check_host_allowed(form["host"])

        url = dialect.build_url(
            form,
            password
        )

        engine = _build_engine(
            url,
            CONNECT_TIMEOUT_SECONDS,
            dialect.connect_args(
                form,
                CONNECT_TIMEOUT_SECONDS
            )
        )

        schema = _verify_and_load_schema(
            engine,
            form["pg_schema"],
            dialect
        )

        has_write_access = _detect_write_access(
            engine,
            form["pg_schema"],
            dialect
        )

        return DBContext(
            engine=engine,
            schema=schema,
            db_name=form["database"],
            pg_schema=form["pg_schema"],
            is_demo=False,
            has_write_access=has_write_access,
            dialect=dialect
        )

    except DBConnectionError:

        _safe_dispose(engine)

        raise

    except Exception as error:

        _log_failure(error, password)

        _safe_dispose(engine)

        # from None: مفيش Exception متسلسل يتعرض للمستخدم بالغلط
        raise DBConnectionError(
            GENERIC_CONNECTION_ERROR,
            "connect"
        ) from None


def connect_sqlite(
    file_bytes: bytes,
    filename: str = ""
) -> DBContext:
    """
    SQLite: المستخدم بيرفع الملف (مش بيكتب مسار على السيرفر، لأن ده
    كان هيسمح بقراءة أي ملف عليه). الملف بيتحفظ مؤقتًا باسم عشوائي،
    وبيتفتح للقراءة بس (mode=ro)، وبيتمسح لما الـ Session تخلص.
    """

    dialect = get_dialect("sqlite")

    max_mb = int(
        os.getenv(
            "MAX_SQLITE_UPLOAD_MB",
            DEFAULT_MAX_SQLITE_UPLOAD_MB
        )
    )

    if not file_bytes:

        raise DBConnectionError(
            "The uploaded file is empty.",
            "form"
        )

    if len(file_bytes) > max_mb * 1024 * 1024:

        raise DBConnectionError(
            f"The file is larger than {max_mb} MB.",
            "form"
        )

    if not file_bytes.startswith(_SQLITE_HEADER):

        raise DBConnectionError(
            "This is not a valid SQLite database file.",
            "form"
        )

    engine = None
    temp_path = None

    try:

        handle, temp_path = tempfile.mkstemp(
            prefix="chatdb_",
            suffix=".sqlite"
        )

        with os.fdopen(handle, "wb") as file:

            file.write(file_bytes)

        form = {"path": temp_path}

        engine = _build_engine(
            dialect.build_url(form, None),
            CONNECT_TIMEOUT_SECONDS,
            dialect.connect_args(
                form,
                CONNECT_TIMEOUT_SECONDS
            )
        )

        schema = _verify_and_load_schema(
            engine,
            None,
            dialect
        )

        base_name = os.path.splitext(
            os.path.basename(filename or "")
        )[0]

        return DBContext(
            engine=engine,
            schema=schema,
            db_name=base_name or "sqlite",
            pg_schema=None,
            is_demo=False,
            has_write_access=False,
            dialect=dialect,
            temp_path=temp_path
        )

    except DBConnectionError:

        _safe_dispose(engine)

        _remove_quietly(temp_path)

        raise

    except Exception as error:

        _log_failure(error)

        _safe_dispose(engine)

        _remove_quietly(temp_path)

        raise DBConnectionError(
            "Could not read this SQLite file.",
            "connect"
        ) from None


def _remove_quietly(path):

    if not path:
        return

    try:

        os.remove(path)

    except OSError:

        pass


def connect_demo() -> DBContext:
    """
    الداتابيز التجريبية (Chinook) من DATABASE_URL في .env.
    """

    load_dotenv()

    database_url = os.getenv("DATABASE_URL")

    if not database_url:

        raise DBConnectionError(
            "DATABASE_URL is not configured on the server (.env).",
            "form"
        )

    engine = None

    try:

        url = _normalize_database_url(database_url)

        engine = _build_engine(
            url,
            DEMO_CONNECT_TIMEOUT_SECONDS
        )

        schema = _verify_and_load_schema(
            engine,
            "public",
            get_dialect("postgresql")
        )

        return DBContext(
            engine=engine,
            schema=schema,
            db_name=url.database or "chinook",
            pg_schema="public",
            is_demo=True,
            has_write_access=_detect_write_access(
                engine,
                "public"
            )
        )

    except DBConnectionError:

        _safe_dispose(engine)

        raise

    except Exception as error:

        _log_failure(error)

        _safe_dispose(engine)

        raise DBConnectionError(
            GENERIC_CONNECTION_ERROR,
            "connect"
        ) from None