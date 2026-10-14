from prompts.clarification_prompt import (
    build_clarification_prompt
)

from schema import format_schema_summary

from authorization.access_policy import visible_schema

from models.model_manager import get_model


def generate_clarification(
    user_question: str,
    db,
    user: dict,
    model_name: str = "nano"
):
    """
    الخيارات المقترحة بتتبني من الأعمدة المسموحة للـ role ده بس، فمش
    هنقترح على USER حاجة (زي الإيميلات) هيتحجب عنها بعد كده.
    """

    role = user.get("role")

    if not role:
        raise ValueError("User role is missing.")

    prompt = build_clarification_prompt(
        user_question,
        db_name=db.display_name,
        schema_summary=format_schema_summary(
            visible_schema(
                db.schema,
                role,
                db.policy
            )
        )
    )

    model = get_model(
        model_name
    )

    response = model(
        prompt
    )

    return response.strip()