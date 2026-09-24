from sql_validator import (
    clean_sql,
    validate_sql
)


queries = [

    'SELECT COUNT(*) FROM "Customer";',

    '''
    ```sql
    SELECT COUNT(*)
    FROM "Customer";
    ```
    ''',

    'DROP TABLE "Customer";'

]


for query in queries:

    print("\nOriginal:")
    print(query)

    try:

        cleaned_query = clean_sql(query)

        validate_sql(cleaned_query)

        print("Result: SAFE")
        print("Cleaned SQL:")
        print(cleaned_query)

    except ValueError as e:

        print("Result: REJECTED")
        print(e)