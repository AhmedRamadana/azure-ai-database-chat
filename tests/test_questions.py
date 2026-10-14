from pipeline import run_pipeline
from tests.helpers import get_demo_db, get_user


questions = [
    "Which customers purchased tracks by AC/DC?",
    "Which customers bought songs from Metallica?",
    "مين العملاء اللي اشتروا tracks من AC/DC؟",
]


for question in questions:

    print("\n" + "=" * 70)

    print("QUESTION:")
    print(question)

    try:

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

            print("\nROWS:")

            for row in result["rows"][:5]:
                print(row)

    except Exception as e:

        print("\nERROR:")
        print(e)