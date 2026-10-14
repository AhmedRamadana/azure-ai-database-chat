"""
schema_answer.py

الإجابة على أسئلة "إيه اللي موجود في الداتابيز؟" (Discovery):

    - إيه الجداول؟  - الجدول X فيه إيه؟  - أقدر أسألك عن إيه؟

الفكرة: الحقائق (أسماء الجداول والأعمدة) بيطلّعها كود Python من
الـ Schema الفعلية، مفلترة حسب الـ Role. الـ LLM بيصيغها بس، ومش
بيشوف أي عمود محجوب، فمستحيل يسرّبه حتى لو اتلخبط.
"""

import re

from authorization.access_policy import visible_schema

from language_utils import detect_language

from models.model_manager import get_model

from prompts.schema_answer_prompt import build_schema_answer_prompt


# حدود عشان الداتابيز الكبيرة ما تبوّظش الـ prompt
MAX_TABLES_OVERVIEW = 60
MAX_COLUMNS_OVERVIEW = 15
MAX_TABLES_DETAIL = 5
MAX_COLUMNS_DETAIL = 80


def _name_variants(table_name: str):
    """
    "Customer" -> {"customer", "customers"}.   "Invoice_Line" ->
    {"invoice_line", "invoice line", "invoiceline", ...}
    """

    base = table_name.lower()

    spaced = re.sub(r"[_\s]+", " ", base)
    # CamelCase: InvoiceLine -> invoice line
    camel = re.sub(
        r"(?<=[a-z0-9])(?=[A-Z])",
        " ",
        table_name
    ).lower()

    variants = {base, spaced, camel, base.replace("_", "")}

    variants |= {variant + "s" for variant in list(variants)}

    return {variant for variant in variants if variant}


def find_mentioned_tables(user_question: str, schema: dict) -> list:
    """
    الجداول اللي السؤال ذكرها بالاسم (بالحروف الإنجليزي). بنقارن
    على حدود الكلمات علشان "Track" ما يتمسكش جوه "Tracking".
    """

    text = re.sub(r"[_\s]+", " ", user_question.lower())

    found = []

    for table_name in schema:

        for variant in _name_variants(table_name):

            pattern = (
                r"(?<![a-z0-9])"
                + re.escape(variant)
                + r"(?![a-z0-9])"
            )

            if re.search(pattern, text):

                found.append(table_name)

                break

    return found


def build_schema_facts(
    user_question: str,
    db,
    role: str
) -> str:
    """
    الحقائق اللي هتتبعت للـ LLM (وتتعرض كـ fallback): اسم الداتابيز،
    والجداول/الأعمدة المسموحة للـ role ده بس.
    """

    schema = visible_schema(
        db.schema,
        role,
        db.policy
    )

    lines = [
        f"DATABASE: {db.display_name}",
        f"TOTAL TABLES AVAILABLE TO THIS USER: {len(schema)}",
    ]

    if not schema:

        lines.append("(no tables are available to this user)")

        return "\n".join(lines)

    mentioned = [
        name
        for name in find_mentioned_tables(user_question, schema)
    ][:MAX_TABLES_DETAIL]

    if mentioned:

        lines.append("")
        lines.append("DETAILS FOR THE TABLES THE USER ASKED ABOUT:")

        for table_name in mentioned:

            info = schema[table_name]

            lines.append("")
            lines.append(f"TABLE: {table_name}")
            lines.append("COLUMNS:")

            for column in info["columns"][:MAX_COLUMNS_DETAIL]:

                lines.append(
                    f"- {column['name']} ({column['type']})"
                )

            extra = len(info["columns"]) - MAX_COLUMNS_DETAIL

            if extra > 0:
                lines.append(f"- ... (+{extra} more columns)")

            for foreign_key in info["foreign_keys"]:

                lines.append(
                    "RELATES TO: "
                    f"{', '.join(foreign_key['column'])} -> "
                    f"{foreign_key['references_table']}."
                    f"{', '.join(foreign_key['references_column'])}"
                )

        return "\n".join(lines)

    lines.append("")
    lines.append("TABLES:")

    for table_name in list(schema)[:MAX_TABLES_OVERVIEW]:

        names = [
            column["name"]
            for column in schema[table_name]["columns"]
        ]

        shown = ", ".join(names[:MAX_COLUMNS_OVERVIEW])

        extra = len(names) - MAX_COLUMNS_OVERVIEW

        if extra > 0:
            shown += f", ... (+{extra} more)"

        lines.append(f"- {table_name}: {shown}")

    hidden = len(schema) - MAX_TABLES_OVERVIEW

    if hidden > 0:
        lines.append(f"- ... (+{hidden} more tables)")

    return "\n".join(lines)


def answer_schema_question(
    user_question: str,
    db,
    user: dict,
    model_name: str = "nano",
    language_hint: str = None
) -> str:
    """
    language_hint: رسالة المستخدم الأصلية (لتحديد لغة الرد). لو
    مبعتتش، بنستخدم user_question نفسها.
    """

    role = user.get("role")

    if not role:
        raise ValueError("User role is missing.")

    facts = build_schema_facts(
        user_question,
        db,
        role
    )

    language = detect_language(language_hint or user_question)

    prompt = build_schema_answer_prompt(
        user_question=user_question,
        facts=facts,
        language=language,
        db_name=db.display_name
    )

    model = get_model(model_name)

    return model(prompt).strip()
