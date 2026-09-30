from text_to_sql import generate_sql


test_questions = [

    "Show me costomers from Brazill",

    "هاتلي الكستمرز من Brazil",

    "كام customer موجود في Brazil؟",

    "مين أكتر artist عنده تراكس؟",

    "hatly el customers mn Brazil",

    "اعرضلي ال albums بتاعة AC DC",

    "هاتلي أسماء العملاء وإيميلاتهم",

    "Show me Metalllica tracks",

    "اعرضلي العملاء من Canada",

    "What are the top 5 artists with the most tracks?",

    "Show me all customer names and emails",

    "Show me customer first names and email addresses",

    "هاتلي كل العملاء مع الإيميلات",

    "اعرضلي أسماء الـ customers والـ emails",

    "Show me the names of all artists",

    "هاتلي أسماء الـ artists",

    "Show me all albums",

    "هاتلي كل الـ tracks",

    "How many customers are from Brazil?",

    "How many tracks does Metallica have?"
]


for i, question in enumerate(
    test_questions,
    start=1
):

    print("\n" + "=" * 70)

    print(f"TEST {i}")

    print("=" * 70)

    print("QUESTION:")

    print(question)

    print("\nGENERATED SQL:")

    try:

        sql = generate_sql(
            user_question=question,
            model_name="nano"
        )

        print(sql)

    except Exception as e:

        print("\nERROR:")

        print(e)