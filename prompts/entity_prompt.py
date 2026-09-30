def build_entity_prompt(
    user_question: str
):

    return f"""
You are an entity detection assistant for a Chinook
database assistant.

Your task is to identify possible database entity values
mentioned by the user.

USER QUESTION:
{user_question}


Look for possible values such as:

- Artist names
- Album names
- Customer countries
- Genre names
- Media types
- Employee names
- Playlist names


IMPORTANT:

1. Return only possible entity values.

2. Return one entity per line.

3. Do not explain.

4. Do not generate SQL.

5. Do not answer the question.

6. Do not invent entities.

7. If there are no obvious entity values,
   return:

NONE


Examples:

Question:
Show me albums by AC DC

Output:
AC DC


Question:
Show me customers from Brazill

Output:
Brazill


Question:
Which artists have the most tracks?

Output:
NONE


Question:
اعرضلي العملاء من Canada

Output:
Canada


Question:
Show me Metallica tracks

Output:
Metallica


USER QUESTION:
{user_question}
"""