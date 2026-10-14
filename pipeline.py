import os
from concurrent.futures import ThreadPoolExecutor

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

from schema_answer import (
    answer_schema_question
)


MAX_SQL_RETRIES = 2


# بعد التصنيف (DATABASE)، تلات مراحل تحليل بتاخد نفس السؤال ومش
# بتعتمد على بعض: فحص الوضوح، وتفكيك الأسئلة، وفحص توفّر الداتا. بدل ما
# نستناهم واحدة ورا التانية، بنشغّلهم مع بعض (نفس الـ prompts ونفس
# المدخلات، فالنتايج بالظبط زي الترتيب القديم). PARALLEL_ANALYSIS=false
# بيرجّعهم متتابعين (للتشخيص أو لو الـ rate limit ضيّق).
PARALLEL_ANALYSIS = (
    os.getenv("PARALLEL_ANALYSIS", "true").strip().lower()
    not in ("0", "false", "no", "off")
)


def _run_analysis_stages(tasks: dict) -> dict:
    """
    tasks: { name: دالة من غير arguments }.
    بترجّع { name: (True, النتيجة) | (False, الـ Exception) }.

    الاستثناء بيتحفظ ومش بيتفجّر هنا: ممكن تكون مرحلة فشلت وإحنا أصلًا
    مش محتاجين نتيجتها (مثلًا السؤال طلع غامض فهنسأل توضيح). الـ
    Exception بيتفجّر بس لما نحتاج النتيجة (_need).
    """

    def capture(function):

        try:
            return True, function()
        except Exception as error:
            return False, error

    if not PARALLEL_ANALYSIS:

        return {
            name: capture(function)
            for name, function in tasks.items()
        }

    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:

        futures = {
            name: pool.submit(capture, function)
            for name, function in tasks.items()
        }

        return {
            name: future.result()
            for name, future in futures.items()
        }


def _need(results: dict, name: str):

    succeeded, value = results[name]

    if not succeeded:
        raise value

    return value


# بنضيفها لسؤال الـ SQL بس (مش للرد ولا للتاريخ) لما نكون سألنا
# توضيح قبل كده ولسه الطلب مش محدد: نختار أنسب تفسير ونجاوب.
ASSUMPTION_NOTE = (
    "\n\n(Note: the request is not fully specific. Do NOT ask for "
    "clarification. Choose the most reasonable interpretation and "
    "write ONE query for it.)"
)


def _last_assistant_was_clarification(
    conversation_history: list
) -> bool:
    """
    جولة التوضيح مسموحة مرة واحدة: لو آخر رد من الـ assistant كان
    سؤال توضيح، فالرسالة الحالية هي الرد عليه، وأي غموض متبقي
    بنحله بافتراض معقول بدل ما نسأل تاني.
    """

    for message in reversed(conversation_history):

        if message.get("role") == "assistant":

            return message.get("type") == "clarification"

    return False


# ============================================================
# Static responses
# ============================================================

def _example_entities(db) -> list:
    """
    أمثلة للجداول في ردود "السؤال مش مرتبط". الداتابيز التجريبية
    بتحافظ على الأمثلة القديمة، والمخصصة بتاخد أول جداولها.
    """

    if db.is_demo:

        return [
            "customers",
            "artists",
            "albums",
            "tracks"
        ]

    return list(db.schema.keys())[:4]


def _join_examples(
    examples: list,
    language: str
) -> str:

    if language in ("arabic", "mixed"):

        return " أو ".join(examples)

    if len(examples) > 1:

        return (
            ", ".join(examples[:-1])
            + ", or "
            + examples[-1]
        )

    return "".join(examples)


def get_greeting_response(
    language: str,
    db
):

    name = db.display_name

    if language == "arabic":

        return (
            "أهلاً! أقدر أساعدك في "
            f"الاستعلام عن بيانات {name}."
        )

    if language == "mixed":

        return (
            "أهلاً! أقدر أساعدك في "
            f"الـ {name} database."
        )

    return (
        "Hello! I can help you "
        f"query the {name} database."
    )


def get_unrelated_response(
    language: str,
    db
):

    name = db.display_name

    examples = _join_examples(
        _example_entities(db),
        language
    )

    if language == "arabic":

        return (
            "السؤال ده مش مرتبط ببيانات "
            f"{name} database، لكن أقدر أساعدك "
            "في عرض أو تحليل البيانات الموجودة "
            "في الـ database، زي "
            f"{examples}."
        )

    if language == "mixed":

        return (
            f"السؤال ده مش مرتبط بالـ {name} database، "
            "لكن أقدر أساعدك في عرض أو تحليل البيانات "
            f"الموجودة، زي {examples}."
        )

    return (
        "This question is not related to the "
        f"{name} database, but I can help you "
        "explore or analyze the available data, "
        f"such as {examples}."
    )


