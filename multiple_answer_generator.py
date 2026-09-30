from prompts.multiple_answer_prompt import (
    build_multiple_answer_prompt
)

from models.model_manager import (
    get_model
)

from language_utils import (
    detect_language
)


def generate_multiple_answer(
    user_question: str,
    question_results,
    model_name: str = "nano"
):

    language = detect_language(
        user_question
    )

    prompt = build_multiple_answer_prompt(
        user_question=user_question,
        question_results=question_results,
        language=language
    )

    model = get_model(
        model_name
    )

    response = model(
        prompt
    )

    return response.strip()