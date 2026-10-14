import time
from tests.helpers import get_demo_db, get_user

from schema import format_schema_for_llm

from prompts.sql_prompt import build_sql_prompt

from models.model_manager import get_model

from sql_validator import clean_sql
from sql_validator import validate_sql


user_question = "How many artists are there?"

print("\n--- SQL Generation Profiling ---")


start = time.perf_counter()

schema = get_demo_db().schema

end = time.perf_counter()

print(
    f"Schema loading: "
    f"{end - start:.3f} seconds"
)


start = time.perf_counter()

schema_context = format_schema_for_llm(
    schema
)

end = time.perf_counter()

print(
    f"Schema formatting: "
    f"{end - start:.3f} seconds"
)


start = time.perf_counter()

prompt = build_sql_prompt(
    user_question,
    schema_context
)

end = time.perf_counter()

print(
    f"Prompt building: "
    f"{end - start:.3f} seconds"
)


start = time.perf_counter()

model = get_model("mini")

end = time.perf_counter()

print(
    f"Model loading: "
    f"{end - start:.3f} seconds"
)


start = time.perf_counter()

response = model(prompt)

end = time.perf_counter()

print(
    f"Azure model response: "
    f"{end - start:.3f} seconds"
)


start = time.perf_counter()

sql_query = clean_sql(
    response.strip()
)

validate_sql(
    sql_query,
    get_demo_db().schema, get_demo_db().dialect
)

end = time.perf_counter()

print(
    f"SQL cleaning + validation: "
    f"{end - start:.3f} seconds"
)


print("\nGenerated SQL:")
print(sql_query)
