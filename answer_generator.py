from prompts.answer_prompt import build_answer_prompt
from models.model_manager import get_model


def generate_answer(
    user_question: str,
    sql_query: str,
    columns,
    rows,
    model_name: str = "nano"
):

    prompt = build_answer_prompt(
        user_question=user_question,
        sql_query=sql_query,
        columns=columns,
        rows=rows
    )

    model = get_model(model_name)

    response = model(prompt)

    return response.strip()