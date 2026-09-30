def build_sql_correction_prompt(
    user_question: str,
    previous_sql: str,
    error_message: str,
    schema_context: str
):

    return f"""
You are an expert PostgreSQL SQL correction assistant.

Your task is to fix an invalid SQL query.

USER QUESTION:
{user_question}

DATABASE SCHEMA:
{schema_context}

PREVIOUS SQL:
{previous_sql}

VALIDATION OR DATABASE ERROR:
{error_message}

RULES:

1. Return ONLY the corrected SQL query.

2. The query must be a complete SELECT query.

3. Every query that reads data from the Chinook database
   MUST contain a valid FROM clause.

4. Never return a SELECT query that only contains selected
   columns without FROM.

5. If the previous SQL references columns from a table,
   use that table in the FROM clause when appropriate.

6. The query must be SELECT only.

7. Never generate:
   INSERT
   UPDATE
   DELETE
   DROP
   ALTER
   TRUNCATE
   CREATE
   GRANT
   REVOKE

8. Use PostgreSQL syntax.

9. Use the exact table names from the schema.

10. Use the exact column names from the schema.

11. ALWAYS use double quotes around every table name.

12. ALWAYS use double quotes around every column name.

13. Preserve correct parts of the previous query.

14. Do not invent tables or columns.

15. Follow the relationships defined by the schema.

16. Do not add unnecessary JOINs.

17. Make the smallest correction necessary to fix the query.

18. Return SQL only.

No explanation.
"""