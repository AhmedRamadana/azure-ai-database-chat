from schema import (
    get_database_schema,
    format_schema_for_llm
)

from prompts.sql_prompt import (
    build_sql_prompt
)

from prompts.sql_correction_prompt import (
    build_sql_correction_prompt
)

from models.model_manager import (
    get_model
)

from sql_validator import (
    clean_sql,
    validate_sql
)


def generate_sql(
    user_question: str,
    model_name: str = "nano"
):

    # -----------------------------------------
    # 1. Get database schema
    # -----------------------------------------

    schema = get_database_schema()

    schema_context = format_schema_for_llm(
        schema
    )

    # -----------------------------------------
    # 2. Build SQL generation prompt
    # -----------------------------------------

    prompt = build_sql_prompt(
        user_question,
        schema_context
    )

    # -----------------------------------------
    # 3. Select model
    # -----------------------------------------

    model = get_model(
        model_name
    )

    # -----------------------------------------
    # 4. Generate SQL
    # -----------------------------------------

    response = model(
        prompt
    )

    response = response.strip()

    # -----------------------------------------
    # 5. Clean generated SQL
    # -----------------------------------------

    sql_query = clean_sql(
        response
    )

    # -----------------------------------------
    # 6. Validate generated SQL
    # -----------------------------------------

    validate_sql(
        sql_query
    )

    return sql_query


def correct_sql(
    user_question: str,
    previous_sql: str,
    error_message: str,
    model_name: str = "nano"
):

    # -----------------------------------------
    # 1. Get database schema
    # -----------------------------------------

    schema = get_database_schema()

    schema_context = format_schema_for_llm(
        schema
    )

    # -----------------------------------------
    # 2. Build correction prompt
    # -----------------------------------------

    prompt = build_sql_correction_prompt(
        user_question=user_question,
        previous_sql=previous_sql,
        error_message=error_message,
        schema_context=schema_context
    )

    # -----------------------------------------
    # 3. Select model
    # -----------------------------------------

    model = get_model(
        model_name
    )

    # -----------------------------------------
    # 4. Generate corrected SQL
    # -----------------------------------------

    response = model(
        prompt
    )

    response = response.strip()

    # -----------------------------------------
    # 5. Clean corrected SQL
    # -----------------------------------------

    corrected_sql = clean_sql(
        response
    )

    # -----------------------------------------
    # 6. Validate corrected SQL
    # -----------------------------------------

    validate_sql(
        corrected_sql
    )

    return corrected_sql
