from pipeline import run_pipeline
from tests.helpers import get_demo_db, get_user


test_questions = [

    "Show me customers from Brazill",

    "Show me customers from Caneda",

    "Show me customers from Germeny",

    "Show me Metalllica tracks",

    "Show me Pink Floid albums",

    "هاتلي customers من Brazill",

    "هاتلي tracks بتاعة Metalllica",

    "hatly el customers mn Brazill",
]


for i, question in enumerate(
    test_questions,
    start=1
):

    print("\n" + "=" * 80)

    print(
        f"TEST {i}"
    )

    print("=" * 80)

    print(
        "QUESTION:"
    )

    print(
        question
    )

    try:

        result = run_pipeline(
            user_question=question,
            model_name="mini",
            db=get_demo_db()
        )

        print(
            "\nTYPE:"
        )

        print(
            result.get("type")
        )

        print(
            "\nRESOLVED QUESTION:"
        )

        print(
            result.get(
                "resolved_question"
            )
        )

        print(
            "\nGENERATED / EXECUTED SQL:"
        )

        print(
            result.get("sql")
        )

        print(
            "\nCOLUMNS:"
        )

        print(
            result.get("columns")
        )

        print(
            "\nROWS:"
        )

        print(
            result.get("rows")
        )

        print(
            "\nANSWER:"
        )

        print(
            result.get("answer")
        )

    except Exception as e:

        print(
            "\nERROR:"
        )

        print(
            repr(e)
        )
