from prompts.context_prompt import (
    build_context_prompt
)

from models.model_manager import (
    get_model
)


def resolve_context(
    current_question: str,
    conversation_history: list,
    model_name: str = "nano"
):

    # No previous conversation
    # means there is no context to resolve.
    if not conversation_history:

        return current_question

    prompt = build_context_prompt(
        current_question=current_question,
        conversation_history=conversation_history
    )

    model = get_model(
        model_name
    )

    response = model(
        prompt
    )

    return response.strip()