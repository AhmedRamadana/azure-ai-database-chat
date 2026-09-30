from multiple_question_analyzer import (
    analyze_multiple_questions
)


test_questions = [

    # ==========================================
    # SINGLE QUESTIONS
    # ==========================================

    "How many customers are there?",

    "Show me customers from Brazil and their emails.",

    "Which artists have the most tracks and what are their track counts?",

    "Show me the top 5 customers with their names, emails, and total spending.",

    "Show me customers from Brazil who have made more than 5 invoices.",


    # ==========================================
    # MULTIPLE QUESTIONS
    # ==========================================

    "How many customers are there and how many artists are there?",

    "How many customers are from Brazil and how many artists are in the database?",

    "Show me the number of customers and the number of tracks.",

    "هاتلي عدد الـ customers وعدد الـ artists.",

    "كام customer عندنا وكام artist؟",


    # ==========================================
    # MIXED
    # ==========================================

    "How many customers عندنا and كام artists؟",

    "Show me customers from Brazil and how many artists are there.",

    "هاتلي customers من Brazil و كام artists موجودين؟",
]


for i, question in enumerate(
    test_questions,
    start=1
):

    print("\n" + "=" * 90)

    print(
        f"TEST {i}"
    )

    print("=" * 90)

    print("\nQUESTION:")

    print(question)

    try:

        result = analyze_multiple_questions(
            user_question=question,
            model_name="mini"
        )

        print("\nTYPE:")

        print(
            result["type"]
        )

        print("\nQUESTIONS:")

        for index, sub_question in enumerate(
            result["questions"],
            start=1
        ):

            print(
                f"{index}. {sub_question}"
            )

    except Exception as error:

        print("\nERROR:")

        print(
            repr(error)
        )