import json

from schema import (
    get_database_schema,
    format_schema_for_llm
)

from prompts.data_discovery_prompt import (
    build_data_discovery_prompt
)

from models.model_manager import (
    get_model
)


def clean_json_response(
    response: str
) -> str:

    response = response.strip()

    # Remove Markdown code fences
    if response.startswith("```"):

        lines = response.splitlines()

        # Remove opening fence
        if lines:
            lines = lines[1:]

        # Remove closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        response = "\n".join(
            lines
        ).strip()

    # Remove accidental json prefix
    if response.lower().startswith("json"):

        response = response[4:].strip()

    return response


def analyze_data_availability(
    user_question: str,
    model_name: str = "nano"
):

    schema = get_database_schema()

    schema_context = format_schema_for_llm(
        schema
    )

    prompt = build_data_discovery_prompt(
        user_question=user_question,
        schema_context=schema_context
    )

    model = get_model(
        model_name
    )

    response = model(
        prompt
    )

    response = clean_json_response(
        response
    )

    try:

        result = json.loads(
            response
        )

    except json.JSONDecodeError as error:

        raise ValueError(
            "Invalid JSON returned by "
            "data discovery: "
            f"{response}"
        ) from error

    status = result.get(
        "status"
    )

    missing_items = result.get(
        "missing_items"
    )

    if status not in [
        "AVAILABLE",
        "UNAVAILABLE"
    ]:

        raise ValueError(
            f"Invalid data discovery status: "
            f"{status}"
        )

    if not isinstance(
        missing_items,
        list
    ):

        raise ValueError(
            "missing_items must be a list."
        )

    return {
        "status": status,
        "missing_items": missing_items
    }
