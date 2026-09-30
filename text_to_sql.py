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


MAX_SQL_CORRECTION_RETRIES = 2


def generate_sql(
    user_question: str,
    model_name: str = "nano"
):

    schema = get_database_schema()

    schema_context = format_schema_for_llm(
        schema
    )

    prompt = build_sql_prompt(
        user_question,
        schema_context
    )

    model = get_model(
        model_name
    )

    response = model(
        prompt
    )

    response = response.strip()

    sql_query = clean_sql(
        response
    )

    # --------------------------------------------------
    # Validate generated SQL
    # --------------------------------------------------

    for attempt in range(
        MAX_SQL_CORRECTION_RETRIES + 1
    ):

        try:

            validate_sql(
                sql_query
            )

            return sql_query

        except Exception as error:

            if attempt >= MAX_SQL_CORRECTION_RETRIES:

                raise RuntimeError(
                    "SQL generation failed after "
                    f"{MAX_SQL_CORRECTION_RETRIES} "
                    "correction retries. "
                    f"Last error: {error}"
                )

            sql_query = correct_sql(
                user_question=user_question,
                previous_sql=sql_query,
                error_message=str(error),
                model_name=model_name
            )


def correct_sql(
    user_question: str,
    previous_sql: str,
    error_message: str,
    model_name: str = "nano"
):

    schema = get_database_schema()

    schema_context = format_schema_for_llm(
        schema
    )

    prompt = build_sql_correction_prompt(
        user_question=user_question,
        previous_sql=previous_sql,
        error_message=error_message,
        schema_context=schema_context
    )

    model = get_model(
        model_name
    )

    response = model(
        prompt
    )

    response = response.strip()

    corrected_sql = clean_sql(
        response
    )

    return corrected_sql
