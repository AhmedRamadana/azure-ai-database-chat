import re
from difflib import SequenceMatcher
from functools import lru_cache

from sqlalchemy import text

from database import engine
from schema import get_database_schema


# =========================================================
# Configuration
# =========================================================

MIN_MATCH_LENGTH = 3

FUZZY_MATCH_THRESHOLD = 0.80


# =========================================================
# Text Normalization
# =========================================================

def normalize_text(value: str) -> str:

    value = value.lower().strip()

    # Remove spaces and punctuation.
    # Example:
    #
    # AC/DC
    # AC DC
    #
    # both become:
    #
    # acdc

    value = re.sub(
        r"[^a-z0-9]+",
        "",
        value
    )

    return value


# =========================================================
# Build Entity Catalog
# =========================================================

@lru_cache(maxsize=1)
def build_entity_catalog():

    schema = get_database_schema()

    catalog = []

    with engine.connect() as connection:

        for table_name, table_info in schema.items():

            for column in table_info["columns"]:

                column_name = column["name"]

                column_type = str(
                    column["type"]
                ).upper()


                # We are interested mainly in
                # textual columns.

                if not any(
                    data_type in column_type
                    for data_type in [
                        "CHAR",
                        "TEXT",
                        "VARCHAR"
                    ]
                ):

                    continue


                # Table and column names come
                # directly from the inspected schema.

                safe_table = (
                    table_name.replace(
                        '"',
                        '""'
                    )
                )

                safe_column = (
                    column_name.replace(
                        '"',
                        '""'
                    )
                )


                query = text(
                    f'''
                    SELECT DISTINCT "{safe_column}"
                    FROM "{safe_table}"
                    WHERE "{safe_column}" IS NOT NULL
                    '''
                )


                try:

                    result = connection.execute(
                        query
                    )

                    for row in result:

                        value = row[0]

                        if not isinstance(
                            value,
                            str
                        ):

                            continue

                        value = value.strip()

                        if not value:

                            continue

                        catalog.append(
                            {
                                "table": table_name,
                                "column": column_name,
                                "value": value
                            }
                        )

                except Exception:

                    # If a particular column cannot
                    # be read, skip it and continue.

                    continue

    return catalog


# =========================================================
# Find Best Entity Match
# =========================================================

def find_entity_match(
    value: str,
    catalog: list
):

    normalized_value = normalize_text(
        value
    )

    if len(normalized_value) < MIN_MATCH_LENGTH:

        return None


    best_match = None
    best_score = 0.0


    for entity in catalog:

        entity_value = entity["value"]

        normalized_entity = normalize_text(
            entity_value
        )


        # Exact normalized match.
        #
        # AC DC
        # AC/DC
        #
        # both become:
        # acdc

        if normalized_value == normalized_entity:

            return {
                **entity,
                "score": 1.0
            }


        score = SequenceMatcher(
            None,
            normalized_value,
            normalized_entity
        ).ratio()


        if score > best_score:

            best_score = score

            best_match = entity


    if (
        best_match is not None
        and best_score >= FUZZY_MATCH_THRESHOLD
    ):

        return {
            **best_match,
            "score": best_score
        }


    return None

from prompts.entity_prompt import (
    build_entity_prompt
)

from models.model_manager import (
    get_model
)


def extract_entity_candidates(
    user_question: str,
    model_name: str = "nano"
):

    prompt = build_entity_prompt(
        user_question
    )

    model = get_model(
        model_name
    )

    response = model(
        prompt
    )

    response = response.strip()

    if not response:

        return []

    if response.upper() == "NONE":

        return []

    candidates = []

    for line in response.splitlines():

        line = line.strip()

        if not line:

            continue

        candidates.append(
            line
        )

    return candidates


def resolve_entities(
    user_question: str,
    model_name: str = "nano"
):

    candidates = extract_entity_candidates(
        user_question=user_question,
        model_name=model_name
    )

    if not candidates:

        return user_question


    catalog = build_entity_catalog()

    resolved_question = user_question


    for candidate in candidates:

        match = find_entity_match(
            value=candidate,
            catalog=catalog
        )

        if match is None:

            continue


        original_value = candidate

        database_value = match["value"]


        if original_value == database_value:

            continue


        resolved_question = (
            resolved_question.replace(
                original_value,
                database_value
            )
        )


    return resolved_question