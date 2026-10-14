from pipeline import run_pipeline
from tests.helpers import get_demo_db, get_user


test_cases = [

    # =========================================================
    # TEST 1
    # Multiple + Conversation Context
    # =========================================================

    {
    "name": "Multiple + Context",
    "question": "How many customers are there and how many artists are there?",
    "history": [
        {
            "role": "user",
            "content": "Show me something about the database."
        },
        {
            "role": "assistant",
            "content": "What would you like to know about the database?"
        }
    ]
},

    # =========================================================
    # TEST 2
    # Multiple + Value Resolution
    # =========================================================

    {
        "name": "Multiple + Value Resolution",
        "question": (
            "How many customers are from Brazill "
            "and how many artists are there?"
        ),
        "history": []
    },


    # =========================================================
    # TEST 3
    # Multiple + Complex Query
    # =========================================================

    {
        "name": "Multiple + Complex Query",
        "question": (
            "Show me the top 5 customers by total spending "
            "and how many artists are in the database."
        ),
        "history": []
    },


    # =========================================================
    # TEST 4
    # Multiple + Empty Result
    # =========================================================

    {
        "name": "Multiple + Empty Result",
        "question": (
            "How many customers are from Egypt "
            "and how many artists are there?"
        ),
        "history": []
    },


    # =========================================================
    # TEST 5
    # Three Independent Questions
    # =========================================================

    {
        "name": "Three Independent Questions",
        "question": (
            "How many customers are there, "
            "how many artists are there, "
            "and how many tracks are there?"
        ),
        "history": []
    },


    # =========================================================
    # TEST 6
    # Arabic / English Mixed Complex
    # =========================================================

    {
        "name": "Arabic + English Mixed Complex",
        "question": (
            "هاتلي top 5 customers by total spending "
            "وكمان قولي كام artists و tracks عندنا."
        ),
        "history": []
    },


    # =========================================================
    # TEST 7
    # One Sub-question Failure / Invalid Request
    # =========================================================

    {
        "name": "Sub-question Failure",
        "question": (
            "How many customers are there "
            "and what is the average age of customers?"
        ),
        "history": []
    },


    # =========================================================
    # TEST 8
    # Ambiguous Multiple Request
    # =========================================================

    {
        "name": "Ambiguous Multiple Request",
        "question": (
            "Tell me something about customers "
            "and artists."
        ),
        "history": []
    }
]


for index, test_case in enumerate(
    test_cases,
    start=1
):

    print("\n\n")

    print(
        "#" * 100
    )

    print(
        f"TEST {index}: {test_case['name']}"
    )

    print(
        "#" * 100
    )

    question = test_case["question"]

    history = test_case["history"]

    print("\nUSER QUESTION:")

    print(question)

    print("\nCONVERSATION HISTORY:")

    print(history)

    try:

        result = run_pipeline(
            user_question=question,
            model_name="mini",
            conversation_history=history,
            db=get_demo_db()
        )

        print("\nTYPE:")

        print(
            result.get("type")
        )

        print("\nRESOLVED QUESTION:")

        print(
            result.get("resolved_question")
        )

        print("\nQUESTIONS:")

        questions = result.get(
            "questions"
        )

        if questions:

            for question_index, sub_question in enumerate(
                questions,
                start=1
            ):

                print(
                    f"{question_index}. {sub_question}"
                )

        print("\nANSWER:")

        print(
            result.get("answer")
        )

        print("\nSQL / RESULTS:")

        results = result.get(
            "results"
        )

        if results:

            for result_index, item in enumerate(
                results,
                start=1
            ):

                print(
                    f"\n--- QUESTION {result_index} ---"
                )

                print(
                    "Question:"
                )

                print(
                    item.get("question")
                )

                print(
                    "\nSQL:"
                )

                print(
                    item.get("sql")
                )

                print(
                    "\nColumns:"
                )

                print(
                    item.get("columns")
                )

                print(
                    "\nRows:"
                )

                rows = item.get(
                    "rows"
                )

                if rows:

                    for row in rows[:10]:

                        print(row)

                    if len(rows) > 10:

                        print(
                            f"... and "
                            f"{len(rows) - 10} more rows"
                        )

                else:

                    print(
                        rows
                    )

        else:

            print(
                result.get("sql")
            )

            print(
                result.get("rows")
            )

    except Exception as error:

        print("\nERROR:")

        print(
            repr(error)
        )