from prompts.clarification_prompt import (
    build_clarification_prompt
)

from models.model_manager import get_model


def generate_clarification(
    user_question: str,
    model_name: str = "nano"
):

    prompt = build_clarification_prompt(
        user_question
    )

    model = get_model(
        model_name
    )

    response = model(
        prompt
    )

    return response.strip()