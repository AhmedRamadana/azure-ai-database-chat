from schema import get_database_schema


schema = get_database_schema()


for table_name, table_info in schema.items():

    print(f"\n{'=' * 50}")
    print(f"Table: {table_name}")

    print("\nColumns:")

    for column in table_info["columns"]:

        print(
            f"  - {column['name']} "
            f"({column['type']})"
        )

    print("\nForeign Keys:")

    for foreign_key in table_info["foreign_keys"]:

        print(
            f"  - {foreign_key['column']} "
            f"→ "
            f"{foreign_key['references_table']}."
            f"{foreign_key['references_column']}"
        )