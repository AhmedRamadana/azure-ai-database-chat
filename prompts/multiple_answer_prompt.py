def build_multiple_answer_prompt(
    user_question: str,
    question_results,
    language: str
):

    results_text = []

    for index, item in enumerate(
        question_results,
        start=1
    ):

        status = item.get(
            "status",
            "AVAILABLE"
        )

        if status == "UNAVAILABLE":

            results_text.append(
                f"""
QUESTION {index}:
{item["question"]}

STATUS:
UNAVAILABLE

MISSING INFORMATION:
{item.get("missing_items", [])}

SQL:
None

RESULT COLUMNS:
[]

RESULT ROWS:
[]
"""
            )

        # =======================================================
        # جديد: Branch مخصوص لـ UNAUTHORIZED
        # لازم يكون منفصل عن AVAILABLE عشان الـ Model يفرّق
        # بين "مفيش داتا" و"ممنوع تشوف الداتا"
        # =======================================================
        elif status == "UNAUTHORIZED":

            results_text.append(
                f"""
QUESTION {index}:
{item["question"]}

STATUS:
UNAUTHORIZED

NOTE:
The user does not have permission to access the data
required to answer this question. The data exists in
the database, but access to it is restricted for the
current user role.

SQL:
None

RESULT COLUMNS:
[]

RESULT ROWS:
[]
"""
            )

        else:

            results_text.append(
                f"""
QUESTION {index}:
{item["question"]}

STATUS:
AVAILABLE

SQL {index}:
{item["sql"]}

RESULT COLUMNS:
{item["columns"]}

RESULT ROWS:
{item["rows"]}
"""
            )

    combined_results = "\n".join(
        results_text
    )

    if language == "arabic":

        language_instruction = """
Answer entirely in Arabic.

Technical terms such as customers, artists, tracks,
SQL, database, and similar technical terms may remain
in English when natural.
"""

    elif language == "mixed":

        language_instruction = """
Answer naturally using the same mixed Arabic-English
style when appropriate.

Keep technical terms such as customers, artists,
tracks, SQL, database, and similar terms in English
when natural.
"""

    else:

        language_instruction = """
Answer entirely in English.
"""

    return f"""
You are a helpful assistant for a Chinook database
question-answering system.

The user asked multiple independent database questions.

Your task is to combine the available database results,
unavailable-data information, and unauthorized-access
information into ONE clear and concise natural-language
answer.

USER QUESTION:
{user_question}

{combined_results}

LANGUAGE:
{language}

LANGUAGE INSTRUCTION:
{language_instruction}

RULES:

1. Use ONLY the provided database results and
   availability information.

2. Do NOT invent facts.

3. Answer every sub-question.

4. Keep the answers clearly separated when there are
   multiple independent questions.

5. Preserve the order of the user's questions.

6. If a result contains no rows, clearly explain that
   no matching data was found for that sub-question.

7. If a question has STATUS = UNAVAILABLE, clearly explain
   that the requested information is not available in the
   database.

8. For UNAVAILABLE questions, mention the missing information
   when useful.

9. If a question has STATUS = UNAUTHORIZED, clearly explain
   that the user does not have permission to access that
   specific information. Do NOT say the data was "not found"
   or "not available" — the data exists, but access to it is
   restricted for the current user role.

10. Never confuse UNAVAILABLE (data does not exist in the
    database) with UNAUTHORIZED (data exists but the user
    lacks permission). These must be phrased differently.

11. Do not generate SQL for unavailable or unauthorized
    information.

12. Do not mention internal system details.

13. Do not mention prompts, models, classification,
    decomposition, or SQL generation.

14. Do not include SQL unless the user explicitly asks
    for SQL.

15. Keep the answer concise.

16. If a result contains a single scalar value, explain
    it naturally instead of exposing the raw tuple format.

17. If a result contains multiple rows, summarize or list
    the useful information clearly.

18. Do not merge unrelated results into one statement.

19. Do not treat unavailable information as zero.

20. Do not claim that missing information exists.

21. Do not treat unauthorized information as unavailable,
    and do not treat it as zero either.

22. Return ONLY the final natural-language answer.
"""