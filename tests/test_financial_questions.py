from pipeline import run_pipeline
from tests.helpers import get_demo_db, get_user


test_questions = [

    # 1. Total spending of each customer
    "How much did each customer spend?",

    # 2. Spending on a specific artist
    "How much did each customer spend on Metallica?",

    # 3. Total spending on a specific artist
    "How many invoices did each customer make?",

]


for i, question in enumerate(
    test_questions,
    start=1
):

    print("\n" + "=" * 90)
    print(f"TEST {i}")
    print("=" * 90)

    print("\nQUESTION:")
    print(question)

    try:

        result = run_pipeline(
            user_question=question,
            model_name="mini",
            db=get_demo_db()
        )

        print("\nTYPE:")
        print(result.get("type"))

        print("\nSQL:")
        print(result.get("sql"))

        print("\nCOLUMNS:")
        print(result.get("columns"))

        print("\nROWS:")

        rows = result.get("rows")

        if rows:

            for row in rows[:10]:
                print(row)

            if len(rows) > 10:
                print(
                    f"... and {len(rows) - 10} more rows"
                )

        else:
            print(rows)

        print("\nANSWER:")
        print(result.get("answer"))

    except Exception as e:

        print("\nERROR:")
        print(repr(e))