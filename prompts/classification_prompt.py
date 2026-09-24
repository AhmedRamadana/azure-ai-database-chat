def build_classification_prompt(
    user_question: str
) -> str:

    prompt = f"""
You are a multilingual classifier for a Chinook database assistant.

The user may communicate in:
- Arabic
- English
- A mixture of Arabic and English

You must understand the user's meaning regardless of language.

Classify the user's message into exactly ONE category.

Categories:

GREETING
- The user is greeting or making simple conversation.

DATABASE
- The user asks a question that can be answered using
  the Chinook database.

UNRELATED
- The user's question is not related to the Chinook database.

Important:
- Understand Arabic questions correctly.
- Understand English questions correctly.
- Understand mixed Arabic-English questions correctly.
- Do not translate the user's question.
- Focus on the meaning of the question.

Return ONLY one of these exact words:

GREETING
DATABASE
UNRELATED

USER QUESTION:
================

{user_question}
"""

    return prompt