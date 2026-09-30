import re

from authorization.access_policy import (
    get_data_sensitivity,
    is_access_allowed
)


# ============================================================
# Patterns
# ============================================================

QUALIFIED_PATTERN = re.compile(
    r'"(?P<table>[^"]+)"\s*\.\s*"(?P<column>[^"]+)"',
    flags=re.IGNORECASE
)

# بيمسك أي "identifier" لوحده بين quotes (ممكن يكون table أو column)
BARE_IDENTIFIER_PATTERN = re.compile(
    r'"(?P<name>[^"]+)"'
)

# بيمسك أسماء الجداول المذكورة في FROM أو JOIN
FROM_JOIN_PATTERN = re.compile(
    r'\b(?:FROM|JOIN)\s+"(?P<table>[^"]+)"',
    flags=re.IGNORECASE
)


# ============================================================
# استخراج الأعمدة المؤهلة (Table.Column) — زي ما كان بالظبط
# ============================================================

def extract_qualified_columns(
    sql_query: str
):

    matches = QUALIFIED_PATTERN.finditer(
        sql_query
    )

    identifiers = []

    for match in matches:

        identifiers.append(
            {
                "table": match.group("table"),
                "column": match.group("column")
            }
        )

    return identifiers


# ============================================================
# جديد: استخراج أسماء الجداول من FROM/JOIN
# ============================================================

def extract_referenced_tables(
    sql_query: str
):

    matches = FROM_JOIN_PATTERN.finditer(
        sql_query
    )

    return list(
        {
            match.group("table")
            for match in matches
        }
    )


# ============================================================
# جديد: استخراج الأعمدة "الغير مؤهلة" (من غير Table.)
# ============================================================

def extract_bare_identifiers(
    sql_query: str,
    referenced_tables: list
):

    # --------------------------------------------------------
    # أولاً: نحدد أماكن (spans) كل الـ Table.Column المؤهلة
    # عشان منحسبهاش تاني كـ bare identifiers
    # --------------------------------------------------------

    qualified_spans = [
        match.span()
        for match in QUALIFIED_PATTERN.finditer(sql_query)
    ]

    def is_inside_qualified_pair(position):

        for start, end in qualified_spans:

            if start <= position < end:
                return True

        return False

    bare_identifiers = []

    for match in BARE_IDENTIFIER_PATTERN.finditer(sql_query):

        # لو الـ identifier ده جزء من زوج مؤهل (Table.Column) بالفعل، تجاهله
        if is_inside_qualified_pair(match.start()):
            continue

        name = match.group("name")

        # لو الاسم ده هو اسم جدول (موجود في FROM/JOIN)، فهو Table مش Column
        if name in referenced_tables:
            continue

        bare_identifiers.append(name)

    return bare_identifiers


# ============================================================
# authorize_sql — النسخة المقوّاة
# ============================================================

def authorize_sql(
    sql_query: str,
    user: dict
):

    if not isinstance(user, dict):
        raise ValueError("Invalid user identity.")

    role = user.get("role")

    if not role:
        raise ValueError("User role is missing.")

    # --------------------------------------------------------
    # 1) الأعمدة المؤهلة (Table.Column) — زي ما كان
    # --------------------------------------------------------

    identifiers = extract_qualified_columns(
        sql_query
    )

    # --------------------------------------------------------
    # 2) جديد: الأعمدة الغير مؤهلة — بنتأكد منها ضد كل
    #    الجداول المذكورة في الاستعلام (Conservative check)
    # --------------------------------------------------------

    referenced_tables = extract_referenced_tables(
        sql_query
    )

    bare_columns = extract_bare_identifiers(
        sql_query=sql_query,
        referenced_tables=referenced_tables
    )

    for bare_column in bare_columns:

        for table_name in referenced_tables:

            identifiers.append(
                {
                    "table": table_name,
                    "column": bare_column
                }
            )

    # --------------------------------------------------------
    # 3) التحقق من كل الـ identifiers (المؤهلة + الغير مؤهلة)
    # --------------------------------------------------------

    restricted_resources = []

    for identifier in identifiers:

        table_name = identifier["table"]
        column_name = identifier["column"]

        sensitivity = get_data_sensitivity(
            table_name=table_name,
            column_name=column_name
        )

        allowed = is_access_allowed(
            role=role,
            sensitivity=sensitivity
        )

        if not allowed:

            restricted_resources.append(
                {
                    "table": table_name,
                    "column": column_name,
                    "sensitivity": sensitivity
                }
            )

    if restricted_resources:

        resources_text = ", ".join(
            [
                f'{item["table"]}.{item["column"]}'
                for item in restricted_resources
            ]
        )

        raise PermissionError(
            "Access denied. "
            f"The requested data requires additional "
            f"permissions: {resources_text}"
        )

    return True