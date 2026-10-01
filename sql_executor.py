import re

from database import execute_query

from sql_validator import (
    validate_sql
)

from authorization.authorization import (
    get_restricted_identifiers,
    strip_restricted_select_items
)


# ============================================================
# Configuration
# ============================================================

SAFETY_LIMIT = 1000


# ============================================================
# Helpers — Row Cap / Real Count
# ============================================================

def _has_limit_clause(query: str) -> bool:

    return re.search(
        r'\bLIMIT\s+\d+',
        query,
        flags=re.IGNORECASE
    ) is not None


def _clamp_limit_clause(
    query: str,
    max_limit: int
) -> str:

    def replace_limit(match):

        current_limit = int(
            match.group(1)
        )

        clamped = min(
            current_limit,
            max_limit
        )

        return f"LIMIT {clamped}"

    return re.sub(
        r'\bLIMIT\s+(\d+)',
        replace_limit,
        query,
        flags=re.IGNORECASE
    )


def _add_safety_limit(
    query: str,
    max_limit: int
) -> str:

    query = query.rstrip().rstrip(";")

    return f"{query} LIMIT {max_limit};"


def _build_count_query(query: str) -> str:

    clean_query = query.rstrip().rstrip(";")

    return (
        f"SELECT COUNT(*) FROM ({clean_query}) "
        f"AS count_subquery;"
    )


# ============================================================
# Helper — Partial Authorization
# ============================================================

def _select_list_has_items(query: str) -> bool:

    select_match = re.search(
        r'\bSELECT\b',
        query,
        flags=re.IGNORECASE
    )

    from_match = re.search(
        r'\bFROM\b',
        query,
        flags=re.IGNORECASE
    )

    if not select_match or not from_match:
        return False

    select_list = query[
        select_match.end():from_match.start()
    ].strip()

    return bool(select_list)


def _apply_authorization(
    query: str,
    user: dict
):
    """
    بتفحص الاستعلام وتتعامل مع الأعمدة الممنوعة بذكاء:

    - لو فيه عمود ممنوع بره الـ SELECT list (زي WHERE) -> رفض كامل
      (مينفعش نشيله من غير ما نغيّر معنى الاستعلام).

    - لو الأعمدة الممنوعة كلها جوه الـ SELECT list بس (عرض) ->
      نشيلها ونكمل بالباقي، ونرجّع أسماءها عشان نقولها للمستخدم.

    - لو مفيش حاجة ممنوعة خالص -> الاستعلام يعدي زي ما هو.

    بترجّع: (query معدّل أو أصلي, restricted_fields)
    """

    restricted = get_restricted_identifiers(
        query,
        user
    )

    if not restricted:
        return query, []

    blocking = [
        col for col in restricted
        if not col["select_only"]
    ]

    if blocking:

        resources_text = ", ".join(
            f'{col["table"]}.{col["column"]}'
            for col in restricted
        )

        raise PermissionError(
            "Access denied. "
            f"The requested data requires additional "
            f"permissions: {resources_text}"
        )

    new_query, removed_fields = strip_restricted_select_items(
        query,
        restricted
    )

    if not _select_list_has_items(new_query):

        resources_text = ", ".join(
            f'{col["table"]}.{col["column"]}'
            for col in restricted
        )

        raise PermissionError(
            "Access denied. "
            f"The requested data requires additional "
            f"permissions: {resources_text}"
        )

    return new_query, removed_fields


# ============================================================
# Main entry point
# ============================================================

def execute_sql(
    query: str,
    user: dict
):
    """
    بتنفذ SQL بعد التحقق والتفويض، وبترجّع:

        columns, rows, real_total, restricted_fields

    restricted_fields = قايمة بأسماء الأعمدة اللي اتشالت من
    الـ SELECT list لأنها ممنوعة (فاضية لو مفيش حاجة اتشالت).
    """

    validate_sql(
        query
    )

    # الأعمدة الممنوعة (لو فيه) بتتشال هنا قبل التنفيذ، والـ
    # query اللي هيتنفذ فعليًا ممكن يبقى مختلف عن الأصلي
    query, restricted_fields = _apply_authorization(
        query,
        user
    )

    # --------------------------------------------------------
    # الحالة 1: فيه LIMIT صريح بالفعل
    # --------------------------------------------------------

    if _has_limit_clause(query):

        safe_query = _clamp_limit_clause(
            query,
            SAFETY_LIMIT
        )

        columns, rows = execute_query(
            safe_query
        )

        real_total = len(rows)

        return columns, rows, real_total, restricted_fields

    # --------------------------------------------------------
    # الحالة 2: مفيش LIMIT خالص
    # --------------------------------------------------------

    count_query = _build_count_query(
        query
    )

    _, count_rows = execute_query(
        count_query
    )

    real_total = count_rows[0][0]

    safe_query = _add_safety_limit(
        query,
        SAFETY_LIMIT
    )

    columns, rows = execute_query(
        safe_query
    )

    return columns, rows, real_total, restricted_fields