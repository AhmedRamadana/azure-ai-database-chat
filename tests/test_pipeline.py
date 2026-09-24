from pipeline import run_pipeline


questions = [
    "Hi",
    "How many customers are there?",
    "What is the capital of France?"
]


for question in questions:

    print("\n" + "=" * 60)
    print("QUESTION:")
    print(question)

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