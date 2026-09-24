from sql_validator import validate_sql


print("TEST 1: SAFE QUERY")

validate_sql(
    'SELECT "Artist"."Name" FROM "Artist" LIMIT 5'
)

print("PASS")


print("\nTEST 2: UNKNOWN COLUMN")

try:

    validate_sql(
        'SELECT "Artist"."WrongColumn" FROM "Artist"'
    )

except ValueError as e:

    print("PASS:", e)


print("\nTEST 3: UNKNOWN TABLE")

try:

    validate_sql(
        'SELECT "Artist"."Name" FROM "Artists"'
    )

except ValueError as e:

    print("PASS:", e)


print("\nTEST 4: UNSAFE QUERY")

try:

    validate_sql(
        'DROP TABLE "Artist"'
    )

except ValueError as e:

    print("PASS:", e)
