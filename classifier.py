from prompts.classification_prompt import (
    build_classification_prompt
)

from schema import format_schema_summary

from models.model_manager import get_model


def classify_question(
    user_question: str,
    db,
    model_name: str = "nano"
):

    prompt = build_classification_prompt(
        user_question,
        db_name=db.display_name,
        schema_summary=format_schema_summary(db.schema)
    )

    model = get_model(model_name)

    response = model(prompt)

    response = response.strip().upper()

    if response not in [
        "GREETING",
        "DATABASE",
        "DISCOVERY",
        "UNRELATED"
    ]:

        raise ValueError(
            f"Invalid classification: {response}"
        )

    return response
