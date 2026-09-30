from multiple_question_analyzer import (
    analyze_multiple_questions
)

from text_to_sql import (
    generate_sql
)

from value_resolver import (
    resolve_sql_values
)

from sql_executor import (
    execute_sql
)

from multiple_answer_generator import (
    generate_multiple_answer
)


def execute_multiple_questions(
    user_question: str,
    model_name: str = "mini"
):

    analysis = analyze_multiple_questions(
        user_question=user_question,
        model_name=model_name
    )

    question_type = analysis["type"]

    questions = analysis["questions"]

    print("\nQUESTION TYPE:")
    print(question_type)

    print("\nDECOMPOSED QUESTIONS:")

    for index, question in enumerate(
        questions,
        start=1
    ):

        print(
            f"{index}. {question}"
        )

    if question_type != "MULTIPLE":

        print(
            "\nThis test expects MULTIPLE."
        )

        return

    question_results = []

    for index, question in enumerate(
        questions,
        start=1
    ):

        print("\n" + "-" * 80)

        print(
            f"PROCESSING QUESTION {index}"
        )

        print("-" * 80)

        print("\nQUESTION:")

        print(question)

        # ==========================================
        # 1. GENERATE SQL
        # ==========================================

        sql_query = generate_sql(
            user_question=question,
            model_name=model_name
        )

        print("\nGENERATED SQL:")

        print(sql_query)

        # ==========================================
        # 2. RESOLVE DATABASE VALUES
        # ==========================================

        resolved_sql, corrections = (
            resolve_sql_values(
                sql_query
            )
        )

        if corrections:

            print("\nVALUE CORRECTIONS:")

            print(corrections)

        # ==========================================
        # 3. EXECUTE SQL
        # ==========================================

        columns, rows = execute_sql(
            resolved_sql
        )

        print("\nCOLUMNS:")

        print(
            list(columns)
        )

        print("\nROWS:")

        for row in rows[:10]:

            print(row)

        if len(rows) > 10:

            print(
                f"... and {len(rows) - 10} more rows"
            )

        # ==========================================
        # 4. STORE RESULT
        # ==========================================

        question_results.append(
            {
                "question": question,
                "sql": resolved_sql,
                "columns": list(columns),
                "rows": rows
            }
        )

    # ==========================================
    # 5. GENERATE COMBINED ANSWER
    # ==========================================

    answer = generate_multiple_answer(
        user_question=user_question,
        question_results=question_results,
        model_name=model_name
    )

    print("\n" + "=" * 80)

    print("FINAL ANSWER")

    print("=" * 80)

    print(answer)

    return {
        "type": "multiple",
        "answer": answer,
        "questions": questions,
        "results": question_results
    }


# ==================================================
# TEST CASES
# ==================================================

test_questions = [

    "How many customers are there and how many artists are there?",

    "How many customers are from Brazil and how many artists are in the database?",

    "Show me the number of customers and the number of tracks.",

    "هاتلي عدد الـ customers وعدد الـ artists.",

    "كام customer عندنا وكام artist؟",

    "How many customers عندنا and كام artists؟",

]


for index, question in enumerate(
    test_questions,
    start=1
):

    print("\n\n")

    print(
        "#" * 90
    )

    print(
        f"TEST {index}"
    )

    print(
        "#" * 90
    )

    print("\nUSER QUESTION:")

    print(question)

    try:

        execute_multiple_questions(
            user_question=question,
            model_name="mini"
        )

    except Exception as error:

        print("\nERROR:")

        print(
            repr(error)
        )