def get_unavailable_response(
    missing_items: list,
    language: str,
    db
):

    name = db.display_name

    missing_text = ", ".join(
        missing_items
    )

    if language == "arabic":

        return (
            "المعلومة المطلوبة غير متاحة في "
            f"الـ {name} database: {missing_text}."
        )

    if language == "mixed":

        return (
            "المعلومة المطلوبة مش موجودة في "
            f"الـ {name} database: {missing_text}."
        )

    return (
        "The requested information is not available "
        f"in the {name} database: {missing_text}."
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


# ============================================================
# Database queries
# ============================================================

def run_database_query(
    user_question: str,
    model_name: str,
    user: dict,
    db,
    assume: bool = False
):

    if assume:

        user_question = user_question + ASSUMPTION_NOTE

    sql_query = generate_sql(
        user_question=user_question,
        db=db,
        model_name=model_name
    )

    for attempt in range(
        MAX_SQL_RETRIES + 1
    ):

        try:

            validate_sql(
                sql_query,
                db.schema,
                db.dialect
            )

            resolved_sql, corrections = (
                resolve_sql_values(
                    db,
                    sql_query
                )
            )

            validate_sql(
                resolved_sql,
                db.schema,
                db.dialect
            )

            # execute_sql بترجّع 4 قيم: columns, rows,
            # real_total, restricted_fields
            columns, rows, real_total, restricted_fields = (
                execute_sql(
                    query=resolved_sql,
                    user=user,
                    db=db
                )
            )

            return (
                resolved_sql,
                columns,
                rows,
                real_total,
                restricted_fields
            )

        except PermissionError:

            raise

        except Exception as error:

            if attempt >= MAX_SQL_RETRIES:

                # آخر SQL اتحاول بيتضاف للرسالة عشان نعرف نشخّص
                raise RuntimeError(
                    "SQL generation/execution failed after "
                    f"{MAX_SQL_RETRIES} retries. "
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


def run_multiple_database_queries(
    user_question: str,
    questions: list,
    model_name: str,
    user: dict,
    db,
    assume: bool = False
):

    question_results = []

    for question in questions:

        data_availability = (
            analyze_data_availability(
                user_question=question,
                db=db,
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
                    "real_total": 0,
                    "restricted_fields": []
                }
            )

            continue

        try:

            (
                sql_query,
                columns,
                rows,
                real_total,
                restricted_fields
            ) = run_database_query(
                user_question=question,
                model_name=model_name,
                user=user,
                db=db,
                assume=assume
            )

            question_results.append(
                {
                    "question": question,
                    "status": "AVAILABLE",
                    "missing_items": [],
                    "sql": sql_query,
                    "columns": list(columns),
                    "rows": rows,
                    "real_total": real_total,
                    "restricted_fields": restricted_fields
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
                    "real_total": 0,
                    "restricted_fields": []
                }
            )

    answer = generate_multiple_answer(
        user_question=user_question,
        question_results=question_results,
        model_name=model_name,
        db_name=db.display_name
    )

    return (
        answer,
        question_results
    )


# ============================================================
# Main pipeline
# ============================================================

def run_pipeline(
    user_question: str,
    model_name: str = "nano",
    conversation_history: list = None,
    user: dict = None,
    *,
    db
):
    """
    db: DBContext بتاع الـ Session (keyword-only وإجباري، عشان أي
    استدعاء قديم من غيره يفشل بوضوح بدل ما يشتغل غلط).
    """

    if db is None:

        raise ValueError(
            "A database connection (db) is required."
        )

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
        db=db,
        model_name=model_name
    )

    classification = classify_question(
        user_question=resolved_question,
        db=db,
        model_name=model_name
    )

    if classification == "GREETING":

        language = detect_language(
            user_question
        )

        return {
            "type": "greeting",
            "answer": get_greeting_response(
                language,
                db
            )
        }

    if classification == "UNRELATED":

        language = detect_language(
            user_question
        )

        return {
            "type": "unrelated",
            "answer": get_unrelated_response(
                language,
                db
            )
        }

    if classification == "DISCOVERY":

        return {
            "type": "discovery",
            "answer": answer_schema_question(
                user_question=resolved_question,
                db=db,
                user=user,
                model_name=model_name,
                language_hint=user_question
            ),
            "resolved_question": resolved_question
        }

    analysis = _run_analysis_stages(
        {
            "input": lambda: analyze_input(
                user_question=resolved_question,
                db=db,
                model_name=model_name
            ),
            "multiple": lambda: analyze_multiple_questions(
                user_question=resolved_question,
                model_name=model_name,
                db_name=db.display_name
            ),
            "availability": lambda: analyze_data_availability(
                user_question=resolved_question,
                db=db,
                model_name=model_name
            ),
        }
    )

    input_status = _need(analysis, "input")

    assume = False

    if input_status == "AMBIGUOUS":

        if _last_assistant_was_clarification(
            conversation_history
        ):

            # سألنا توضيح قبل كده: مفيش جولة تانية. نجاوب بأنسب تفسير
            # ونقول للمستخدم إحنا افترضنا إيه.
            assume = True

        else:

            clarification = generate_clarification(
                user_question=resolved_question,
                db=db,
                user=user,
                model_name=model_name
            )

            return {
                "type": "clarification",
                "answer": clarification,
                "resolved_question": resolved_question
            }

    multiple_analysis = _need(analysis, "multiple")

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
                user=user,
                db=db,
                assume=assume
            )
        )

        return {
            "type": "multiple",
            "answer": answer,
            "questions": questions,
            "results": question_results,
            "resolved_question": resolved_question
        }

    data_availability = _need(analysis, "availability")

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
            language=language,
            db=db
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

    # --------------------------------------------------------
    # PermissionError هنا معناها رفض كامل (عمود ممنوع في WHERE
    # مثلاً، أو صف كامل، أو كل الأعمدة المطلوبة ممنوعة). الرفض
    # الجزئي بيرجع كنتيجة عادية فيها restricted_fields.
    # --------------------------------------------------------

    try:

        (
            sql_query,
            columns,
            rows,
            real_total,
            restricted_fields
        ) = run_database_query(
            user_question=resolved_question,
            model_name=model_name,
            user=user,
            db=db,
            assume=assume
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
        restricted_fields=restricted_fields,
        model_name=model_name,
        db_name=db.display_name,
        assumed=assume
    )

    return {
        "type": "database",
        "answer": answer,
        "sql": sql_query,
        "columns": list(columns),
        "rows": rows,
        "real_total": real_total,
        "restricted_fields": restricted_fields,
        "resolved_question": resolved_question
    }