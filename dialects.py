"""
dialects.py

كل الفروق بين أنواع الداتابيز في مكان واحد. باقي الكود (الـ pipeline،
الـ Authorization، الـ Policy، الـ Discovery) ما بيعرفش أنهي نوع، وبينادي
على الـ Dialect بس.

القرار التصميمي الأساسي: **الـ identifiers دايمًا بين double quotes**
("Table"."Column") في كل الأنواع. الـ scanner والـ validator والـ
Authorization كلهم مبنيين على كده، فبدل ما نعيد كتابتهم لكل نوع:

    PostgreSQL -> double quotes أصلًا
    SQLite     -> بيقبل double quotes أصلًا
    MySQL      -> بنشغّل الـ Session بـ ANSI_QUOTES، فالـ double quotes
                  بقت identifiers (مش strings)

وأي طريقة تانية لكتابة الـ identifiers (backticks أو [brackets] أو
# comments) بتترفض، لأنها كانت هتعدّي من فحص الـ Authorization.

الأنواع المدعومة دلوقتي: PostgreSQL و MySQL (و MariaDB) و SQLite.
(SQL Server و Oracle لسه: مفيش بيئة اختبار ليهم، ومحتاجين تعامل خاص.)
"""

import re
import time

from sqlalchemy import text
from sqlalchemy.engine import URL


DEFAULT_STATEMENT_TIMEOUT_MS = 30_000

_SCHEMA_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def is_valid_schema_name(name: str) -> bool:

    return bool(
        isinstance(name, str)
        and _SCHEMA_NAME_RE.match(name)
    )


def _names_pattern(*alternatives: str):

    return re.compile(
        r"\b(?:" + "|".join(alternatives) + r")\b",
        flags=re.IGNORECASE
    )


# ============================================================
# Base
# ============================================================

class Dialect:

    # مفتاح داخلي، واسم للعرض
    key = ""
    label = ""

    # أرقام الـ Port الافتراضي (None = مفيش سيرفر، زي SQLite)
    default_port = None

    # SQLite: ملف مش سيرفر
    file_based = False

    # هل فيه اختيار Schema (PostgreSQL بس)؟
    has_schemas = False

    # اختيارات الـ SSL في الفورم (فاضية = مفيش حقل SSL)
    ssl_modes = ()
    default_ssl_mode = None

    # الاسم اللي بيتكتب في الـ prompts
    prompt_name = ""

    # ملاحظات syntax بتتحط في الـ prompt (للداتابيز المخصصة)
    prompt_rules = ""

    # أسماء دوال/جداول خطرة (تتفحص بره الـ strings والـ quoted identifiers)
    forbidden_names = None

    # حروف ممنوعة بره الـ strings (بتتفحص على الـ "structure")
    forbidden_chars = ()

    # --- connection -----------------------------------------

    def build_url(self, form: dict, password: str) -> URL:
        raise NotImplementedError

    def connect_args(self, form: dict, timeout: int) -> dict:
        raise NotImplementedError

    def verify_server(self, engine) -> bool:
        raise NotImplementedError

    def reflection_schema(self, schema_name):
        """
        القيمة اللي بتتمرر لـ SQLAlchemy inspector (schema=...).
        """

        return None

    # --- execution ------------------------------------------

    def prepare_connection(
        self,
        connection,
        schema_name,
        timeout_ms: int
    ):
        """
        بتتنادى جوه الـ transaction قبل كل استعلام: read-only + timeout
        (+ الـ Schema/ANSI_QUOTES حسب النوع).
        """

        raise NotImplementedError

    def detect_write_access(self, engine, schema_name) -> bool:
        """
        للتحذير بس. الحماية الفعلية هي prepare_connection.
        """

        return False

    # --- SQL validation -------------------------------------

    def validate_structure(self, structure: str):
        """
        فحوصات إضافية على الـ structure (النص بعد ما الـ strings
        والـ quoted identifiers اتقنّعوا). بترفع ValueError.
        """

        for char in self.forbidden_chars:

            if char in structure:

                raise ValueError(
                    "Unsafe SQL detected: "
                    f"{char!r} is not allowed in "
                    f"{self.label} queries."
                )

        if self.forbidden_names is not None:

            match = self.forbidden_names.search(structure)

            if match:

                raise ValueError(
                    f"Unsafe SQL detected: {match.group(0)}"
                )


# ============================================================
# PostgreSQL
# ============================================================

