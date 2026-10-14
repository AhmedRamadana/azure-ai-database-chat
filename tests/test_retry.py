from text_to_sql import correct_sql
from tests.helpers import get_demo_db, get_user
from sql_validator import validate_sql


user_question = "How many artists are there?"

bad_sql = """
SELECT COUNT("ArtistId")
FROM "Artists";
"""

error_message = (
    "Unknown table: Artists"
)


print("BAD SQL:")
print(bad_sql)


print("\nCORRECTING SQL...\n")


corrected_sql = correct_sql(
    user_question=user_question,
    previous_sql=bad_sql,
    error_message=error_message,
    model_name="mini",
    db=get_demo_db()
)


print("CORRECTED SQL:")
print(corrected_sql)


print("\nVALIDATING CORRECTED SQL...\n")


validate_sql(
    corrected_sql,
    get_demo_db().schema, get_demo_db().dialect
)


print("RETRY TEST: PASS")
