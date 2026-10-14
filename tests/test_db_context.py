"""
tests/test_db_context.py

تشغيل:

    python -m tests.test_db_context

القسم الأول (Offline) مش محتاج داتابيز. القسم التاني (Live) بيشتغل
بس لو DATABASE_URL موجود في .env، وبيتأكد من الحاجات اللي بتتفرض
على مستوى Postgres نفسه (READ ONLY, timeout, search_path). كل
استعلامات الـ Live قراءة بس: مفيش أي محاولة كتابة على الداتابيز بتاعتك.
"""

import logging
import os
import sys

from dotenv import load_dotenv

import value_resolver
from db_context import (
    DBConnectionError,
    DBContext,
    GENERIC_CONNECTION_ERROR,
    connect_custom,
    connect_demo,
    validate_connection_form
)
from schema import format_schema_for_llm

load_dotenv()

logging.disable(logging.CRITICAL)

results = []


def check(name, condition, detail=""):

    results.append(bool(condition))

    print(
        ("PASS  " if condition else "FAIL  ")
        + name
        + (f"   [{detail}]" if detail and not condition else "")
    )


def error_of(function):

    try:

        function()

    except DBConnectionError as error:

        return error

    return None


# ============================================================
# Offline
# ============================================================

print("\n--- Offline ---")

# 1) فحوصات الفورم
cases = {
    "empty host": ("", 5432, "d", "u"),
    "URL pasted as host": ("mysql://u:p@h:3306/x", 3306, "d", "u"),
    "host with spaces": ("my host", 5432, "d", "u"),
    "port not a number": ("h", "abc", "d", "u"),
    "port 0": ("h", 0, "d", "u"),
    "port too large": ("h", 65536, "d", "u"),
    "empty database": ("h", 5432, "", "u"),
    "empty user": ("h", 5432, "d", ""),
}

for label, (host, port, database, user) in cases.items():

    error = error_of(
        lambda: validate_connection_form(host, port, database, user)
    )

    check(
        f"form rejects: {label}",
        error is not None and error.kind == "form"
    )

check(
    "form rejects bad sslmode",
    error_of(
        lambda: validate_connection_form("h", 5432, "d", "u", "bogus")
    ) is not None
)

check(
    "form rejects schema name with quotes / SQL",
    error_of(
        lambda: validate_connection_form(
            "h", 5432, "d", "u", "prefer", 'public"; DROP TABLE x'
        )
    ) is not None
)

clean = validate_connection_form(
    " db.example.com ", " 5432 ", " mydb ", " me "
)

check(
    "form cleans valid input",
    clean["host"] == "db.example.com"
    and clean["port"] == 5432
    and clean["database"] == "mydb"
    and clean["user"] == "me"
    and clean["pg_schema"] == "public"
)

# 2) فشل الاتصال: رسالة ثابتة من غير أي تسريب
SECRET = "Sup3rSecretPassw0rd"

error = error_of(
    lambda: connect_custom(
        "127.0.0.1", 1, "mydb", "myuser", SECRET
    )
)

check(
    "unreachable server -> generic message",
    error is not None and error.message == GENERIC_CONNECTION_ERROR
)

check(
    "message leaks no host / user / password / port",
    error is not None
    and not any(
        value in error.message
        for value in ("127.0.0.1", "myuser", SECRET, "mydb")
    )
)

check(
    "no chained exception is exposed",
    error is not None and error.__cause__ is None
)

# 3) عزل الـ Value Resolver بين Sessions (من غير داتابيز حقيقية)


class FakeEngine:

    def dispose(self):
        pass


class FakeDB(DBContext):

    def __init__(self, values):

        super().__init__(
            engine=FakeEngine(),
            schema={
                "Customer": {
                    "columns": [
                        {"name": "Country", "type": "TEXT"}
                    ],
                    "foreign_keys": []
                }
            },
            db_name="fake"
        )

        self._values = values

    def execute(self, query):

        return ["Country"], [(v,) for v in self._values]


db_a = FakeDB(["Brazil", "Canada"])
db_b = FakeDB(["Germany", "France"])

sql_a, _ = value_resolver.resolve_sql_values(
    db_a,
    'SELECT 1 FROM "Customer" WHERE "Customer"."Country" = \'Brazill\''
)

sql_b, _ = value_resolver.resolve_sql_values(
    db_b,
    'SELECT 1 FROM "Customer" WHERE "Customer"."Country" = \'Brazill\''
)

check("session A resolves Brazill -> Brazil", "'Brazil'" in sql_a)

check(
    "session B (different data) does NOT inherit A's cache",
    "'Brazil'" not in sql_b and "Brazill" in sql_b
)

check(
    "caches are separate objects",
    db_a.value_cache is not db_b.value_cache
)

# 4) الـ Schema formatting
small = db_a.schema

check(
    "small schema uses the full format",
    "TABLE: Customer" in format_schema_for_llm(small)
)

big = {
    f"T{i}": {
        "columns": [
            {"name": f"c{j}", "type": "TEXT"}
            for j in range(10)
        ],
        "foreign_keys": []
    }
    for i in range(20)
}

check(
    "large schema switches to compact format",
    "compact" in format_schema_for_llm(big)
)

check(
    "repr() does not leak connection details",
    "fake" in repr(db_a) and "password" not in repr(db_a).lower()
)


# ============================================================
# Live (Demo database from .env)
# ============================================================

print("\n--- Live (DATABASE_URL) ---")

if not os.getenv("DATABASE_URL"):

    print("SKIP  DATABASE_URL is not set")

else:

    try:

        demo_a = connect_demo()
        demo_b = connect_demo()

    except DBConnectionError as error:

        check("connect_demo()", False, error.message)

    else:

        check(
            "connect_demo() loads the schema",
            demo_a.is_demo and len(demo_a.schema) > 0
        )

        _, rows = demo_a.execute("SHOW transaction_read_only")

        check(
            "every query runs in a READ ONLY transaction",
            rows[0][0] == "on",
            rows
        )

        _, rows = demo_a.execute("SHOW statement_timeout")

        check(
            "statement_timeout is applied (30s)",
            rows[0][0] == "30s",
            rows
        )

        _, rows = demo_a.execute("SHOW search_path")

        check(
            "search_path is the selected schema",
            "public" in rows[0][0],
            rows
        )

        check(
            "two sessions have separate engines / caches / schemas",
            demo_a.engine is not demo_b.engine
            and demo_a.value_cache is not demo_b.value_cache
            and demo_a.schema is not demo_b.schema
        )

        if "Customer" in demo_a.schema:

            sql, corrections = value_resolver.resolve_sql_values(
                demo_a,
                'SELECT 1 FROM "Customer" '
                'WHERE "Customer"."Country" = \'Brazill\''
            )

            check(
                "value resolver works on the real DB",
                "'Brazil'" in sql,
                sql
            )

            check(
                "cache is stored on the session object",
                ("Customer", "Country") in demo_a.value_cache
                and not demo_b.value_cache
            )

        demo_a.dispose()
        demo_b.dispose()


# ============================================================

print(f"\n{sum(results)}/{len(results)} passed")

sys.exit(0 if all(results) else 1)