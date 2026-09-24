from schema import (
    get_database_schema,
    format_schema_for_llm
)


schema = get_database_schema()

schema_context = format_schema_for_llm(
    schema
)

print(schema_context)