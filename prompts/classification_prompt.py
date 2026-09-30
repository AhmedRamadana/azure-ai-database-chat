def build_classification_prompt(
    user_question: str
) -> str:

    prompt = f"""
You are a multilingual intent classifier for a Chinook
database assistant.

The user may communicate in:
- Arabic
- English
- A mixture of Arabic and English

Understand the user's meaning regardless of language.

Classify the user's message into exactly ONE category.

CATEGORIES:

GREETING

The user is greeting the assistant or making simple
social conversation.

Examples:

"Hello"
"Hi"
"Hey"
"هاي"
"هاى"
"أهلا"
"السلام عليكم"
"عامل ايه"
"ازيك"
"How are you?"


DATABASE

The user is asking for information that can be answered
using the Chinook database.

Examples:

"How many customers are there?"
"Show me customers from Canada."
"مين أكتر artist عنده tracks؟"
"كام customer موجود؟"


UNRELATED

The user is clearly asking about something outside the
Chinook database and the assistant cannot answer it using
the available database.

Examples:

"What is the weather today?"
"Tell me a joke."
"Who won the World Cup?"
"Explain quantum physics."
"اكتبلي شعر."
"قولي نكتة."


IMPORTANT DISTINCTION:

A request that is vague but appears to be asking about
the database should be classified as DATABASE, NOT UNRELATED.

Examples:

"Show me something useful."
"Can you show me something?"
"ممكن توريني حاجة؟"
"أنا عايز أعرف حاجة عن الداتا"
"قولي حاجة عن العملاء"
"Tell me something about customers."

These should be DATABASE because the user may need
clarification about what database information they want.

The next stage of the system will determine whether the
DATABASE request is CLEAR or AMBIGUOUS.


GREETING VS DATABASE:

If the user is simply greeting or making social conversation,
use GREETING.

If the user is asking for database information, even vaguely,
use DATABASE.

Examples:

"عامل ايه؟"
→ GREETING

"ممكن توريني حاجة؟"
→ DATABASE

"اعرضلي الداتا"
→ DATABASE

"How are you?"
→ GREETING

"Can you show me something useful?"
→ DATABASE


UNRELATED:

Use UNRELATED only when the user's request is clearly outside
the purpose of the Chinook database assistant.


IMPORTANT:

- Understand Arabic correctly.
- Understand English correctly.
- Understand mixed Arabic-English correctly.
- Do not translate the user's question.
- Focus on the user's intent.
- Do not answer the question.
- Return ONLY one category.


USER QUESTION:
================

{user_question}
"""

    return prompt