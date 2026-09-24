from database import execute_query
from sql_validator import validate_sql


def execute_sql(query: str):

    validate_sql(query)

    columns, rows = execute_query(query)

    return columns, rows