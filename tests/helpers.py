"""
helpers.py

مساعدات مشتركة للاختبارات اللي بتشتغل على الداتابيز التجريبية (Chinook).

    from tests.helpers import get_demo_db, get_user

get_demo_db(): اتصال واحد بيتعمل مرة واحدة ويتشارك بين كل الاختبارات
في نفس العملية (بيستخدم DATABASE_URL من .env).
get_user(role): يوزر تجريبي بالـ role المطلوب.

الاختبارات دي بتشتغل من روت المشروع:

    python -m tests.test_pipeline
"""

import os
import sys

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from auth.mock_auth import get_mock_user

_demo_db = None


def get_demo_db():

    global _demo_db

    if _demo_db is None:

        from db_context import connect_demo

        _demo_db = connect_demo()

    return _demo_db


def get_user(role: str = "USER"):

    return get_mock_user(
        user_id=f"{role.lower()}_test",
        role=role
    )
