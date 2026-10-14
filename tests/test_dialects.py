"""
اختبارات أنواع الداتابيز (PostgreSQL / MySQL / SQLite).

بتشتغل بالكامل من غير سيرفر:
    - SQLite: بيبني ملف مؤقت من data/*.csv ويختبر الاتصال والتنفيذ والحماية.
    - الـ Validator والـ Form: على Schema وهمية.

وفيه جزء MySQL بيتفعّل بس لو حددت سيرفر (MariaDB / MySQL) بالمتغيرات:

    MYSQL_TEST_HOST   (مثلًا 127.0.0.1)
    MYSQL_TEST_PORT   (الافتراضي 3306)
    MYSQL_TEST_DB     (فيه Chinook محمّلة، أسماء الجداول بنفس حالة الحروف)
    MYSQL_TEST_USER / MYSQL_TEST_PASSWORD   (يوزر بصلاحية كتابة)
    MYSQL_TEST_RO_USER / MYSQL_TEST_RO_PASSWORD   (يوزر SELECT بس)

لو مفيش سيرفر، الجزء ده بيتخطى ويتسجّل SKIP.

التشغيل (من روت المشروع):

    python -m tests.test_dialects
"""

import os
import sqlite3
import sys
import tempfile
import time

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

import pandas as pd

from db_context import (
    DBConnectionError,
    connect_custom,
    connect_sqlite,
    validate_connection_form
)
from dialects import DIALECTS, get_dialect
from sql_executor import execute_sql
from sql_validator import validate_sql

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data"
)

USER = {"user_id": "u", "role": "USER"}
ADMIN = {"user_id": "a", "role": "ADMIN"}

RESULTS = []


def check(name, condition):

    RESULTS.append(bool(condition))

    print(("PASS: " if condition else "FAIL: ") + name)


def raises(function, *args, **kwargs):

    try:
        function(*args, **kwargs)
    except Exception as error:
        return f"{type(error).__name__}: {str(error)[:120]}"

    return None


def build_sqlite_bytes():

    handle, path = tempfile.mkstemp(suffix=".sqlite")

    os.close(handle)

    connection = sqlite3.connect(path)

    for file_name in sorted(os.listdir(DATA_DIR)):

        if file_name.endswith(".csv"):

            pd.read_csv(
                os.path.join(DATA_DIR, file_name)
            ).to_sql(
                file_name.split(".")[0],
                connection,
                index=False
            )

    connection.close()

    with open(path, "rb") as file:
        data = file.read()

    os.remove(path)

    return data


# ============================================================
# Registry + form
# ============================================================

check(
    "registry: postgresql, mysql, sqlite",
    set(DIALECTS) == {"postgresql", "mysql", "sqlite"}
)

check(
    "get_dialect(None) defaults to PostgreSQL",
    get_dialect().key == "postgresql"
)

check(
    "unknown dialect rejected",
    raises(get_dialect, "oracle") is not None
)

form = validate_connection_form(
    "db.example.com", "3306", "shop", "u", None, "public", "mysql"
)

check(
    "form (mysql): default SSL mode applied, no schema",
    form["sslmode"] == "disable" and form["pg_schema"] is None
)

check(
    "form (mysql): PostgreSQL-only SSL mode rejected",
    raises(
        validate_connection_form,
        "h", 3306, "d", "u", "verify-full", "public", "mysql"
    ) is not None
)

check(
    "form (postgresql): still validates schema names",
    raises(
        validate_connection_form,
        "h", 5432, "d", "u", "prefer", "bad schema!", "postgresql"
    ) is not None
)

check(
    "form (sqlite): connect_custom refuses (upload only)",
    raises(connect_custom, "h", 1, "d", "u", "p", dialect="sqlite")
    is not None
)

check(
    "URLs: drivers and read-only flags",
    get_dialect("postgresql").build_url(
        {"user": "u", "host": "h", "port": 5432,
         "database": "d", "sslmode": "require"}, "p"
    ).drivername == "postgresql+psycopg2"
    and get_dialect("mysql").build_url(
        {"user": "u", "host": "h", "port": 3306, "database": "d"}, "p"
    ).drivername == "mysql+pymysql"
    and "mode=ro" in str(
        get_dialect("sqlite").build_url({"path": "/tmp/x.db"}, None)
    )
)


