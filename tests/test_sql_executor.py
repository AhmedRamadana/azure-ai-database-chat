"""
تأكيد إن الـ executor بيرفض أي استعلام مش SELECT قبل ما يوصل للداتابيز.

التشغيل (من روت المشروع):

    python -m tests.test_sql_executor
"""

from sql_executor import execute_sql
from tests.helpers import get_demo_db, get_user


query = '''
DROP TABLE "Customer";
'''


try:

    columns, rows, real_total, restricted = execute_sql(
        query,
        get_user("USER"),
        get_demo_db()
    )

    print("FAIL: a DROP TABLE statement was executed")

except ValueError as error:

    print("PASS: rejected before reaching the database")
    print(error)
