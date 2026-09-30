import re

from database import execute_query

from sql_validator import (
    validate_sql
)

from authorization.authorization import (
    authorize_sql
)


# ============================================================
# Configuration
# ============================================================

# أقصى عدد صف نجيبه فعليًا من الداتابيز في أي استعلام مفيهوش
# LIMIT صريح، أو نقلل أي LIMIT أكبر منه (Safety Net)
SAFETY_LIMIT = 1000


# ============================================================
# Helpers
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
    """
    لو فيه LIMIT في الاستعلام وقيمته أكبر من max_limit، بنقللها.
    لو أقل من أو يساوي max_limit، بنسيبها زي ما هي — نية الـ Model
    (زي "top 10") محترمة.
    """

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
    """
    لو الاستعلام مفيهوش LIMIT خالص، نضيف واحد كـ Safety Net.
    """

    query = query.rstrip().rstrip(";")

    return f"{query} LIMIT {max_limit};"


def _build_count_query(query: str) -> str:
    """
    بيبني استعلام COUNT(*) حوالين الاستعلام الأصلي (من غير أي
    LIMIT) عشان نعرف العدد الحقيقي الكامل للنتائج المطابقة، قبل
    ما نقصّه بأي Limit.
    """

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
    user: dict
):
    """
    بتنفذ SQL بعد التحقق والتفويض، وبترجّع:

        columns, rows, real_total

    real_total = العدد الحقيقي الكامل للنتائج المطابقة، حتى لو
    rows نفسها اتقصت لسقف الأمان (SAFETY_LIMIT).
    """

    validate_sql(
        query
    )

    authorize_sql(
        sql_query=query,
        user=user
    )

    # --------------------------------------------------------
    # الحالة 1: فيه LIMIT صريح بالفعل — نية واضحة (زي "top 10")
    # نحترمها، بس نتأكد إنها مش كبيرة جدًا
    # --------------------------------------------------------

    if _has_limit_clause(query):

        safe_query = _clamp_limit_clause(
            query,
            SAFETY_LIMIT
        )

        columns, rows = execute_query(
            safe_query
        )

        # الـ LIMIT كانت مقصودة، فـ "العدد الحقيقي" هو نفسه
        # عدد الصفوف اللي رجعت فعليًا
        real_total = len(rows)

        return columns, rows, real_total

    # --------------------------------------------------------
    # الحالة 2: مفيش LIMIT خالص — محتاجين العدد الحقيقي الكامل
    # قبل ما نقص بأي حاجة
    # --------------------------------------------------------

    count_query = _build_count_query(
        query
    )

    # ملحوظة أمنية: مش محتاجين نعيد validate_sql/authorize_sql
    # هنا، لأن count_query مبني بالكامل حوالين نفس الاستعلام
    # الأصلي اللي اتفحص فعلاً فوق — مفيش أي identifier جديد
    # اتضاف، بس Wrapping بس (COUNT + subquery alias بسيط)
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

    return columns, rows, real_total