# ============================================================
# Validators (Schema وهمية)
# ============================================================

SCHEMA = {
    "Artist": {
        "columns": [
            {"name": "ArtistId", "type": "INTEGER"},
            {"name": "Name", "type": "TEXT"}
        ],
        "foreign_keys": []
    }
}

CASES = {
    "mysql": {
        "backtick": 'SELECT `Name` FROM "Artist"',
        "# comment": 'SELECT "Name" FROM "Artist" # x',
        "@@version": 'SELECT @@version FROM "Artist"',
        "user variable": 'SELECT @x := 1 FROM "Artist"',
        "SLEEP": 'SELECT SLEEP(3) FROM "Artist"',
        "BENCHMARK": 'SELECT BENCHMARK(100000000, MD5(1)) FROM "Artist"',
        "LOAD_FILE": 'SELECT LOAD_FILE(\'/etc/passwd\') FROM "Artist"',
        "mysql.user": 'SELECT "Name" FROM "Artist" CROSS JOIN mysql.user',
        "information_schema": (
            'SELECT "Name" FROM "Artist" '
            "CROSS JOIN information_schema.tables"
        ),
        "INTO OUTFILE": 'SELECT "Name" FROM "Artist" INTO OUTFILE \'/tmp/x\'',
        "brackets": 'SELECT [Name] FROM "Artist"',
    },
    "sqlite": {
        "sqlite_master": 'SELECT "Name" FROM "Artist" CROSS JOIN sqlite_master',
        "pragma_table_info": (
            'SELECT "Name" FROM "Artist" '
            "CROSS JOIN pragma_table_info('Artist')"
        ),
        "load_extension": 'SELECT load_extension(\'x\') FROM "Artist"',
        "randomblob": 'SELECT randomblob(1000000000) FROM "Artist"',
        "backtick": 'SELECT `Name` FROM "Artist"',
        "brackets": 'SELECT [Name] FROM "Artist"',
    },
    "postgresql": {
        "pg_sleep": 'SELECT pg_sleep(5) FROM "Artist"',
        "pg_catalog": 'SELECT "Name" FROM "Artist" CROSS JOIN pg_user',
        "information_schema": (
            'SELECT "Name" FROM "Artist" '
            "CROSS JOIN information_schema.tables"
        ),
    },
}

for key, cases in CASES.items():

    dialect = get_dialect(key)

    for label, sql in cases.items():

        check(
            f"validator ({key}) rejects: {label}",
            raises(validate_sql, sql, SCHEMA, dialect) is not None
        )

    check(
        f"validator ({key}) accepts a normal query",
        raises(
            validate_sql,
            'SELECT "Name" FROM "Artist" WHERE "Name" LIKE \'A%\'',
            SCHEMA,
            dialect
        ) is None
    )

check(
    "validator (mysql): '#' inside a string or quoted name is not a comment",
    raises(
        validate_sql,
        'SELECT "Name" FROM "Artist" WHERE "Name" = \'#1\'',
        SCHEMA,
        get_dialect("mysql")
    ) is None
)

check(
    "validator: Postgres arrays with [] stay allowed for PostgreSQL",
    raises(
        validate_sql,
        'SELECT ("Name")[1] FROM "Artist"',
        SCHEMA,
        get_dialect("postgresql")
    ) is None
)


# ============================================================
# Alias shadowing (الـ alias اللي بيستخدم اسم جدول تاني)
# ============================================================

TWO_TABLES = {
    "Customer": {
        "columns": [
            {"name": "CustomerId", "type": "INTEGER"},
            {"name": "City", "type": "TEXT"}
        ],
        "foreign_keys": []
    },
    "Employee": {
        "columns": [
            {"name": "EmployeeId", "type": "INTEGER"},
            {"name": "City", "type": "TEXT"}
        ],
        "foreign_keys": []
    },
}

