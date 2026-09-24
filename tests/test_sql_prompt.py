from schema import (
    get_database_schema,
    format_schema_for_llm
)

from prompts.sql_prompt import build_sql_prompt


schema = get_database_schema()

schema_context = format_schema_for_llm(
    schema
)


question = "How many customers are there?"


prompt = build_sql_prompt(
    question,
    schema_context
)

print(prompt)