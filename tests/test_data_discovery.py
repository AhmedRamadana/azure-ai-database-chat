from data_discovery import (
    analyze_data_availability
)
from tests.helpers import get_demo_db, get_user


test_cases = [

    # =========================================================
    # AVAILABLE
    # =========================================================

    "How many customers are there?",

    "How many artists are there?",

    "Show me customers from Brazil.",

    "Which artist has the most tracks?",

    "What is the total spending of customers?",


    # =========================================================
    # UNAVAILABLE
    # =========================================================

    "What is the average age of customers?",

    "Show me customers' salaries.",

    "What is the average height of customers?",


    # =========================================================
    # ARABIC
    # =========================================================

    "كام customer موجود؟",

    "إيه متوسط عمر العملاء؟",


    # =========================================================
    # MIXED
    # =========================================================

    "How many customers عندنا؟",

    "What is the average age of customers؟"
]


for index, question in enumerate(
    test_cases,
    start=1
):

    print("\n")

    print(
        "=" * 80
    )

    print(
        f"TEST {index}"
    )

    print(
        "=" * 80
    )

    print("\nQUESTION:")

    print(
        question
    )

    try:

        result = analyze_data_availability(
            user_question=question,
            model_name="mini",
            db=get_demo_db()
        )

        print("\nRESULT:")

        print(
            result
        )

    except Exception as error:

        print("\nERROR:")

        print(
            repr(error)
        )
