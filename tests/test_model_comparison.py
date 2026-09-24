import time

from pipeline import run_pipeline


questions = [
    "How many artists are there?",
    "Which albums belong to AC/DC?",
    "Which customers purchased tracks by Metallica?",
    "What are the top 5 artists with the most tracks?",
    "كام customer موجود في database؟",
]


models = [
    "nano",
    "mini",
]


for question in questions:

    print("\n" + "=" * 80)
    print("QUESTION:")
    print(question)

    for model_name in models:

        print("\n" + "-" * 80)
        print(f"MODEL: {model_name}")

        start_time = time.perf_counter()

        try:

            result = run_pipeline(
                user_question=question,
                model_name=model_name
            )

            end_time = time.perf_counter()

            latency = end_time - start_time

            print("\nTYPE:")
            print(result["type"])

            print("\nANSWER:")
            print(result["answer"])

            print("\nLATENCY:")
            print(f"{latency:.2f} seconds")

            if result["type"] == "database":

                print("\nSQL:")
                print(result["sql"])

                print("\nROWS PREVIEW:")

                for row in result["rows"][:5]:
                    print(row)

        except Exception as e:

            end_time = time.perf_counter()

            latency = end_time - start_time

            print("\nERROR:")
            print(e)

            print("\nLATENCY:")
            print(f"{latency:.2f} seconds")

