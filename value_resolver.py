import re
from difflib import SequenceMatcher

from authorization.access_policy import (
    PUBLIC,
    get_data_sensitivity
)


# Minimum similarity required before correcting a value.
#
# 0.78 allows common typos such as:
#
# Caneda  -> Canada
# Brazill -> Brazil
# Germeny -> Germany
#
# while still requiring a reasonably strong match.
SIMILARITY_THRESHOLD = 0.78


# Minimum difference between the best and second-best matches.
#
# This prevents the resolver from making a correction
# when two database values are almost equally similar.
MIN_SCORE_MARGIN = 0.05


# أقصى عدد قيم مختلفة بنحمّلها للعمود الواحد. العمود اللي فيه أكتر
# من كده (زي IDs أو أوصاف طويلة) بنتخطاه: مفيش فايدة من تصحيح
# الإملاء عليه، وتحميله كله مكلف.
MAX_DISTINCT_VALUES = 5000


def normalize_value(value: str) -> str:
    """
    Normalize a value only for comparison.

    The original database value is never modified.

    Examples:

        "AC/DC" -> "acdc"
        "AC DC" -> "acdc"
        "Pink Floyd" -> "pinkfloyd"
    """

    value = value.lower().strip()

    # Keep only letters and numbers.
    value = re.sub(
        r"[^a-z0-9]+",
        "",
        value
    )

    return value


def _is_text_column(column_type: str) -> bool:

    column_type = str(column_type).upper()

    return any(
        marker in column_type
        for marker in ("CHAR", "TEXT")
    )


def get_distinct_values(
    db,
    table_name: str,
    column_name: str
):
    """
    Get distinct string values from a database column.

    الكاش جوه db.value_cache (مربوط بالـ Session)، فمفيش تسريب
    بين مستخدمين أو بين داتابيزات مختلفة.
    """

    key = (table_name, column_name)

    cache = db.value_cache

    if key in cache:

        return cache[key]

    # أعمدة RESTRICTED / DENIED عمرها ما بتتحمّل قيمها: التصحيح
    # الإملائي عليها مالوش لازمة، وتحميلها كان بيجيب بيانات حساسة
    # (إيميلات مثلًا) في ذاكرة الـ Session قبل ما الـ Authorization
    # تشتغل أصلًا.
    if get_data_sensitivity(
        table_name,
        column_name,
        db.policy
    ) != PUBLIC:

        cache[key] = ()

        return ()

    table_info = db.schema.get(table_name)

    column_type = None

    if table_info:

        for column in table_info["columns"]:

            if column["name"] == column_name:

                column_type = column["type"]

    # جدول/عمود مش في الـ Schema، أو عمود مش نصي: مفيش حاجة نصححها
    if column_type is None or not _is_text_column(column_type):

        cache[key] = ()

        return ()

    safe_table = table_name.replace('"', '""')
    safe_column = column_name.replace('"', '""')

    query = f'''
        SELECT DISTINCT "{safe_column}"
        FROM "{safe_table}"
        WHERE "{safe_column}" IS NOT NULL
        ORDER BY "{safe_column}"
        LIMIT {MAX_DISTINCT_VALUES + 1};
    '''

    _, rows = db.execute(query)

    if len(rows) > MAX_DISTINCT_VALUES:

        # عالي التنوع: نتخطاه
        values = ()

    else:

        values = tuple(
            row[0]
            for row in rows
            if isinstance(row[0], str)
        )

    cache[key] = values

    return values


def find_best_match(
    user_value: str,
    database_values
):
    """
    Find the closest database value.

    Returns:

        {
            "value": matched_value,
            "score": similarity_score
        }

    or:

        None

    when there is no sufficiently confident match.
    """

    normalized_user_value = normalize_value(
        user_value
    )

    if not normalized_user_value:
        return None

    scored_values = []

    for database_value in database_values:

        normalized_database_value = (
            normalize_value(
                database_value
            )
        )

        if not normalized_database_value:
            continue

        # Exact normalized match.
        #
        # Example:
        # AC DC -> AC/DC
        if (
            normalized_user_value
            == normalized_database_value
        ):

            return {
                "value": database_value,
                "score": 1.0
            }

        score = SequenceMatcher(
            None,
            normalized_user_value,
            normalized_database_value
        ).ratio()

        scored_values.append(
            (
                database_value,
                score
            )
        )

    if not scored_values:
        return None

    # Highest similarity first.
    scored_values.sort(
        key=lambda item: item[1],
        reverse=True
    )

    best_value, best_score = (
        scored_values[0]
    )

    if len(scored_values) == 1:

        second_score = 0.0

    else:

        second_score = scored_values[1][1]

    # Reject weak matches.
    if best_score < SIMILARITY_THRESHOLD:
        return None

    # Reject ambiguous matches.
    if (
        best_score - second_score
        < MIN_SCORE_MARGIN
    ):
        return None

    return {
        "value": best_value,
        "score": best_score
    }


def resolve_value(
    db,
    table_name: str,
    column_name: str,
    user_value: str
):
    """
    Resolve one value against real database values.

    Examples:

        Germeny
        ↓
        Germany

        Metalllica
        ↓
        Metallica

        Pink Floid
        ↓
        Pink Floyd

        Caneda
        ↓
        Canada
    """

    database_values = get_distinct_values(
        db,
        table_name,
        column_name
    )

    return find_best_match(
        user_value,
        database_values
    )


def resolve_sql_values(
    db,
    sql_query: str
):
    """
    Resolve string values inside SQL WHERE conditions.

    Currently supports patterns such as:

        "Customer"."Country" = 'Germeny'

        "Artist"."Name" = 'Pink Floid'

    Returns:

        corrected_sql,
        corrections
    """

    corrections = []

    pattern = re.compile(
        r'''
        (?P<table>"[^"]+")
        \s*\.\s*
        (?P<column>"[^"]+")
        \s*=\s*
        '(?P<value>(?:''|[^'])*)'
        ''',
        flags=re.VERBOSE | re.IGNORECASE
    )

    def replace_match(match):

        table_name = match.group(
            "table"
        )[1:-1]

        column_name = match.group(
            "column"
        )[1:-1]

        original_value = match.group(
            "value"
        )

        # PostgreSQL represents a single quote
        # inside a string as two single quotes.
        user_value = original_value.replace(
            "''",
            "'"
        )

        result = resolve_value(
            db=db,
            table_name=table_name,
            column_name=column_name,
            user_value=user_value
        )

        # No confident match.
        #
        # Keep the original SQL unchanged.
        if result is None:
            return match.group(0)

        resolved_value = result["value"]
        score = result["score"]

        # No correction is necessary.
        if resolved_value == user_value:
            return match.group(0)

        corrections.append(
            {
                "table": table_name,
                "column": column_name,
                "original": user_value,
                "resolved": resolved_value,
                "score": round(
                    score,
                    4
                )
            }
        )

        # Escape single quotes for PostgreSQL.
        escaped_value = resolved_value.replace(
            "'",
            "''"
        )

        return (
            f'{match.group("table")}.'
            f'{match.group("column")} = '
            f"'{escaped_value}'"
        )

    corrected_sql = pattern.sub(
        replace_match,
        sql_query
    )

    return corrected_sql, corrections