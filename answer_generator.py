from prompts.answer_prompt import build_answer_prompt
from models.model_manager import get_model
from language_utils import detect_language


LLM_SAMPLE_SIZE = 15


def generate_answer(
    user_question: str,
    sql_query: str,
    columns,
    rows,
    real_total: int,
    restricted_fields: list,
    model_name: str = "nano"
):

    language = detect_language(
        user_question
    )

    if real_total > LLM_SAMPLE_SIZE:

        rows_for_llm = rows[:LLM_SAMPLE_SIZE]

    else:

        rows_for_llm = rows

    prompt = build_answer_prompt(
        user_question=user_question,
        sql_query=sql_query,
        columns=columns,
        rows=rows_for_llm,
        real_total=real_total,
        restricted_fields=restricted_fields,
        language=language
    )

    model = get_model(
        model_name
    )

    response = model(
        prompt
    )

    return response.strip()