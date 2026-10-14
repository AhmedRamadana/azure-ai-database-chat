from pipeline import run_pipeline
from tests.helpers import get_demo_db, get_user


test_questions = [

    # 1. Multiple JOIN + Aggregation + Sorting
    """
    Show me the top 5 customers who spent the most money,
    including their first name, last name, email, and total spending.
    """,

    # 2. Artist → Album → Track + Aggregation
    """
    Show me the top 5 artists with the highest number of tracks,
    including the artist name and track count.
    """,

    # 3. Filtering + Aggregation
    """
    Show me the top 5 customers from Brazil based on their total spending.
    """,

    # 4. Multiple requested columns
    """
    Show me the first name, last name, email, country,
    and total number of invoices for each customer.
    """,

    # 5. Arabic complex question
    """
    هاتلي أكتر 5 customers دفعوا فلوس،
    مع الاسم والإيميل وإجمالي المبلغ اللي دفعوه.
    """,

    # 6. Mixed language
    """
    اعرضلي top 5 artists اللي عندهم أكبر number of tracks
    مع اسم الـ artist وعدد الـ tracks.
    """,

    # 7. Complex relationship
    """
    Which customers have purchased tracks from Metallica,
    and how much did each customer spend in total?
    """,

    # 8. Multiple conditions
    """
    Show me customers from Brazil who have made more than
    5 invoices, including their names and email addresses.
    """,

]


for i, question in enumerate(
    test_questions,
    start=1
):

    print("\n" + "=" * 90)
    print(f"TEST {i}")
    print("=" * 90)

    print("\nQUESTION:")
    print(question.strip())

    try:

        result = run_pipeline(
            user_question=question.strip(),
            model_name="mini",
            db=get_demo_db()
        )

        print("\nTYPE:")
        print(result.get("type"))

        print("\nRESOLVED QUESTION:")
        print(result.get("resolved_question"))

        print("\nSQL:")
        print(result.get("sql"))

        print("\nCOLUMNS:")
        print(result.get("columns"))

        print("\nROWS:")
        rows = result.get("rows")

        if rows is not None:

            for row in rows[:10]:
                print(row)

            if len(rows) > 10:
                print(
                    f"... and {len(rows) - 10} more rows"
                )

        print("\nANSWER:")
        print(result.get("answer"))

    except Exception as e:

        print("\nERROR:")
        print(repr(e))