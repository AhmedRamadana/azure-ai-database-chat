from classifier import (
    classify_question
)

from input_analyzer import (
    analyze_input
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

from clarification_generator import (
    generate_clarification
)

from language_utils import (
    detect_language
)

from context_resolver import (
    resolve_context
)

from value_resolver import (
    resolve_sql_values
)

from multiple_question_analyzer import (
    analyze_multiple_questions
)

from multiple_answer_generator import (
    generate_multiple_answer
)

from data_discovery import (
    analyze_data_availability
)

from auth.mock_auth import (
    get_mock_user
)


MAX_SQL_RETRIES = 2


def get_greeting_response(
    language: str
):

    if language == "arabic":

        return (
            "أهلاً! أقدر أساعدك في "
            "الاستعلام عن بيانات Chinook."
        )

    if language == "mixed":

        return (
            "أهلاً! أقدر أساعدك في "
            "الـ Chinook database."
        )

    return (
        "Hello! I can help you "
        "query the Chinook database."
    )


def get_unrelated_response(
    language: str
):

    if language == "arabic":

        return (
            "السؤال ده مش مرتبط ببيانات "
            "Chinook database، لكن أقدر أساعدك "
            "في عرض أو تحليل البيانات الموجودة "
            "في الـ database، زي customers أو "
            "artists أو albums أو tracks."
        )

    if language == "mixed":

        return (
            "السؤال ده مش مرتبط بالـ Chinook database، "
            "لكن أقدر أساعدك في عرض أو تحليل البيانات "
            "الموجودة، زي customers أو artists أو albums أو tracks."
        )

    return (
        "This question is not related to the "
        "Chinook database, but I can help you "
        "explore or analyze the available data, "
        "such as customers, artists, albums, or tracks."
    )


def get_unavailable_response(
    missing_items: list,
    language: str
):

    missing_text = ", ".join(
        missing_items
    )

    if language == "arabic":

        return (
            "المعلومة المطلوبة غير متاحة في "
            f"الـ Chinook database: {missing_text}."
        )

    if language == "mixed":

        return (
            "المعلومة المطلوبة مش موجودة في "
            f"الـ Chinook database: {missing_text}."
        )

    return (
        "The requested information is not available "
        f"in the Chinook database: {missing_text}."
    )


def get_access_denied_response(
    language: str
):

    if language == "arabic":

        return (
            "عذرًا، ليس لديك صلاحية للوصول "
            "إلى البيانات المطلوبة."
        )

    if language == "mixed":

        return (
            "Sorry, you don't have permission "
            "to access the requested data."
        )

    return (
        "Sorry, you don't have permission "
        "to access the requested data."
    )


def run_database_query(
    user_question: str,
    model_name: str,
    user: dict
):

    sql_query = generate_sql(
        user_question=user_question,
        model_name=model_name
    )

    for attempt in range(
        MAX_SQL_RETRIES + 1
    ):

        try:

            validate_sql(
                sql_query
            )

            resolved_sql, corrections = (
                resolve_sql_values(
                    sql_query
                )
            )

            validate_sql(
                resolved_sql
            )

            # execute_sql بقت ترجّع 3 قيم بدل 2:
            # columns, rows, real_total
            columns, rows, real_total = execute_sql(
                query=resolved_sql,
                user=user
            )

            return (
                resolved_sql,
                columns,
                rows,
                real_total
            )

        except PermissionError:

            raise

        except Exception as error:

            if attempt >= MAX_SQL_RETRIES:

                raise RuntimeError(
                    "SQL generation/execution failed after "
                    f"{MAX_SQL_RETRIES} retries. "
                    f"Last error: {error}"
                )

            sql_query = correct_sql(
                user_question=user_question,
                previous_sql=sql_query,
                error_message=str(error),
                model_name=model_name
            )


def run_multiple_database_queries(
    user_question: str,
    questions: list,
    model_name: str,
    user: dict
):

    question_results = []

    for question in questions:

        data_availability = (
            analyze_data_availability(
                user_question=question,
                model_name=model_name
            )
        )

        if data_availability["status"] == "UNAVAILABLE":

            question_results.append(
                {
                    "question": question,
                    "status": "UNAVAILABLE",
                    "missing_items": (
                        data_availability[
                            "missing_items"
                        ]
                    ),
                    "sql": None,
                    "columns": [],
                    "rows": [],
                    "real_total": 0
                }
            )

            continue

        try:

            sql_query, columns, rows, real_total = (
                run_database_query(
                    user_question=question,
                    model_name=model_name,
                    user=user
                )
            )

            question_results.append(
                {
                    "question": question,
                    "status": "AVAILABLE",
                    "missing_items": [],
                    "sql": sql_query,
                    "columns": list(columns),
                    "rows": rows,
                    "real_total": real_total
                }
            )

        except PermissionError:

            question_results.append(
                {
                    "question": question,
                    "status": "UNAUTHORIZED",
                    "missing_items": [],
                    "sql": None,
                    "columns": [],
                    "rows": [],
                    "real_total": 0
                }
            )

    answer = generate_multiple_answer(
        user_question=user_question,
        question_results=question_results,
        model_name=model_name
    )

    return (
        answer,
        question_results
    )


def run_pipeline(
    user_question: str,
    model_name: str = "nano",
    conversation_history: list = None,
    user: dict = None
):

    if conversation_history is None:

        conversation_history = []

    if user is None:

        user = get_mock_user(
            user_id="user_001",
            role="USER"
        )

    resolved_question = resolve_context(
        current_question=user_question,
        conversation_history=conversation_history,
        model_name=model_name
    )

    classification = classify_question(
        user_question=resolved_question,
        model_name=model_name
    )

    if classification == "GREETING":

        language = detect_language(
            user_question
        )

        return {
            "type": "greeting",
            "answer": get_greeting_response(
                language
            )
        }

    if classification == "UNRELATED":

        language = detect_language(
            user_question
        )

        return {
            "type": "unrelated",
            "answer": get_unrelated_response(
                language
            )
        }

    input_status = analyze_input(
        user_question=resolved_question,
        model_name=model_name
    )

    if input_status == "AMBIGUOUS":

        clarification = generate_clarification(
            user_question=resolved_question,
            model_name=model_name
        )

        return {
            "type": "clarification",
            "answer": clarification
        }

    multiple_analysis = (
        analyze_multiple_questions(
            user_question=resolved_question,
            model_name=model_name
        )
    )

    question_type = multiple_analysis[
        "type"
    ]

    questions = multiple_analysis[
        "questions"
    ]

    if question_type == "MULTIPLE":

        answer, question_results = (
            run_multiple_database_queries(
                user_question=resolved_question,
                questions=questions,
                model_name=model_name,
                user=user
            )
        )

        return {
            "type": "multiple",
            "answer": answer,
            "questions": questions,
            "results": question_results,
            "resolved_question": resolved_question
        }

    data_availability = (
        analyze_data_availability(
            user_question=resolved_question,
            model_name=model_name
        )
    )

    if data_availability["status"] == "UNAVAILABLE":

        language = detect_language(
            user_question
        )

        answer = get_unavailable_response(
            missing_items=(
                data_availability[
                    "missing_items"
                ]
            ),
            language=language
        )

        return {
            "type": "unavailable",
            "answer": answer,
            "missing_items": (
                data_availability[
                    "missing_items"
                ]
            ),
            "resolved_question": resolved_question
        }

    try:

        sql_query, columns, rows, real_total = (
            run_database_query(
                user_question=resolved_question,
                model_name=model_name,
                user=user
            )
        )

    except PermissionError:

        language = detect_language(
            user_question
        )

        return {
            "type": "unauthorized",
            "answer": get_access_denied_response(
                language
            ),
            "resolved_question": resolved_question
        }

    answer = generate_answer(
        user_question=resolved_question,
        sql_query=sql_query,
        columns=columns,
        rows=rows,
        real_total=real_total,
        model_name=model_name
    )

    return {
        "type": "database",
        "answer": answer,
        "sql": sql_query,
        "columns": list(columns),
        "rows": rows,
        "real_total": real_total,
        "resolved_question": resolved_question
    }