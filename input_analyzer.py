from prompts.input_analysis_prompt import (
    build_input_analysis_prompt
)

from models.model_manager import get_model


def analyze_input(
    user_question: str,
    model_name: str = "nano"
):

    prompt = build_input_analysis_prompt(
        user_question
    )

    model = get_model(
        model_name
    )

    response = model(
        prompt
    )

    response = response.strip().upper()

    if response not in [
        "CLEAR",
        "AMBIGUOUS"
    ]:

        raise ValueError(
            f"Invalid input analysis result: {response}"
        )

    return response