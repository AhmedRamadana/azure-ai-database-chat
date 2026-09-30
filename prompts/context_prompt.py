def build_context_prompt(
    current_question: str,
    conversation_history: list
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
Chinook database assistant.

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


Current question:
How many customers are there?

Output:
How many customers are there?


Return ONLY the standalone question.
"""