import re

from schema import get_database_schema


FORBIDDEN_KEYWORDS = [

    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "GRANT",
    "REVOKE"

]


def validate_sql(query: str) -> bool:

    query = query.strip()

    if not query:

        raise ValueError(
            "Generated SQL is empty."
        )

    normalized_query = query.upper()

    # --------------------------------------------------
    # 1. Only SELECT queries are allowed
    # --------------------------------------------------

    if not normalized_query.startswith("SELECT"):

        raise ValueError(
            "Only SELECT queries are allowed."
        )

    # --------------------------------------------------
    # 2. Block dangerous SQL keywords
    # --------------------------------------------------

    for keyword in FORBIDDEN_KEYWORDS:

        pattern = rf"\b{keyword}\b"

        if re.search(
            pattern,
            normalized_query
        ):

            raise ValueError(
                f"Unsafe SQL detected: {keyword}"
            )

    # --------------------------------------------------
    # 3. Validate SQL completeness
    # --------------------------------------------------

    validate_sql_structure(
        query
    )

    # --------------------------------------------------
    # 4. Validate database schema
    # --------------------------------------------------

    validate_schema_identifiers(
        query
    )

    return True


def validate_sql_structure(query: str) -> bool:

    normalized_query = query.upper().strip()

    # --------------------------------------------------
    # SELECT queries that access Chinook tables
    # must contain FROM.
    #
    # Example of invalid query:
    #
    # SELECT "Artist"."Name"
    #
    # Correct:
    #
    # SELECT "Artist"."Name"
    # FROM "Artist"
    # --------------------------------------------------

    if not re.search(
        r"\bFROM\b",
        normalized_query
    ):

        raise ValueError(
            "SELECT query must contain a FROM clause."
        )

    # --------------------------------------------------
    # Validate that FROM is followed by a table
    # --------------------------------------------------

    from_match = re.search(
        r'\bFROM\s+"([^"]+)"',
        query,
        flags=re.IGNORECASE
    )

    if not from_match:

        raise ValueError(
            "FROM clause must reference a valid table."
        )

    return True


def validate_schema_identifiers(query: str) -> bool:

    schema = get_database_schema()

    valid_tables = set(
        schema.keys()
    )

    valid_columns = set()

    for table_info in schema.values():

        for column in table_info["columns"]:

            valid_columns.add(
                column["name"]
            )

    # --------------------------------------------------
    # Extract aliases created using AS
    # --------------------------------------------------

    aliases = set(

        re.findall(
            r'\bAS\s+"([^"]+)"',
            query,
            flags=re.IGNORECASE
        )

    )

    # --------------------------------------------------
    # Validate table names after FROM / JOIN
    # --------------------------------------------------

    table_matches = re.findall(

        r'\b(?:FROM|JOIN)\s+"([^"]+)"',

        query,

        flags=re.IGNORECASE

    )

    for table_name in table_matches:

        if table_name not in valid_tables:

            raise ValueError(
                f"Unknown table: {table_name}"
            )

    # --------------------------------------------------
    # Validate qualified references:
    #
    # "Table"."Column"
    # --------------------------------------------------

    qualified_matches = re.findall(

        r'"([^"]+)"\s*\.\s*"([^"]+)"',

        query

    )

    for table_name, column_name in qualified_matches:

        if table_name not in valid_tables:

            raise ValueError(
                f"Unknown table: {table_name}"
            )

        table_columns = {

            column["name"]

            for column in schema[table_name]["columns"]

        }

        if column_name not in table_columns:

            raise ValueError(
                f"Unknown column: "
                f"{table_name}.{column_name}"
            )

    # --------------------------------------------------
    # Validate standalone quoted identifiers
    #
    # Ignore:
    # - table names
    # - qualified identifiers
    # - aliases
    # --------------------------------------------------

    quoted_identifiers = re.findall(

        r'"([^"]+)"',

        query

    )

    for identifier in quoted_identifiers:

        if identifier in valid_tables:

            continue

        if identifier in aliases:

            continue

        if identifier in valid_columns:

            continue

        # --------------------------------------------------
        # If identifier appears as part of:
        #
        # "Table"."Column"
        #
        # it was already validated above.
        # --------------------------------------------------

        if re.search(

            rf'"{re.escape(identifier)}"\s*\.',

            query

        ):

            continue

        raise ValueError(
            f"Unknown identifier: {identifier}"
        )

    return True


def clean_sql(query: str) -> str:

    query = query.strip()

    # --------------------------------------------------
    # Remove Markdown code fences
    # --------------------------------------------------

    if query.startswith("```"):

        lines = query.splitlines()

        if lines[0].startswith("```"):

            lines = lines[1:]

        if lines and lines[-1].strip() == "```":

            lines = lines[:-1]

        query = "\n".join(
            lines
        )

    # --------------------------------------------------
    # Remove optional "sql" prefix
    # --------------------------------------------------

    if query.lower().startswith("sql"):

        query = query[3:].strip()

    return query.strip()