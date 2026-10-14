from sql_validator import validate_sql
from tests.helpers import get_demo_db, get_user


print("TEST 1: SAFE QUERY")

validate_sql(
    'SELECT "Artist"."Name" FROM "Artist" LIMIT 5',
    get_demo_db().schema, get_demo_db().dialect
)

print("PASS")


print("\nTEST 2: UNKNOWN COLUMN")

try:

    validate_sql(
        'SELECT "Artist"."WrongColumn" FROM "Artist"',
        get_demo_db().schema, get_demo_db().dialect
    )

except ValueError as e:

    print("PASS:", e)


print("\nTEST 3: UNKNOWN TABLE")

try:

    validate_sql(
        'SELECT "Artist"."Name" FROM "Artists"',
        get_demo_db().schema, get_demo_db().dialect
    )

except ValueError as e:

    print("PASS:", e)


print("\nTEST 4: UNSAFE QUERY")

try:

    validate_sql(
        'DROP TABLE "Artist"',
        get_demo_db().schema, get_demo_db().dialect
    )

except ValueError as e:

    print("PASS:", e)
