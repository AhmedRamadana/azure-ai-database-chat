"""
اختبارات فحوصات الأمان الجديدة في sql_validator.py
(statements متعددة، SELECT INTO، دوال خطرة، تعليقات...).

التشغيل (من روت المشروع):

    python -m tests.test_sql_safety
"""

import os
import sys

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from sql_validator import validate_sql_safety


RESULTS = []


def check(name, condition):

    RESULTS.append(bool(condition))

    print(("PASS: " if condition else "FAIL: ") + name)


def rejected(sql):

    try:

        validate_sql_safety(sql)

    except ValueError:

        return True

    return False


def main():

    print("--- SQL Safety Tests ---\n")

    # ---------------------------------------------------------
    # لازم تتـرفض
    # ---------------------------------------------------------

    must_reject = {

        "pg_sleep (resource exhaustion)":
            'SELECT pg_sleep(30) FROM "Artist"',

        "pg_read_file":
            "SELECT pg_read_file('/etc/passwd') FROM \"Artist\"",

        "set_config":
            "SELECT set_config('search_path','x',false) "
            'FROM "Artist"',

        "current_setting":
            "SELECT current_setting('server_version') "
            'FROM "Artist"',

        "multiple statements":
            'SELECT "Name" FROM "Artist"; SELECT 1',

        "SELECT INTO (creates a table)":
            'SELECT "Name" INTO "stolen" FROM "Artist"',

        "line comment":
            'SELECT "Name" FROM "Artist" -- hidden',

        "block comment":
            'SELECT "Name" /* x */ FROM "Artist"',

        "query_to_xml (runs SQL from a string)":
            "SELECT query_to_xml('select 1', true, true, '') "
            'FROM "Artist"',

        "dblink":
            "SELECT dblink('host=x','select 1') FROM \"Artist\"",

        "information_schema":
            'SELECT "column_name" FROM information_schema.columns',

        "backslash (E-string tricks)":
            "SELECT E'\\'' FROM \"Artist\"",

        "dollar-quoted string":
            'SELECT $$x$$ FROM "Artist"',

        "unclosed quote":
            'SELECT "Name FROM "Artist"',

        "escaped quote inside identifier":
            'SELECT "Na""me" FROM "Artist"',

        "stacked DROP":
            'SELECT "Name" FROM "Artist"; DROP TABLE "Artist"',

        "DELETE hidden in a string passed to a function":
            "SELECT x FROM \"Artist\" WHERE "
            "f('delete from \"Artist\" returning *')",
    }

    for name, sql in must_reject.items():

        check(f"rejected: {name}", rejected(sql))

    # ---------------------------------------------------------
    # لازم تعدّي (مفيش False Positives على الاستعلامات العادية)
    # ---------------------------------------------------------

    must_accept = {

        "trailing semicolon":
            'SELECT "Name" FROM "Artist";',

        "semicolon inside a string literal":
            'SELECT "Name" FROM "Artist" '
            "WHERE \"Name\" = 'a;b'",

        "'Into the Wild' as a value":
            'SELECT "Name" FROM "Track" '
            "WHERE \"Name\" = 'Into the Wild'",

        "a function name inside a string literal":
            'SELECT "Name" FROM "Artist" '
            "WHERE \"Name\" = 'pg_sleep'",

        "EXTRACT(YEAR FROM ...)":
            'SELECT EXTRACT(YEAR FROM "Invoice"."InvoiceDate"), '
            'COUNT(*) FROM "Invoice" GROUP BY 1',

        "normal JOIN with aggregation":
            'SELECT "Artist"."Name", COUNT("Track"."TrackId") '
            'FROM "Artist" JOIN "Album" '
            'ON "Artist"."ArtistId" = "Album"."ArtistId" '
            'JOIN "Track" ON "Album"."AlbumId" = "Track"."AlbumId" '
            'GROUP BY "Artist"."ArtistId", "Artist"."Name" '
            'ORDER BY 2 DESC LIMIT 5',

        "price multiplication":
            'SELECT SUM("InvoiceLine"."UnitPrice" * '
            '"InvoiceLine"."Quantity") AS "TotalSpending" '
            'FROM "InvoiceLine"',
    }

    for name, sql in must_accept.items():

        check(f"accepted: {name}", not rejected(sql))

    print()

    passed = sum(RESULTS)

    print(f"{passed}/{len(RESULTS)} passed")

    print("\n--- Tests Completed ---")

    if passed != len(RESULTS):

        sys.exit(1)


if __name__ == "__main__":

    main()