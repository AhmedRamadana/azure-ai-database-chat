from schema import format_schema_for_llm
from tests.helpers import get_demo_db, get_user

from prompts.sql_prompt import build_sql_prompt


schema = get_demo_db().schema

schema_context = format_schema_for_llm(
    schema
)


question = "How many customers are there?"


prompt = build_sql_prompt(
    question,
    schema_context
)

print(prompt)