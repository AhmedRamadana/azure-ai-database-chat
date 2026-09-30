from database import execute_query


queries = {

    "countries": """
        SELECT DISTINCT "Country"
        FROM "Customer"
        ORDER BY "Country";
    """,

    "artists": """
        SELECT "Name"
        FROM "Artist"
        ORDER BY "Name";
    """
}


for name, query in queries.items():

    print("\n" + "=" * 70)
    print(name.upper())
    print("=" * 70)

    try:

        columns, rows = execute_query(query)

        print("COLUMNS:")
        print(list(columns))

        print("\nROWS:")

        for row in rows:
            print(row)

    except Exception as e:

        print("\nERROR:")
        print(e)