class PostgreSQL(Dialect):

    key = "postgresql"
    label = "PostgreSQL"
    default_port = 5432
    has_schemas = True
    ssl_modes = (
        "disable", "allow", "prefer",
        "require", "verify-ca", "verify-full"
    )
    default_ssl_mode = "prefer"
    prompt_name = "PostgreSQL"
    prompt_rules = """
- Use ILIKE for case-insensitive text matching.
- Use EXTRACT(YEAR FROM "col") or DATE_TRUNC('month', "col") for
  dates. The `::` cast syntax is allowed.
- Concatenate text with ||.
""".strip()

    # الأسماء دي كانت في sql_validator.py (اتنقلت هنا من غير تغيير)
    forbidden_names = _names_pattern(
        r"pg_\w*",
        r"lo_\w+",
        r"dblink\w*",
        r"set_config",
        r"current_setting",
        r"query_to_xml\w*",
        r"table_to_xml\w*",
        r"cursor_to_xml",
        r"schema_to_xml\w*",
        r"database_to_xml\w*",
        r"information_schema",
        r"txid_\w+"
    )

    def build_url(self, form, password):

        return URL.create(
            drivername="postgresql+psycopg2",
            username=form["user"],
            password=password or None,
            host=form["host"],
            port=form["port"],
            database=form["database"],
            query={"sslmode": form["sslmode"]}
        )

    def connect_args(self, form, timeout):

        return {"connect_timeout": timeout}

    def verify_server(self, engine):

        with engine.connect() as connection:

            version = connection.execute(
                text("SELECT version()")
            ).scalar()

        return bool(version and "PostgreSQL" in str(version))

    def reflection_schema(self, schema_name):

        return schema_name or "public"

    def prepare_connection(
        self,
        connection,
        schema_name,
        timeout_ms
    ):

        schema_name = schema_name or "public"

        if not is_valid_schema_name(schema_name):

            raise ValueError("Invalid schema name.")

        connection.execute(
            text("SET TRANSACTION READ ONLY")
        )

        connection.execute(
            text(f"SET LOCAL statement_timeout = {int(timeout_ms)}")
        )

        # اتفحص بالـ regex فوق، فآمن نحطه جوه quotes
        connection.execute(
            text(f'SET LOCAL search_path TO "{schema_name}"')
        )

    def detect_write_access(self, engine, schema_name):

        query = text(
            """
            SELECT COALESCE(
                bool_or(
                    has_table_privilege(
                        c.oid,
                        'INSERT,UPDATE,DELETE'
                    )
                ),
                false
            )
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = :schema
              AND c.relkind IN ('r', 'p')
            """
        )

        try:

            with engine.connect() as connection:

                return bool(
                    connection.execute(
                        query,
                        {"schema": schema_name or "public"}
                    ).scalar()
                )

        except Exception:

            return False

    def validate_structure(self, structure):

        # الفحص الأصلي (pg_*, lo_*, ...)
        super().validate_structure(structure)


# ============================================================
# MySQL / MariaDB
# ============================================================

class MySQL(Dialect):

    key = "mysql"
    label = "MySQL / MariaDB"
    default_port = 3306
    ssl_modes = ("disable", "require")
    default_ssl_mode = "disable"
    prompt_name = "MySQL"
    prompt_rules = """
- Identifiers are ALWAYS written with double quotes, for example
  "Customer"."Email" (the session runs in ANSI_QUOTES mode). NEVER use
  backticks. Strings use single quotes.
- Use LIKE for text matching (it is case-insensitive by default).
  ILIKE does not exist.
- Use EXTRACT(YEAR FROM "col") or YEAR("col") for dates. Do not use
  DATE_TRUNC or the `::` cast syntax; use CAST("col" AS SIGNED) or
  CAST("col" AS DECIMAL(10,2)).
- Concatenate text with CONCAT(a, b). The || operator is NOT concatenation.
- FULL OUTER JOIN does not exist.
""".strip()

    forbidden_names = _names_pattern(
        r"sleep",
        r"benchmark",
        r"load_file",
        r"get_lock",
        r"release_lock",
        r"release_all_locks",
        r"is_free_lock",
        r"is_used_lock",
        r"master_pos_wait",
        r"sys_eval",
        r"sys_exec",
        r"information_schema",
        r"performance_schema",
        r"mysql",
        r"sys",
        r"outfile",
        r"dumpfile",
    )

    # backtick و [..] بيعدّوا فحص الـ identifiers، و @ متغيّرات الـ Session.
    # (# تعليق في MySQL، وبيتفحص لوحده في validate_structure تحت.)
    forbidden_chars = ("`", "[", "]", "@")

    def validate_structure(self, structure):

        # mask_sql بيحوّل محتوى الـ quoted identifiers لـ #، فبنشيلها
        # الأول وبعدين نشوف لو فيه # حقيقية (تعليق) بره الـ identifiers.
        if "#" in re.sub(r'"#*"', '""', structure):

            raise ValueError(
                "SQL comments are not allowed."
            )

        super().validate_structure(structure)

    def build_url(self, form, password):

        return URL.create(
            drivername="mysql+pymysql",
            username=form["user"],
            password=password or None,
            host=form["host"],
            port=form["port"],
            database=form["database"],
            query={"charset": "utf8mb4"}
        )

    def connect_args(self, form, timeout):

        args = {
            "connect_timeout": timeout,
            "read_timeout": 60,
            "write_timeout": 60,
        }

        if form.get("sslmode") == "require":

            # PyMySQL بيفعّل TLS لما ssl يبقى dict مش فاضي
            args["ssl"] = {"fake_flag_to_enable_tls": True}

        return args

    def verify_server(self, engine):

        with engine.connect() as connection:

            version = connection.execute(
                text("SELECT VERSION()")
            ).scalar()

        return bool(version)

    def prepare_connection(
        self,
        connection,
        schema_name,
        timeout_ms
    ):

        # الـ double quotes تبقى identifiers
        connection.execute(
            text(
                "SET SESSION sql_mode = "
                "CONCAT(@@sql_mode, ',ANSI_QUOTES')"
            )
        )

        connection.execute(
            text("SET SESSION TRANSACTION READ ONLY")
        )

        timeout_ms = int(timeout_ms)

        try:

            # MySQL 5.7.8+
            connection.execute(
                text(f"SET SESSION max_execution_time = {timeout_ms}")
            )

        except Exception:

            # MariaDB (بالثواني)
            connection.execute(
                text(
                    "SET SESSION max_statement_time = "
                    f"{max(timeout_ms // 1000, 1)}"
                )
            )

    def detect_write_access(self, engine, schema_name):

        try:

            with engine.connect() as connection:

                grants = " ".join(
                    str(row[0])
                    for row in connection.execute(
                        text("SHOW GRANTS FOR CURRENT_USER()")
                    )
                )

            return bool(
                re.search(
                    r"\b(ALL PRIVILEGES|INSERT|UPDATE|DELETE)\b",
                    grants,
                    flags=re.IGNORECASE
                )
            )

        except Exception:

            return False


