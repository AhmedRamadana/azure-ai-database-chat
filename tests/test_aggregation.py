from pipeline import run_pipeline


questions = [
    "How many artists are there?",
    "How many tracks are there?",
    "How many customers are there?",
    "How many tracks does each artist have?",
    "What are the top 5 artists with the most tracks?",
    "What are the top 5 customers by total spending?",
    "كام artist موجود؟",
    "كام track موجود؟",
    "مين أكتر 5 artists عندهم tracks؟",
]


for question in questions:

    print("\n" + "=" * 70)

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

            print("\nROWS:")

            for row in result["rows"][:10]:
                print(row)

    except Exception as e:

        print("\nERROR:")
        print(e)

