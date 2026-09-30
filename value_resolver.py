import re
from difflib import SequenceMatcher
from functools import lru_cache

from database import execute_query


# Minimum similarity required before correcting a value.
#
# 0.80 allows common typos such as:
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


@lru_cache(maxsize=32)
def get_distinct_values(
    table_name: str,
    column_name: str
):
    """
    Get distinct string values from a database column.

    Results are cached so the same database column
    is not queried repeatedly.
    """

    query = f'''
        SELECT DISTINCT "{column_name}"
        FROM "{table_name}"
        WHERE "{column_name}" IS NOT NULL
        ORDER BY "{column_name}";
    '''

    columns, rows = execute_query(query)

    values = []

    for row in rows:

        value = row[0]

        if isinstance(value, str):
            values.append(value)

    return tuple(values)


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
        table_name,
        column_name
    )

    return find_best_match(
        user_value,
        database_values
    )


def resolve_sql_values(
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

    Example:

        (
            corrected_sql,
            [
                {
                    "table": "Customer",
                    "column": "Country",
                    "original": "Germeny",
                    "resolved": "Germany",
                    "score": 0.8571
                }
            ]
        )
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
