from prompts.input_analysis_prompt import (
    build_input_analysis_prompt
)

from schema import format_schema_summary

from models.model_manager import get_model


def analyze_input(
    user_question: str,
    db,
    model_name: str = "nano"
):

    prompt = build_input_analysis_prompt(
        user_question,
        db_name=db.display_name,
        schema_summary=format_schema_summary(db.schema)
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