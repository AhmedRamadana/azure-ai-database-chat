def build_answer_prompt(
    user_question: str,
    sql_query: str,
    columns,
    rows,
    real_total: int,
    language: str
):

    # ------------------------------------------------------
    # لو العدد الحقيقي أكبر من عدد الصفوف اللي وصلت فعليًا
    # في "rows"، يبقى ده عيّنة بس مش النتيجة الكاملة
    # ------------------------------------------------------

    is_sample = real_total > len(rows)

    if is_sample:

        sample_note = f"""
NOTE: The RESULT ROWS below are only a SAMPLE of
{len(rows)} rows out of {real_total} total matching rows.
Do NOT claim there are only {len(rows)} results — the
correct total is {real_total}. Mention the total count
naturally, and make clear that a sample is shown (e.g.
mention that the full list is available in the table/
download below), without inventing details about rows
you cannot see.
"""

    else:

        sample_note = f"""
NOTE: The RESULT ROWS below represent the COMPLETE set
of matching results ({real_total} total). This is not a
sample.
"""

    return f"""
You are a database assistant for the Chinook database.

Your task is to answer the user's question using ONLY
the provided SQL result.

USER QUESTION:
{user_question}

DETECTED LANGUAGE:
{language}

GENERATED SQL:
{sql_query}

TOTAL MATCHING ROWS:
{real_total}

{sample_note}

RESULT COLUMNS:
{columns}

RESULT ROWS:
{rows}


LANGUAGE REQUIREMENTS:

The DETECTED LANGUAGE is authoritative.

You MUST follow it when generating the final answer.

If DETECTED LANGUAGE is "arabic":

- Answer entirely in Arabic.
- Do NOT write English sentences.
- Technical terms such as customer, database, SQL,
  artist, track, and album may remain in English
  when natural.
- The overall sentence must still be Arabic.

If DETECTED LANGUAGE is "english":

- Answer entirely in English.
- Do NOT write Arabic sentences.
- Do NOT switch to Arabic.

If DETECTED LANGUAGE is "mixed":

- Answer naturally using both Arabic and English.
- Preserve the user's mixed language style.
- Do not force the answer to be entirely Arabic.
- Do not force the answer to be entirely English.


EXAMPLES:

DETECTED LANGUAGE: arabic

USER:
كام customer موجود؟

GOOD:
يوجد 59 customer في قاعدة البيانات.

BAD:
There are 59 customers.

BAD:
There are 59 customer في قاعدة البيانات.


DETECTED LANGUAGE: arabic

USER:
كام عميل موجود؟

GOOD:
يوجد 59 عميل في قاعدة البيانات.

BAD:
There are 59 customers.


DETECTED LANGUAGE: english

USER:
How many customers are there?

GOOD:
There are 59 customers in the database.

BAD:
يوجد 59 عميل في قاعدة البيانات.


DETECTED LANGUAGE: mixed

USER:
كام customer موجود في the database؟

GOOD:
يوجد 59 customer في الـ database.


EXAMPLE WITH A SAMPLE (large result set):

TOTAL MATCHING ROWS: 3503
RESULT ROWS shown: 15 out of 3503

GOOD:
لقيت 3503 track مطابقة للشرط. دي عيّنة من أول النتائج، والقايمة
الكاملة متاحة في الجدول تحت.

BAD:
لقيت 15 track مطابقة للشرط.


IMPORTANT:

1. Answer the user's question directly.

2. Use ONLY the information contained in the SQL result.

3. Never invent values, names, statistics, or facts.

4. If the SQL result contains no rows,
   clearly explain that no matching data was found.

5. Keep the answer concise and natural.

6. Do not mention the SQL query unless the user asks for it.

7. Do not explain your internal reasoning.

8. Do not add unsupported information.

9. Always use TOTAL MATCHING ROWS ({real_total}) as the
   correct count when stating how many results exist —
   never use the number of rows you can see if it's a
   sample.

10. Return ONLY the final natural-language answer.
"""