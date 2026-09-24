from classifier import (
    classify_question
)

from text_to_sql import (
    generate_sql,
    correct_sql
)

from sql_executor import (
    execute_sql
)

from sql_validator import (
    validate_sql
)

from answer_generator import (
    generate_answer
)


# Maximum number of SQL correction attempts
MAX_SQL_RETRIES = 2


def run_database_query(
    user_question: str,
    model_name: str
):

    # -----------------------------------------
    # 1. Generate initial SQL
    # -----------------------------------------

    sql_query = generate_sql(
        user_question=user_question,
        model_name=model_name
    )

    # -----------------------------------------
    # 2. Try to validate and execute SQL
    # -----------------------------------------

    for attempt in range(
        MAX_SQL_RETRIES + 1
    ):

        try:

            # Validate SQL
            validate_sql(
                sql_query
            )

            # Execute SQL
            columns, rows = execute_sql(
                sql_query
            )

            # If everything succeeds
            # return the result
            return (
                sql_query,
                columns,
                rows
            )

        except Exception as error:

            # ---------------------------------
            # 3. Check retry limit
            # ---------------------------------

            if attempt >= MAX_SQL_RETRIES:

                raise RuntimeError(
                    "SQL generation failed after "
                    f"{MAX_SQL_RETRIES} retries. "
                    f"Last error: {error}"
                )

            # ---------------------------------
            # 4. Ask LLM to correct SQL
            # ---------------------------------

            sql_query = correct_sql(
                user_question=user_question,
                previous_sql=sql_query,
                error_message=str(error),
                model_name=model_name
            )


def run_pipeline(
    user_question: str,
    model_name: str = "nano"
):

    # -----------------------------------------
    # 1. Classify user question
    # -----------------------------------------

    classification = classify_question(
        user_question=user_question,
        model_name=model_name
    )

    # -----------------------------------------
    # 2. Greeting
    # -----------------------------------------

    if classification == "GREETING":

        return {
            "type": "greeting",
            "answer": (
                "Hello! How can I help you "
                "with the Chinook database?"
            )
        }

    # -----------------------------------------
    # 3. Unrelated question
    # -----------------------------------------

    if classification == "UNRELATED":

        return {
            "type": "unrelated",
            "answer": (
                "This question is not related "
                "to the Chinook database. "
                "Please ask me something about "
                "the available database data."
            )
        }

    # -----------------------------------------
    # 4. Database question
    # -----------------------------------------

    sql_query, columns, rows = run_database_query(
        user_question=user_question,
        model_name=model_name
    )

    # -----------------------------------------
    # 5. Generate natural-language answer
    # -----------------------------------------

    answer = generate_answer(
        user_question=user_question,
        sql_query=sql_query,
        columns=columns,
        rows=rows,
        model_name=model_name
    )

    # -----------------------------------------
    # 6. Return final result
    # -----------------------------------------

    return {
        "type": "database",
        "answer": answer,
        "sql": sql_query,
        "columns": list(columns),
        "rows": rows
    }