for dialect_key in ("postgresql", "mysql", "sqlite"):

    dialect = get_dialect(dialect_key)

    for label, sql in {
        "AS": 'SELECT "Customer"."City" FROM "Employee" AS "Customer"',
        "without AS": 'SELECT "Customer"."City" FROM "Employee" "Customer"',
        "JOIN": (
            'SELECT "Employee"."City" FROM "Customer" '
            'JOIN "Employee" AS "Customer" ON 1 = 1'
        ),
        "comma join": (
            'SELECT "Employee"."City" FROM "Customer", '
            '"Employee" AS "Customer"'
        ),
    }.items():

        check(
            f"alias shadowing ({dialect_key}) rejected: {label}",
            raises(validate_sql, sql, TWO_TABLES, dialect) is not None
        )

    for label, sql in {
        "short alias": 'SELECT e."City" FROM "Employee" AS e',
        "alias equal to its own table": (
            'SELECT "Customer"."City" FROM "Customer" AS "Customer"'
        ),
        "normal join": (
            'SELECT "Customer"."City" FROM "Customer" '
            'JOIN "Employee" ON "Customer"."CustomerId" = '
            '"Employee"."EmployeeId"'
        ),
        "column alias": 'SELECT COUNT(*) AS "total" FROM "Customer"',
    }.items():

        check(
            f"alias shadowing ({dialect_key}) still allows: {label}",
            raises(validate_sql, sql, TWO_TABLES, dialect) is None
        )


# ============================================================
# SQLite end-to-end (من غير سيرفر)
# ============================================================

DATA = build_sqlite_bytes()

sq = connect_sqlite(DATA, "chinook.sqlite")

path = sq.temp_path

check(
    "sqlite: connected, tables loaded, name from the file",
    sq.dialect.key == "sqlite"
    and len(sq.schema) >= 10
    and sq.db_name == "chinook"
    and sq.pg_schema is None
)

check(
    "sqlite: the temp file exists while the session lives",
    os.path.exists(path)
)

error = raises(
    sq.execute,
    'INSERT INTO "Artist" ("ArtistId", "Name") VALUES (99999, \'x\')'
)

check(
    "sqlite: INSERT is rejected by SQLite itself (read-only database)",
    error is not None
    and "readonly" in error.lower().replace("-", "").replace(" ", "")
)

check(
    "sqlite: nothing was written",
    sq.execute(
        'SELECT COUNT(*) FROM "Artist" WHERE "ArtistId" = 99999'
    )[1][0][0] == 0
)

sq.statement_timeout_ms = 1000

started = time.time()

error = raises(
    sq.execute,
    'SELECT COUNT(*) FROM "Track" a, "Track" b, "Track" c'
)

check(
    "sqlite: a slow query is interrupted by the timeout",
    error is not None and time.time() - started < 10
)

sq.statement_timeout_ms = 30000

columns, rows, total, removed = execute_sql(
    'SELECT * FROM "Customer" WHERE "CustomerId" = 6', USER, sq
)

check(
    "sqlite USER: SELECT * hides Email / Phone / Address / Fax",
    not ({"Email", "Phone", "Address", "Fax"} & set(columns))
    and "FirstName" in columns
    and len(removed) == 4
)

columns, rows, total, removed = execute_sql(
    'SELECT * FROM "Customer" WHERE "CustomerId" = 6', ADMIN, sq
)

check(
    "sqlite ADMIN: sees Email",
    "Email" in columns and removed == []
)

columns, rows, total, removed = execute_sql(
    'SELECT "BillingCountry", COUNT(*) AS "n" FROM "Invoice" '
    'GROUP BY "BillingCountry" ORDER BY "n" DESC',
    USER,
    sq
)

check(
    "sqlite: aggregate query returns real total",
    columns == ["BillingCountry", "n"] and total >= 20
)

check(
    "sqlite: Invoice.BillingAddress hidden from USER (policy)",
    "Invoice.BillingAddress" in sq.policy_summary["RESTRICTED"]
)

check(
    "sqlite: Employee.City cannot be read through an alias named Customer",
    raises(
        execute_sql,
        'SELECT "Customer"."City" FROM "Employee" AS "Customer"',
        USER,
        sq
    ) is not None
)

