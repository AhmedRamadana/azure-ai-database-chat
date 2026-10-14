from schema import format_schema_for_llm
from tests.helpers import get_demo_db, get_user


schema = get_demo_db().schema

schema_context = format_schema_for_llm(
    schema
)

print(schema_context)