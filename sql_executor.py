import re

from sql_validator import (
    validate_sql
)

from sql_scan import (
    mask_sql,
    paren_depths
)

from authorization.authorization import (
    apply_column_authorization
)


# ============================================================
# Configuration
# ============================================================

SAFETY_LIMIT = 1000


# ============================================================
# Helpers — Row Cap / Real Count
# ============================================================

def _top_level_limits(query: str):
    """
    كل LIMIT على المستوى الأساسي للاستعلام (مش جوه subquery ولا
    جوه string).
    """

    structure, _, _ = mask_sql(query)

    depths = paren_depths(structure)

    return [
        match
        for match in re.finditer(
            r"\bLIMIT\s+(\d+)",
            structure,
            flags=re.IGNORECASE
        )
        if depths[match.start()] == 0
    ]


def _has_limit_clause(query: str) -> bool:

    return bool(
        _top_level_limits(query)
    )


def _clamp_limit_clause(
    query: str,
    max_limit: int
) -> str:

    for match in reversed(
        _top_level_limits(query)
    ):

        start, end = match.span(1)

        clamped = min(
            int(match.group(1)),
            max_limit
        )

        query = (
            query[:start]
            + str(clamped)
            + query[end:]
        )

    return query


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
# Main entry point
# ============================================================

def execute_sql(
    query: str,
    user: dict,
    db
):
    """
    بتنفذ SQL بعد التحقق والتفويض، وبترجّع:

        columns, rows, real_total, restricted_fields

    db: الـ DBContext بتاع الـ Session (الـ Schema والاتصال منه).

    restricted_fields = قايمة بأسماء الأعمدة اللي اتشالت من
    الـ SELECT list لأنها ممنوعة على المستخدم (فاضية لو مفيش).
    """

    validate_sql(
        query,
        db.schema,
        db.dialect
    )

    # توسيع الـ * + شيل الأعمدة الممنوعة (أو رفض كامل). الاستعلام
    # اللي هيتنفذ فعليًا ممكن يبقى مختلف عن الأصلي.
    query, restricted_fields = apply_column_authorization(
        query,
        user,
        db.schema,
        db.policy
    )

    # --------------------------------------------------------
    # الحالة 1: فيه LIMIT صريح على المستوى الأساسي
    # --------------------------------------------------------

    if _has_limit_clause(query):

        safe_query = _clamp_limit_clause(
            query,
            SAFETY_LIMIT
        )

        columns, rows = db.execute(
            safe_query
        )

        real_total = len(rows)

        return columns, rows, real_total, restricted_fields

    # --------------------------------------------------------
    # الحالة 2: مفيش LIMIT خالص
    # --------------------------------------------------------

    # ملحوظة أمنية: count_query مبني بالكامل حوالين الاستعلام اللي
    # عدّى الفحص فوق، ومفيهوش أي identifier جديد.
    count_query = _build_count_query(
        query
    )

    _, count_rows = db.execute(
        count_query
    )

    real_total = count_rows[0][0]

    safe_query = _add_safety_limit(
        query,
        SAFETY_LIMIT
    )

    columns, rows = db.execute(
        safe_query
    )

    return columns, rows, real_total, restricted_fields