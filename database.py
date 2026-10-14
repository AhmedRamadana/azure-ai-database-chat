"""
database.py

تنفيذ الاستعلامات على Engine بيتم تمريره (مفيش Engine Global ولا
قراءة من .env وقت الـ import). كل Session ليها Engine خاص بيها
(انظر db_context.py).

كل استعلام بيتنفذ جوه transaction واحدة، والـ Dialect (dialects.py)
هو اللي بيجهّزها حسب نوع الداتابيز:

    PostgreSQL: SET TRANSACTION READ ONLY + statement_timeout + search_path
                (SET LOCAL جوه الـ transaction بدل connection options لأن
                الـ poolers زي Supabase / Neon / PgBouncer بترفض الـ options)
    MySQL:      ANSI_QUOTES + READ ONLY + max_execution_time
    SQLite:     الملف مفتوح mode=ro + PRAGMA query_only + progress handler
"""

from sqlalchemy import text

from dialects import (
    DEFAULT_STATEMENT_TIMEOUT_MS,
    get_dialect,
    is_valid_schema_name
)


# اسم قديم (اتنقل لـ dialects.py)
is_valid_pg_schema_name = is_valid_schema_name


def execute_query(
    engine,
    query: str,
    pg_schema: str = "public",
    statement_timeout_ms: int = DEFAULT_STATEMENT_TIMEOUT_MS,
    dialect=None
):
    """
    بترجّع (columns, rows).

    dialect: نوع الداتابيز (None -> PostgreSQL). هو اللي بيحدد إزاي
    بنقفل الكتابة ونحط الـ timeout قبل أي استعلام.
    """

    dialect = dialect or get_dialect()

    with engine.begin() as connection:

        dialect.prepare_connection(
            connection,
            pg_schema,
            int(statement_timeout_ms)
        )

        result = connection.execute(
            text(query)
        )

        rows = result.fetchall()

        columns = list(result.keys())

    return columns, rows
