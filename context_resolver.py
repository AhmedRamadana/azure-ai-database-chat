from prompts.context_prompt import (
    build_context_prompt
)

from models.model_manager import (
    get_model
)


# أقصى عدد رسائل من تاريخ المحادثة بنبعتها للـ LLM. بدون حد، الـ
# prompt بيكبر مع كل رسالة (تكلفة وبطء)، وغالبًا السؤال بيعتمد على
# آخر كام رسالة بس.
MAX_HISTORY_MESSAGES = 6


def resolve_context(
    current_question: str,
    conversation_history: list,
    db,
    model_name: str = "nano"
):

    # No previous conversation
    # means there is no context to resolve.
    if not conversation_history:

        return current_question

    prompt = build_context_prompt(
        current_question=current_question,
        conversation_history=(
            conversation_history[-MAX_HISTORY_MESSAGES:]
        ),
        db_name=db.display_name
    )

    model = get_model(
        model_name
    )

    response = model(
        prompt
    )

    return response.strip()