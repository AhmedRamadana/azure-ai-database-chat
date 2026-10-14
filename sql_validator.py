import re

from sql_scan import mask_sql

from dialects import get_dialect


# كلمات الكتابة/التعديل. بنفحصها على النص الخام (حتى جوه الـ strings)
# عن قصد: ده بيمنع الدوال اللي بتنفذ SQL مكتوب كنص، وبنقبل إن كلمة
# زي 'Drop' جوه اسم أغنية تترفض (False Positive مقبول).
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


# كلمات بنفحصها بره الـ strings بس (عشان اسم أغنية زي 'Into the Wild'
# ميترفضش). SELECT ... INTO بينشئ جدول جديد، يعني كتابة فعلية.
FORBIDDEN_STRUCTURAL_KEYWORDS = [

    "INTO",
    "COPY",
    "EXECUTE",
    "CALL"

]


# دوال وأسماء خطرة: بقت جوه كل Dialect (dialects.py) لأنها بتختلف من نوع
# لنوع. ده الـ pattern بتاع PostgreSQL (للتوافق مع الكود القديم).
FORBIDDEN_NAMES_PATTERN = get_dialect("postgresql").forbidden_names


def validate_sql_safety(query: str, dialect=None) -> bool:
    """
    فحوصات أمان مستقلة عن الـ Schema. dialect=None -> PostgreSQL.
    """

    dialect = dialect or get_dialect()

    # --------------------------------------------------
    # 1. حروف بتتلاعب بتحليلنا للنص
    # --------------------------------------------------

    if "\\" in query:

        raise ValueError(
            "Backslashes are not allowed in SQL."
        )

    if re.search(r"\$[A-Za-z_]*\$", query):

        raise ValueError(
            "Dollar-quoted strings are not allowed."
        )

    structure, no_strings, balanced = mask_sql(
        query
    )

    if not balanced:

        raise ValueError(
            "SQL contains an unclosed quote."
        )

    if '""' in no_strings:

        raise ValueError(
            "Escaped quotes inside identifiers are not allowed."
        )

    # --------------------------------------------------
    # 2. تعليقات
    # --------------------------------------------------

    if "--" in structure or "/*" in structure:

        raise ValueError(
            "SQL comments are not allowed."
        )

    # --------------------------------------------------
    # 3. statement واحد بس (الفاصلة المنقوطة الأخيرة مسموحة)
    # --------------------------------------------------

    body = structure.rstrip()

    if body.endswith(";"):

        body = body[:-1]

    if ";" in body:

        raise ValueError(
            "Multiple SQL statements are not allowed."
        )

    # --------------------------------------------------
    # 4. كلمات الكتابة (على النص الخام)
    # --------------------------------------------------

    upper_query = query.upper()

    for keyword in FORBIDDEN_KEYWORDS:

        if re.search(
            rf"\b{keyword}\b",
            upper_query
        ):

            raise ValueError(
                f"Unsafe SQL detected: {keyword}"
            )

    # --------------------------------------------------
    # 5. كلمات بنية خطرة (بره الـ strings)
    # --------------------------------------------------

    for keyword in FORBIDDEN_STRUCTURAL_KEYWORDS:

        if re.search(
            rf"\b{keyword}\b",
            structure,
            flags=re.IGNORECASE
        ):

            raise ValueError(
                f"Unsafe SQL detected: {keyword}"
            )

    # --------------------------------------------------
    # 6. دوال وأسماء خطرة
    # --------------------------------------------------

    dialect.validate_structure(structure)

    return True


def validate_sql(query: str, schema: dict, dialect=None) -> bool:
    """
    schema: الـ Schema بتاعة الـ Session (db.schema). بقت parameter
    بدل ما نقراها من الداتابيز، عشان كل Session ليها داتابيز مختلفة.

    dialect: نوع الداتابيز (db.dialect). None -> PostgreSQL.
    """

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
    # 2. Safety checks (keywords, functions, statements...)
    # --------------------------------------------------

    validate_sql_safety(
        query,
        dialect
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
        query,
        schema
    )

    return True


def validate_sql_structure(query: str) -> bool:

    normalized_query = query.upper().strip()

    # --------------------------------------------------
    # SELECT queries that read from tables
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


def validate_schema_identifiers(
    query: str,
    schema: dict
) -> bool:

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
    # Alias shadowing:
    #
    #   FROM "Employee" AS "Customer"
    #
    # الـ alias ده بيخلّي "Customer"."City" يتقري كأنه Customer.City
    # (PUBLIC) مع إنه فعليًا Employee.City (RESTRICTED). الـ
    # Authorization بتحل الأسماء بالنص، فبنرفض أي alias بيستخدم اسم
    # جدول تاني.
    # --------------------------------------------------

    alias_bindings = re.findall(

        r'\b(?:FROM|JOIN)\s+"([^"]+)"\s+(?:AS\s+)?"([^"]+)"'
        r'|,\s*"([^"]+)"\s+(?:AS\s+)?"([^"]+)"',

        query,

        flags=re.IGNORECASE

    )

    for from_table, from_alias, comma_table, comma_alias in alias_bindings:

        table_name = from_table or comma_table

        alias = from_alias or comma_alias

        if (
            table_name in valid_tables
            and alias in valid_tables
            and alias != table_name
        ):

            raise ValueError(
                f"A table alias cannot reuse another table's name: "
                f"{alias}"
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