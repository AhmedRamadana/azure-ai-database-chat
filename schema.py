from functools import lru_cache

from database import engine
from sqlalchemy import inspect


@lru_cache(maxsize=1)
def get_database_schema():

    inspector = inspect(engine)

    schema = {}

    tables = inspector.get_table_names()

    for table in tables:

        columns = inspector.get_columns(table)

        foreign_keys = inspector.get_foreign_keys(table)

        schema[table] = {
            "columns": [
                {
                    "name": column["name"],
                    "type": str(column["type"])
                }
                for column in columns
            ],
            "foreign_keys": [
                {
                    "column": fk["constrained_columns"],
                    "references_table": fk["referred_table"],
                    "references_column": fk["referred_columns"]
                }
                for fk in foreign_keys
            ]
        }

    return schema


def format_schema_for_llm(schema):

    lines = []

    lines.append("DATABASE SCHEMA")
    lines.append("================")

    for table_name, table_info in schema.items():

        lines.append(
            f"\nTABLE: {table_name}"
        )

        lines.append("COLUMNS:")

        for column in table_info["columns"]:

            lines.append(
                f"- {column['name']}: "
                f"{column['type']}"
            )

        foreign_keys = table_info["foreign_keys"]

        if foreign_keys:

            lines.append("FOREIGN KEYS:")

            for foreign_key in foreign_keys:

                columns = ", ".join(
                    foreign_key["column"]
                )

                references_columns = ", ".join(
                    foreign_key["references_column"]
                )

                lines.append(
                    f"- {table_name}.{columns} "
                    f"→ "
                    f"{foreign_key['references_table']}."
                    f"{references_columns}"
                )

    return "\n".join(lines)