sq.dispose()

check(
    "sqlite: temp file deleted on dispose",
    not os.path.exists(path)
)

check(
    "sqlite: non-SQLite bytes rejected",
    "not a valid SQLite" in (
        raises(connect_sqlite, b"hello world" * 100, "x.db") or ""
    )
)

check(
    "sqlite: empty upload rejected",
    raises(connect_sqlite, b"", "x.db") is not None
)

os.environ["MAX_SQLITE_UPLOAD_MB"] = "0"

check(
    "sqlite: size limit enforced (MAX_SQLITE_UPLOAD_MB)",
    "larger than" in (raises(connect_sqlite, DATA, "x.db") or "")
)

del os.environ["MAX_SQLITE_UPLOAD_MB"]


# ============================================================
# MySQL / MariaDB (اختياري: محتاج سيرفر)
# ============================================================

MYSQL_HOST = os.getenv("MYSQL_TEST_HOST")

if not MYSQL_HOST:

    print("SKIP: MySQL tests (set MYSQL_TEST_HOST to enable them)")

else:

    port = int(os.getenv("MYSQL_TEST_PORT", "3306"))
    name = os.environ["MYSQL_TEST_DB"]
    user = os.environ["MYSQL_TEST_USER"]
    password = os.environ["MYSQL_TEST_PASSWORD"]

    my = connect_custom(
        MYSQL_HOST, port, name, user, password, dialect="mysql"
    )

    check(
        "mysql: connected, tables loaded, schema is the database",
        my.dialect.key == "mysql"
        and "Customer" in my.schema
        and my.pg_schema is None
    )

    check(
        "mysql: a write-capable user is flagged",
        my.has_write_access is True
    )

    ro_user = os.getenv("MYSQL_TEST_RO_USER")

    if ro_user:

        ro = connect_custom(
            MYSQL_HOST, port, name, ro_user,
            os.environ["MYSQL_TEST_RO_PASSWORD"], dialect="mysql"
        )

        check(
            "mysql: a read-only user is not flagged",
            ro.has_write_access is False
        )

        ro.dispose()

    columns, rows = my.execute(
        'SELECT "FirstName", "Country" FROM "Customer" '
        'ORDER BY "CustomerId" LIMIT 2'
    )

    check(
        "mysql: double-quoted identifiers work (ANSI_QUOTES)",
        columns == ["FirstName", "Country"] and len(rows) == 2
    )

    error = raises(
        my.execute,
        'INSERT INTO "Artist" ("ArtistId", "Name") '
        "VALUES (99999, 'x')"
    )

    check(
        "mysql: INSERT is rejected by the database (READ ONLY)",
        error is not None and "READ ONLY" in error.upper()
    )

    check(
        "mysql: nothing was written",
        my.execute(
            'SELECT COUNT(*) FROM "Artist" WHERE "ArtistId" = 99999'
        )[1][0][0] == 0
    )

    my.statement_timeout_ms = 1000

    started = time.time()

    error = raises(
        my.execute,
        'SELECT COUNT(*) FROM "Track" a, "Track" b, "Track" c'
    )

    check(
        "mysql: a slow query is cut by the timeout",
        error is not None and time.time() - started < 10
    )

    my.statement_timeout_ms = 30000

    columns, rows, total, removed = execute_sql(
        'SELECT * FROM "Customer" WHERE "CustomerId" = 6', USER, my
    )

    check(
        "mysql USER: SELECT * hides Email / Phone / Address / Fax",
        not ({"Email", "Phone", "Address", "Fax"} & set(columns))
        and len(removed) == 4
    )

    error = raises(
        connect_custom, MYSQL_HOST, port, name, user, "WRONG-PW",
        dialect="mysql"
    )

    check(
        "mysql: wrong password -> generic error without details",
        error is not None
        and "WRONG-PW" not in error
        and "Could not connect" in error
    )

    my.dispose()


# ============================================================
# Summary
# ============================================================

print()
print(f"{sum(RESULTS)}/{len(RESULTS)} passed")
print()
print("--- Tests Completed ---")

if not all(RESULTS):
    sys.exit(1)