# ============================================================
# SQLite
# ============================================================

class SQLite(Dialect):

    key = "sqlite"
    label = "SQLite"
    file_based = True
    prompt_name = "SQLite"
    prompt_rules = """
- Identifiers are written with double quotes, for example
  "Customer"."Email". NEVER use backticks or [brackets].
- Use LIKE for text matching (case-insensitive for ASCII). ILIKE does
  not exist.
- There is no EXTRACT or DATE_TRUNC. Use strftime('%Y', "col") for the
  year, strftime('%Y-%m', "col") for the month, and CAST(x AS INTEGER)
  when a number is needed. The `::` cast syntax does not exist.
- Concatenate text with ||.
- Booleans are stored as 0 and 1.
""".strip()

    forbidden_names = _names_pattern(
        r"sqlite_\w+",
        r"pragma_\w+",
        r"load_extension",
        r"readfile",
        r"writefile",
        r"edit",
        r"fts3_tokenizer",
        r"randomblob",
        r"zeroblob",
    )

    # SQLite بيقبل backticks و [brackets] كـ identifiers
    forbidden_chars = ("`", "[", "]")

    def build_url(self, form, password=None):

        # mode=ro: الملف بيتفتح للقراءة بس على مستوى SQLite نفسه
        path = form["path"].replace("\\", "/")

        return URL.create(
            drivername="sqlite",
            database=f"file:{path}",
            query={"mode": "ro", "uri": "true"}
        )

    def connect_args(self, form, timeout):

        return {
            "timeout": timeout,
            "check_same_thread": False
        }

    def verify_server(self, engine):

        with engine.connect() as connection:

            return bool(
                connection.execute(
                    text("SELECT sqlite_version()")
                ).scalar()
            )

    def prepare_connection(
        self,
        connection,
        schema_name,
        timeout_ms
    ):

        connection.execute(text("PRAGMA query_only = ON"))

        # SQLite مفيهوش statement_timeout: بنقطع الاستعلام بـ progress handler
        raw = connection.connection.driver_connection

        deadline = time.monotonic() + int(timeout_ms) / 1000

        raw.set_progress_handler(
            lambda: 1 if time.monotonic() > deadline else 0,
            10_000
        )

    def detect_write_access(self, engine, schema_name):

        # الملف مفتوح mode=ro
        return False


# ============================================================
# Registry
# ============================================================

DIALECTS = {
    dialect.key: dialect
    for dialect in (
        PostgreSQL(),
        MySQL(),
        SQLite(),
    )
}

DEFAULT_DIALECT_KEY = "postgresql"


def get_dialect(key=None) -> Dialect:
    """
    key=None -> PostgreSQL (التوافق مع الكود القديم).
    """

    key = (key or DEFAULT_DIALECT_KEY).strip().lower()

    if key not in DIALECTS:

        raise ValueError(f"Unsupported database type: {key}")

    return DIALECTS[key]
