from text_to_sql import generate_sql


test_questions = [

    # -----------------------------------------
    # Country typos
    # -----------------------------------------

    "Show me customers from Brazill",
    "Show me customers from Caneda",
    "Show me customers from Germeny",

    # -----------------------------------------
    # Artist typos
    # -----------------------------------------

    "Show me Metalllica tracks",
    "Show me AC DC albums",
    "Show me Pink Floid albums",

    # -----------------------------------------
    # Arabic / mixed entity names
    # -----------------------------------------

    "هاتلي customers من Brazill",
    "هاتلي tracks بتاعة Metalllica",
    "اعرضلي albums بتاعة AC DC",

    # -----------------------------------------
    # Arabizi
    # -----------------------------------------

    "hatly el customers mn Brazill",
    "hatly tracks beta3t Metalllica",

    # -----------------------------------------
    # Correct values
    # -----------------------------------------

    "Show me customers from Brazil",
    "Show me customers from Canada",
    "Show me Metallica tracks",
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