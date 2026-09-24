from pipeline import run_pipeline


questions = [
    # English
    "How many artists are there?",

    # Arabic
    "كام فنان موجود في قاعدة البيانات؟",

    # Mixed
    "كام customer موجود في database؟",

    # English JOIN
    "Which customers purchased tracks by AC/DC?",

    # Arabic JOIN
    "مين العملاء اللي اشتروا tracks من AC/DC؟",

    # Mixed JOIN
    "مين customers اللي اشتروا songs من Metallica؟",

    # Arabic aggregation
    "مين أكتر 5 artists عندهم tracks؟",
]


for question in questions:

    print("\n" + "=" * 80)

    print("QUESTION:")
    print(question)

    try:

        result = run_pipeline(
            user_question=question,
            model_name="nano"
        )

        print("\nTYPE:")
        print(result["type"])

        print("\nANSWER:")
        print(result["answer"])

        if result["type"] == "database":

            print("\nSQL:")
            print(result["sql"])

            print("\nROWS PREVIEW:")

            for row in result["rows"][:5]:
                print(row)

    except Exception as e:

        print("\nERROR:")
        print(e)