from prompts.classification_prompt import (
    build_classification_prompt
)

from models.model_manager import get_model


def classify_question(
    user_question: str,
    model_name: str = "nano"
):

    prompt = build_classification_prompt(
        user_question
    )

    model = get_model(model_name)

    response = model(prompt)

    response = response.strip().upper()

    if response not in [
        "GREETING",
        "DATABASE",
        "UNRELATED"
    ]:

        raise ValueError(
            f"Invalid classification: {response}"
        )

    return response
