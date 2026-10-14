from schema import (
    format_schema_for_llm
)

from prompts.sql_prompt import (
    build_sql_prompt
)

from prompts.sql_prompt_generic import (
    build_generic_sql_prompt
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


def _build_prompt(
    user_question: str,
    db
) -> str:
    """
    الداتابيز التجريبية (Chinook) بتستخدم الـ Prompt الأصلي المضبوط
    (قواعد الـ JOIN والـ financial logic الخاصة بيها). أي داتابيز
    تانية بتستخدم Prompt عام من غير أي افتراضات عن Chinook.
    """

    schema_context = format_schema_for_llm(
        db.schema
    )

    if db.is_demo:

        return build_sql_prompt(
            user_question,
            schema_context
        )

    return build_generic_sql_prompt(
        user_question,
        schema_context,
        db.display_name,
        dialect_name=db.dialect.prompt_name,
        dialect_rules=db.dialect.prompt_rules
    )


def generate_sql(
    user_question: str,
    db,
    model_name: str = "nano"
):

    prompt = _build_prompt(
        user_question,
        db
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
                sql_query,
                db.schema,
                db.dialect
            )

            return sql_query

        except Exception as error:

            if attempt >= MAX_SQL_CORRECTION_RETRIES:

                raise RuntimeError(
                    "SQL generation failed after "
                    f"{MAX_SQL_CORRECTION_RETRIES} "
                    "correction retries. "
                    f"Last error: {error}. "
                    f"Last SQL: {sql_query}"
                )

            sql_query = correct_sql(
                user_question=user_question,
                previous_sql=sql_query,
                error_message=str(error),
                db=db,
                model_name=model_name
            )


def correct_sql(
    user_question: str,
    previous_sql: str,
    error_message: str,
    db,
    model_name: str = "nano"
):

    schema_context = format_schema_for_llm(
        db.schema
    )

    prompt = build_sql_correction_prompt(
        user_question=user_question,
        previous_sql=previous_sql,
        error_message=error_message,
        schema_context=schema_context,
        db_name=db.display_name,
        dialect_name=db.dialect.prompt_name,
        dialect_rules=db.dialect.prompt_rules
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