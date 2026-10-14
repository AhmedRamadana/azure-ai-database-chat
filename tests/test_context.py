from context_resolver import resolve_context
from tests.helpers import get_demo_db, get_user


test_cases = [
    {
        "history": [
            {
                "role": "user",
                "content": "How many customers are from Canada?"
            },
            {
                "role": "assistant",
                "content": "There are 3 customers from Canada."
            }
        ],
        "question": "What about Brazil?",
        "expected": "How many customers are from Brazil?"
    },

    {
        "history": [
            {
                "role": "user",
                "content": "Show me the top 5 artists by number of tracks."
            },
            {
                "role": "assistant",
                "content": "Here are the top 5 artists."
            }
        ],
        "question": "What about the top 10?",
        "expected": "Show me the top 10 artists by number of tracks."
    },

    {
        "history": [
            {
                "role": "user",
                "content": "How many customers are there?"
            },
            {
                "role": "assistant",
                "content": "There are 59 customers."
            }
        ],
        "question": "How many artists?",
        "expected": "How many artists are there?"
    },

    {
        "history": [
            {
                "role": "user",
                "content": "اعرضلي العملاء من Canada."
            },
            {
                "role": "assistant",
                "content": "يوجد عملاء من Canada."
            }
        ],
        "question": "طب و Egypt؟",
        "expected": "اعرضلي العملاء من Egypt."
    },

    {
        "history": [
            {
                "role": "user",
                "content": "كام customer موجود؟"
            },
            {
                "role": "assistant",
                "content": "يوجد 59 customer."
            }
        ],
        "question": "وكام artist؟",
        "expected": "كام artist موجود؟"
    },

    {
        "history": [
            {
                "role": "user",
                "content": "How many customers are from Canada?"
            },
            {
                "role": "assistant",
                "content": "There are 3 customers from Canada."
            }
        ],
        "question": "How many artists are there?",
        "expected": "How many artists are there?"
    }
]


for index, test in enumerate(
    test_cases,
    start=1
):

    print(
        f"\n========== TEST {index} =========="
    )

    result = resolve_context(
        current_question=test["question"],
        conversation_history=test["history"],
        model_name="mini",
        db=get_demo_db()
    )

    print(
        "Current Question:"
    )

    print(
        test["question"]
    )

    print(
        "\nResolved Question:"
    )

    print(
        result
    )

    print(
        "\nExpected:"
    )

    print(
        test["expected"]
    )

    if result.strip() == test["expected"].strip():

        print(
            "\nPASS"
        )

    else:

        print(
            "\nFAIL"
        )