from sql_validator import validate_sql
from tests.helpers import get_demo_db, get_user


# =========================================================
# Safe Queries
# =========================================================

safe_queries = [
    'SELECT * FROM "Artist"',
    'SELECT COUNT(*) FROM "Customer"',
    'SELECT "Name" FROM "Genre"',
]


# =========================================================
# Unsafe Queries
# =========================================================

unsafe_queries = [
    'DROP TABLE "Artist"',
    'DELETE FROM "Customer"',
    'UPDATE "Artist" SET "Name" = \'Hacked\'',
    'INSERT INTO "Artist" ("Name") VALUES (\'Hacker\')',
    'ALTER TABLE "Artist" ADD COLUMN "Test" TEXT',
    'TRUNCATE TABLE "Artist"',
]


# =========================================================
# Test Safe Queries
# =========================================================

print("\n" + "=" * 70)
print("TESTING SAFE QUERIES")
print("=" * 70)


for query in safe_queries:

    try:

        validate_sql(query, get_demo_db().schema, get_demo_db().dialect)

        print("PASS:", query)

    except Exception as e:

        print("FAIL:", query)
        print("ERROR:", e)


# =========================================================
# Test Unsafe Queries
# =========================================================

print("\n" + "=" * 70)
print("TESTING UNSAFE QUERIES")
print("=" * 70)


for query in unsafe_queries:

    try:

        validate_sql(query, get_demo_db().schema, get_demo_db().dialect)

        print("FAIL - UNSAFE QUERY WAS ACCEPTED:")
        print(query)

    except ValueError as e:

        print("PASS - UNSAFE QUERY REJECTED:")
        print(query)
        print("REASON:", e)