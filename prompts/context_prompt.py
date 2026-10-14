def build_context_prompt(
    current_question: str,
    conversation_history: list,
    db_name: str = "Chinook"
):

    history_text = ""

    for message in conversation_history:

        role = message.get("role")
        content = message.get("content")

        history_text += (
            f"{role.upper()}: {content}\n"
        )

    return f"""
You are a conversation context resolver for a
{db_name} database assistant.

Your task is to understand the user's current question
using the previous conversation.

The goal is to convert the current question into a
standalone question that can be understood without
the previous conversation.

CONVERSATION HISTORY:
=====================

{history_text}


CURRENT USER QUESTION:
======================

{current_question}


RULES:

1. If the current question depends on previous context,
   rewrite it as a complete standalone question.

2. Preserve the user's original intent.

3. Do not change the requested operation.

4. Do not invent information.

5. Resolve references such as:

   - "what about..."
   - "and Brazil?"
   - "what about the top 10?"
   - "how about them?"
   - "and the albums?"
   - "what about the previous one?"

6. If the current question is already standalone,
   return it unchanged.

6a. REPLIES TO A CLARIFICATION QUESTION:
   If the last ASSISTANT message asked the user a clarification
   question with options, and the current message is a short
   answer to it, then rewrite it as ONE standalone question
   that combines the user's ORIGINAL request (the USER message
   before the clarification) with the option(s) they chose.

   Short answers include:
   - an option number: "1", "2 and 3", "the first one"
   - "both", "all", "the second one", "yes", "no"
   - the wording of an option
   - Arabic: "الأول", "التاني", "الاتنين", "الكل", "اه", "ايوه",
     "لا", "رقم 2"

   If the user chose several options, include all of them.
   If the current message is clearly a NEW unrelated question
   (not an answer), ignore this rule and treat it normally.

7. The question may be written in:
   - Arabic
   - English
   - Mixed Arabic-English

8. Preserve the user's language style.

9. Do NOT answer the question.

10. Do NOT generate SQL.

11. Return ONLY the standalone question.


EXAMPLES:

Previous:
How many customers are from Canada?

Current:
What about Brazil?

Output:
How many customers are from Brazil?


Previous:
Show me the top 5 artists by number of tracks.

Current:
What about the top 10?

Output:
Show me the top 10 artists by number of tracks.


Previous:
How many customers are there?

Current:
How many artists?

Output:
How many artists are there?


Previous:
اعرضلي العملاء من Canada.

Current:
طب و Egypt؟

Output:
اعرضلي العملاء من Egypt.


Previous:
كام customer موجود؟

Current:
وكام artist؟

Output:
كام artist موجود؟


Previous:
USER: Show me the data.
ASSISTANT: What would you like to see?
1. Customers by country
2. Top selling tracks
3. Total sales per year

Current:
2

Output:
Show me the top selling tracks.


Previous:
USER: اعرضلي معلومات عن المبيعات
ASSISTANT: تقصد انهي معلومات عن المبيعات؟
1. إجمالي المبيعات لكل سنة
2. أعلى العملاء إنفاقًا

Current:
الاتنين

Output:
اعرضلي إجمالي المبيعات لكل سنة وأعلى العملاء إنفاقًا.


Previous:
USER: Show me the data.
ASSISTANT: What would you like to see?
1. Customers by country
2. Top selling tracks

Current:
How many albums are there?

Output:
How many albums are there?


Current question:
How many customers are there?

Output:
How many customers are there?


Return ONLY the standalone question.
"""