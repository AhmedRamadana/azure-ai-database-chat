from pipeline import run_pipeline
from tests.helpers import get_demo_db, get_user


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
        model_name="nano",
        db=get_demo_db()
    )

    print("\nTYPE:")
    print(result["type"])

    print("\nANSWER:")
    print(result["answer"])

    if result["type"] == "database":

        print("\nSQL:")
        print(result["sql"])