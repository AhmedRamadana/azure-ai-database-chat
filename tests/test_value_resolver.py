from value_resolver import (
    get_distinct_values,
    resolve_value,
    resolve_sql_values
)


print("\n" + "=" * 70)
print("DEBUG 1 — DATABASE VALUES")
print("=" * 70)


print("\nCustomer.Country values:")

try:

    countries = get_distinct_values(
        "Customer",
        "Country"
    )

    print(
        f"Number of countries: {len(countries)}"
    )

    print("\nFirst 10 values:")

    for value in countries[:10]:

        print(
            f"  {repr(value)} "
            f"| type={type(value)}"
        )

except Exception as e:

    print(f"ERROR: {e}")


print("\nArtist.Name values:")

try:

    artists = get_distinct_values(
        "Artist",
        "Name"
    )

    print(
        f"Number of artists: {len(artists)}"
    )

    print("\nFirst 10 values:")

    for value in artists[:10]:

        print(
            f"  {repr(value)} "
            f"| type={type(value)}"
        )

except Exception as e:

    print(f"ERROR: {e}")


print("\n" + "=" * 70)
print("DEBUG 2 — EXACT VALUE CHECK")
print("=" * 70)


try:

    countries = get_distinct_values(
        "Customer",
        "Country"
    )

    print(
        "\nBrazil exists:",
        "Brazil" in countries
    )

    print(
        "Germany exists:",
        "Germany" in countries
    )

except Exception as e:

    print(f"ERROR: {e}")


try:

    artists = get_distinct_values(
        "Artist",
        "Name"
    )

    print(
        "\nMetallica exists:",
        "Metallica" in artists
    )

    print(
        "Pink Floyd exists:",
        "Pink Floyd" in artists
    )

    print(
        "AC/DC exists:",
        "AC/DC" in artists
    )

except Exception as e:

    print(f"ERROR: {e}")


print("\n" + "=" * 70)
print("TEST 3 — DIRECT VALUE RESOLUTION")
print("=" * 70)


test_values = [

    ("Customer", "Country", "Brazil"),
    ("Customer", "Country", "Brazill"),
    ("Customer", "Country", "Caneda"),
    ("Customer", "Country", "Germeny"),
    ("Customer", "Country", "Egypt"),

    ("Artist", "Name", "Metallica"),
    ("Artist", "Name", "Metalllica"),
    ("Artist", "Name", "Pink Floyd"),
    ("Artist", "Name", "Pink Floid"),
    ("Artist", "Name", "AC/DC"),
    ("Artist", "Name", "AC DC"),
]


for table, column, value in test_values:

    print("\n" + "-" * 70)

    print(
        f"TABLE  : {table}"
    )

    print(
        f"COLUMN : {column}"
    )

    print(
        f"INPUT  : {value}"
    )

    try:

        result = resolve_value(
            table_name=table,
            column_name=column,
            user_value=value
        )

        print(
            "RESULT :",
            repr(result)
        )

    except Exception as e:

        print(
            "ERROR  :",
            repr(e)
        )


print("\n" + "=" * 70)
print("TEST 4 — SQL VALUE RESOLUTION")
print("=" * 70)


sql_tests = [

    """
    SELECT "Customer"."FirstName",
           "Customer"."LastName",
           "Customer"."Country"
    FROM "Customer"
    WHERE "Customer"."Country" = 'Brazill';
    """,

    """
    SELECT "Customer"."FirstName",
           "Customer"."LastName"
    FROM "Customer"
    WHERE "Customer"."Country" = 'Germeny';
    """,

    """
    SELECT "Artist"."Name"
    FROM "Artist"
    WHERE "Artist"."Name" = 'Pink Floid';
    """,

    """
    SELECT "Artist"."Name"
    FROM "Artist"
    WHERE "Artist"."Name" = 'Metalllica';
    """,

    """
    SELECT "Artist"."Name"
    FROM "Artist"
    WHERE "Artist"."Name" = 'AC DC';
    """
]


for i, sql in enumerate(
    sql_tests,
    start=1
):

    print("\n" + "-" * 70)

    print(
        f"SQL TEST {i}"
    )

    print("\nORIGINAL SQL:")

    print(
        sql.strip()
    )

    try:

        corrected_sql, corrections = (
            resolve_sql_values(sql)
        )

        print("\nCORRECTED SQL:")

        print(
            corrected_sql.strip()
        )

        print("\nCORRECTIONS:")

        print(
            corrections
        )

    except Exception as e:

        print(
            "\nERROR:",
            repr(e)
        )
