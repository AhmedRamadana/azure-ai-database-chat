"""
schema.py

قراءة الـ Schema من الداتابيز بتاعة الـ Session دي. مفيش cache
Global: الـ Schema بتتحمّل مرة واحدة وقت الاتصال وبتتخزن جوه
DBContext.
"""

from sqlalchemy import inspect


# لو إجمالي الأعمدة أكتر من الرقم ده بنستخدم صيغة مضغوطة للـ LLM
# (Chinook حوالي 64 عمود، فبيفضل على الصيغة الكاملة زي ما هو).
COMPACT_COLUMN_THRESHOLD = 150


def get_database_schema(
    engine,
    pg_schema: str = "public"
):

    inspector = inspect(engine)

    schema = {}

    tables = inspector.get_table_names(
        schema=pg_schema
    )

    for table in tables:

        columns = inspector.get_columns(
            table,
            schema=pg_schema
        )

        foreign_keys = inspector.get_foreign_keys(
            table,
            schema=pg_schema
        )

        schema[table] = {
            "columns": [
                {
                    "name": column["name"],
                    "type": str(column["type"])
                }
                for column in columns
            ],
            "foreign_keys": [
                {
                    "column": fk["constrained_columns"],
                    "references_table": fk["referred_table"],
                    "references_column": fk["referred_columns"]
                }
                for fk in foreign_keys
            ]
        }

    return schema


def _total_columns(schema) -> int:

    return sum(
        len(table_info["columns"])
        for table_info in schema.values()
    )


def format_schema_for_llm(
    schema,
    compact: bool = None
):
    """
    compact=None  -> تلقائي حسب حجم الـ Schema.
    """

    if compact is None:

        compact = (
            _total_columns(schema) > COMPACT_COLUMN_THRESHOLD
        )

    if compact:

        return _format_compact(schema)

    return _format_full(schema)


def _format_full(schema):

    lines = []

    lines.append("DATABASE SCHEMA")
    lines.append("================")

    for table_name, table_info in schema.items():

        lines.append(
            f"\nTABLE: {table_name}"
        )

        lines.append("COLUMNS:")

        for column in table_info["columns"]:

            lines.append(
                f"- {column['name']}: "
                f"{column['type']}"
            )

        foreign_keys = table_info["foreign_keys"]

        if foreign_keys:

            lines.append("FOREIGN KEYS:")

            for foreign_key in foreign_keys:

                columns = ", ".join(
                    foreign_key["column"]
                )

                references_columns = ", ".join(
                    foreign_key["references_column"]
                )

                lines.append(
                    f"- {table_name}.{columns} "
                    f"→ "
                    f"{foreign_key['references_table']}."
                    f"{references_columns}"
                )

    return "\n".join(lines)


def _format_compact(schema):
    """
    سطر واحد لكل جدول، عشان الداتابيز الكبيرة ما تبوّظش الـ context.
    """

    lines = []

    lines.append("DATABASE SCHEMA (compact)")
    lines.append("=========================")

    for table_name, table_info in schema.items():

        columns = ", ".join(
            f"{column['name']} {column['type']}"
            for column in table_info["columns"]
        )

        line = f"TABLE {table_name}({columns})"

        foreign_keys = table_info["foreign_keys"]

        if foreign_keys:

            references = "; ".join(
                f"{', '.join(fk['column'])} → "
                f"{fk['references_table']}."
                f"{', '.join(fk['references_column'])}"
                for fk in foreign_keys
            )

            line += f" FK[{references}]"

        lines.append(line)

    return "\n".join(lines)


# ============================================================
# ملخص خفيف للجداول (للـ prompts اللي مش محتاجة الـ Schema كاملة:
# التصنيف، فحص الوضوح، التوضيح). بيعرّف الـ LLM الداتابيز دي عن إيه
# من غير ما يفترض دومين معين (موسيقى مثلًا).
# ============================================================

SUMMARY_MAX_TABLES = 40
SUMMARY_MAX_COLUMNS = 10


def format_schema_summary(
    schema,
    max_tables: int = SUMMARY_MAX_TABLES,
    max_columns: int = SUMMARY_MAX_COLUMNS
) -> str:
    """
    TABLES:
    - Customer: CustomerId, FirstName, LastName, ... (+7 more)
    """

    lines = ["TABLES:"]

    table_names = list(schema.keys())

    for table_name in table_names[:max_tables]:

        names = [
            column["name"]
            for column in schema[table_name]["columns"]
        ]

        shown = ", ".join(names[:max_columns])

        extra = len(names) - max_columns

        if extra > 0:
            shown += f", ... (+{extra} more)"

        lines.append(f"- {table_name}: {shown}")

    hidden_tables = len(table_names) - max_tables

    if hidden_tables > 0:
        lines.append(f"- ... (+{hidden_tables} more tables)")

    return "\n".join(lines)
