import json

from prompts.multiple_question_prompt import (
    build_multiple_question_prompt
)

from models.model_manager import (
    get_model
)


MAX_QUESTIONS = 5


def analyze_multiple_questions(
    user_question: str,
    model_name: str = "nano",
    db_name: str = "Chinook"
):

    prompt = build_multiple_question_prompt(
        user_question,
        db_name=db_name
    )

    model = get_model(
        model_name
    )

    response = model(
        prompt
    )

    response = response.strip()

    try:

        result = json.loads(
            response
        )

    except json.JSONDecodeError as error:

        raise ValueError(
            "Multiple question analyzer returned "
            "invalid JSON."
        ) from error

    if not isinstance(
        result,
        dict
    ):

        raise ValueError(
            "Multiple question analyzer result "
            "must be a JSON object."
        )

    question_type = result.get(
        "type"
    )

    questions = result.get(
        "questions"
    )

    if question_type not in [
        "SINGLE",
        "MULTIPLE"
    ]:

        raise ValueError(
            f"Invalid question type: "
            f"{question_type}"
        )

    if not isinstance(
        questions,
        list
    ):

        raise ValueError(
            "'questions' must be a list."
        )

    if not questions:

        raise ValueError(
            "Question list cannot be empty."
        )

    if len(questions) > MAX_QUESTIONS:

        raise ValueError(
            f"Too many questions returned. "
            f"Maximum allowed: {MAX_QUESTIONS}"
        )

    for question in questions:

        if not isinstance(
            question,
            str
        ):

            raise ValueError(
                "Every decomposed question "
                "must be a string."
            )

        if not question.strip():

            raise ValueError(
                "Decomposed questions cannot be empty."
            )

    # الـ label مجرد توقع من الموديل. لو الـ label والقايمة مش متطابقين
    # (مثلًا MULTIPLE بسؤال واحد، وده بيحصل كتير مع nano على سؤال واحد
    # عادي)، الأمان إننا نعامله كسؤال واحد بنصه الأصلي بدل ما نفشل.
    # ده مش بيفتح أي ثغرة: السؤال بيكمل في نفس الـ pipeline والفحوصات.
    if (
        question_type == "SINGLE" and len(questions) != 1
    ) or (
        question_type == "MULTIPLE" and len(questions) < 2
    ):

        return {
            "type": "SINGLE",
            "questions": [user_question.strip()]
        }

    return {
        "type": question_type,
        "questions": [
            question.strip()
            for question in questions
        ]
    }