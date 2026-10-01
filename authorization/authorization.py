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

BARE_IDENTIFIER_PATTERN = re.compile(
    r'"(?P<name>[^"]+)"'
)

FROM_JOIN_PATTERN = re.compile(
    r'\b(?:FROM|JOIN)\s+"(?P<table>[^"]+)"',
    flags=re.IGNORECASE
)


# ============================================================
# استخراج الأعمدة (زي ما كان، من غير تعديل)
# ============================================================

def extract_qualified_columns(
    sql_query: str
):

    matches = QUALIFIED_PATTERN.finditer(
        sql_query
    )

    return [
        {
            "table": match.group("table"),
            "column": match.group("column")
        }
        for match in matches
    ]


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


def extract_bare_identifiers(
    sql_query: str,
    referenced_tables: list
):

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

        if is_inside_qualified_pair(match.start()):
            continue

        name = match.group("name")

        if name in referenced_tables:
            continue

        bare_identifiers.append(name)

    return bare_identifiers


# ============================================================
# authorize_sql — النسخة الأصلية (Full block)
#
# لسه موجودة ومستخدمة زي ما هي — أي حد يستدعيها لسه هياخد
# رفض كامل لو فيه أي عمود ممنوع. مفيدة لما مش عايزين/مش قادرين
# نعمل Partial Authorization (زي في الأسئلة المتعددة المستقلة).
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

    restricted = get_restricted_identifiers(
        sql_query,
        user
    )

    if restricted:

        resources_text = ", ".join(
            [
                f'{item["table"]}.{item["column"]}'
                for item in restricted
            ]
        )

        raise PermissionError(
            "Access denied. "
            f"The requested data requires additional "
            f"permissions: {resources_text}"
        )

    return True


# ============================================================
# جديد: get_restricted_identifiers
#
# بترجّع كل الأعمدة الممنوعة في الاستعلام، مع تحديد هل كل واحد
# منها موجود في الـ SELECT list بس (قابل للإزالة) أو في مكان
# تاني زي WHERE/ORDER BY (مش قابل للإزالة بأمان)
# ============================================================

def get_restricted_identifiers(
    sql_query: str,
    user: dict
):

    role = user.get("role")

    identifiers = extract_qualified_columns(
        sql_query
    )

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

    # نحدد نهاية الـ SELECT list (أول FROM في الاستعلام)
    from_match = re.search(
        r'\bFROM\b',
        sql_query,
        flags=re.IGNORECASE
    )

    select_clause_end = (
        from_match.start()
        if from_match
        else len(sql_query)
    )

    restricted = []
    seen = set()

    for identifier in identifiers:

        key = (identifier["table"], identifier["column"])

        if key in seen:
            continue

        seen.add(key)

        sensitivity = get_data_sensitivity(
            table_name=identifier["table"],
            column_name=identifier["column"]
        )

        if is_access_allowed(role, sensitivity):
            continue

        # هل العمود ده بيظهر جوه الـ SELECT list؟
        qualified_pattern = (
            rf'"{re.escape(identifier["table"])}"'
            rf'\s*\.\s*"{re.escape(identifier["column"])}"'
        )

        bare_pattern = (
            rf'"{re.escape(identifier["column"])}"'
        )

        select_text = sql_query[:select_clause_end]

        appears_in_select = bool(
            re.search(qualified_pattern, select_text)
            or re.search(bare_pattern, select_text)
        )

        appears_elsewhere = bool(
            re.search(
                qualified_pattern,
                sql_query[select_clause_end:]
            )
            or re.search(
                bare_pattern,
                sql_query[select_clause_end:]
            )
        )

        restricted.append(
            {
                "table": identifier["table"],
                "column": identifier["column"],
                "sensitivity": sensitivity,
                # قابل للإزالة بأمان بس لو ظهر في الـ SELECT
                # ومفيش ظهور ليه برة (WHERE/ORDER BY/...)
                "select_only": (
                    appears_in_select
                    and not appears_elsewhere
                )
            }
        )

    return restricted


# ============================================================
# جديد: strip_restricted_select_items
#
# بتشيل من الـ SELECT list أي عمود ممنوع (اللي select_only=True
# بس)، وترجّع الاستعلام الجديد + قايمة الأعمدة اللي اتشالت
# ============================================================

def _split_top_level_commas(text: str):

    items = []
    depth = 0
    current = ""

    for char in text:

        if char == "(":
            depth += 1

        elif char == ")":
            depth -= 1

        if char == "," and depth == 0:

            items.append(current)
            current = ""

        else:

            current += char

    if current.strip():
        items.append(current)

    return items


def strip_restricted_select_items(
    sql_query: str,
    restricted_columns: list
):

    select_match = re.search(
        r'\bSELECT\b',
        sql_query,
        flags=re.IGNORECASE
    )

    from_match = re.search(
        r'\bFROM\b',
        sql_query,
        flags=re.IGNORECASE
    )

    if not select_match or not from_match:
        return sql_query, []

    select_list_text = sql_query[
        select_match.end():from_match.start()
    ]

    items = _split_top_level_commas(
        select_list_text
    )

    removed_fields = []
    kept_items = []

    strippable = [
        col for col in restricted_columns
        if col.get("select_only")
    ]

    for item in items:

        item_stripped = item.strip()

        matched_column = None

        for col in strippable:

            qualified_pattern = (
                rf'"{re.escape(col["table"])}"'
                rf'\s*\.\s*"{re.escape(col["column"])}"'
            )

            bare_pattern = (
                rf'^"{re.escape(col["column"])}"'
            )

            if (
                re.search(qualified_pattern, item_stripped)
                or re.match(bare_pattern, item_stripped)
            ):

                matched_column = col
                break

        if matched_column:

            removed_fields.append(
                f'{matched_column["table"]}.'
                f'{matched_column["column"]}'
            )

        else:

            kept_items.append(item_stripped)

    new_select_list = ", ".join(kept_items)

    new_query = (
        sql_query[:select_match.end()]
        + " " + new_select_list + " "
        + sql_query[from_match.start():]
    )

    return new_query, removed_fields