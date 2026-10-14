"""
اختبارات معالجة الأخطاء والـ logging والإعدادات (من غير LLM ولا داتابيز).

التشغيل (من روت المشروع):

    python -m tests.test_errors
"""

import importlib
import io
import logging
import os
import sys

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

import httpx
import openai
from sqlalchemy.exc import OperationalError

import errors
import observability

RESULTS = []


def check(name, condition):

    RESULTS.append(bool(condition))

    print(("PASS: " if condition else "FAIL: ") + name)


REQUEST = httpx.Request("POST", "https://example.invalid/openai")


def response(status):

    return httpx.Response(status, request=REQUEST)


SECRET = "SECRET-PASSWORD-123 SELECT \"Email\" FROM \"Customer\""

CASES = {
    "LLM_TIMEOUT": openai.APITimeoutError(request=REQUEST),
    "LLM_RATE_LIMIT": openai.RateLimitError(
        SECRET, response=response(429), body=None
    ),
    "LLM_AUTH": openai.AuthenticationError(
        SECRET, response=response(401), body=None
    ),
    "LLM_CONNECTION": openai.APIConnectionError(request=REQUEST),
    "LLM_CONTENT_FILTER": openai.BadRequestError(
        SECRET, response=response(400), body={"code": "content_filter"}
    ),
    "LLM_UNAVAILABLE": openai.InternalServerError(
        SECRET, response=response(500), body=None
    ),
    "DB_ERROR": OperationalError(SECRET, None, Exception(SECRET)),
    "QUERY_FAILED": ValueError(SECRET),
    "UNKNOWN": KeyError(SECRET),
}

# ============================================================
# 1) التصنيف
# ============================================================

for expected, error in CASES.items():

    check(
        f"classify: {type(error).__name__} -> {expected}",
        errors.classify_error(error) == expected
    )

check(
    "classify: RuntimeError (SQL retries exhausted) -> QUERY_FAILED",
    errors.classify_error(RuntimeError(SECRET)) == "QUERY_FAILED"
)

check(
    "classify: a plain BadRequestError is not a content-filter block",
    errors.classify_error(
        openai.BadRequestError("x", response=response(400), body=None)
    ) == "LLM_UNAVAILABLE"
)

check(
    "every code has English and Arabic text",
    all(
        {"english", "arabic"} <= set(texts)
        for texts in errors.MESSAGES.values()
    )
)

# ============================================================
# 2) رسالة المستخدم: مفيش تسريب + Ref + اللغة
# ============================================================

stream = io.StringIO()

handler = logging.StreamHandler(stream)

errors.logger.addHandler(handler)

errors.logger.setLevel(logging.INFO)

try:

    raise CASES["DB_ERROR"]

except OperationalError as raised:

    # الـ Exception لازم يكون اتعمله raise فعلًا علشان يبقى له traceback
    info_en = errors.handle_error(
        raised,
        language="english",
        context={"model": "mini", "role": "USER"}
    )

info_ar = errors.handle_error(CASES["LLM_TIMEOUT"], language="arabic")

check(
    "message has the fixed English text and a Ref",
    info_en["code"] == "DB_ERROR"
    and f"(Ref: {info_en['ref']})" in info_en["message"]
    and len(info_en["ref"]) == 8
)

check(
    "message is Arabic for Arabic users",
    "اتأخرت" in info_ar["message"]
)

check(
    "mixed/unknown language falls back to English",
    "took too long" in errors.handle_error(
        CASES["LLM_TIMEOUT"], language="mixed"
    )["message"]
)

leaks = []

for error in CASES.values():

    shown = errors.handle_error(error)["message"]

    if "SECRET" in shown or "SELECT" in shown or "Email" in shown:
        leaks.append(type(error).__name__)

check(
    "the user message never contains the exception text",
    not leaks
)

check(
    "two errors get different Ref codes",
    errors.handle_error(CASES["DB_ERROR"])["ref"]
    != errors.handle_error(CASES["DB_ERROR"])["ref"]
)

log_text = stream.getvalue()

check(
    "the server log has the Ref, the code and the exception type",
    info_en["ref"] in log_text
    and "code=DB_ERROR" in log_text
    and "OperationalError" in log_text
)

check(
    "the server log keeps the traceback and the context",
    "Traceback" in log_text and "'role': 'USER'" in log_text
)

# ============================================================
# 3) log_request: بيانات تشغيلية بس
# ============================================================

stream.truncate(0)
stream.seek(0)

observability.log_request(
    result_type="database",
    model="mini",
    role="USER",
    dialect="sqlite",
    latency_seconds=1.234,
    rows=5,
    restricted_fields=["users.email"]
)

line = stream.getvalue()

check(
    "request log has type/model/role/db/latency/rows/restricted",
    all(
        part in line
        for part in (
            "type=database", "model=mini", "role=USER", "db=sqlite",
            "latency=1.23s", "rows=5", "users.email"
        )
    )
)

check(
    "request log has no question or answer fields",
    "question" not in line.lower() and "answer" not in line.lower()
)

errors.logger.removeHandler(handler)

before = len(observability.logger.handlers)

observability.setup_logging()
observability.setup_logging()

check(
    "setup_logging is idempotent (no duplicate handlers)",
    len(observability.logger.handlers) <= max(before, 1)
)

os.environ["LOG_LEVEL"] = "WARNING"

observability.setup_logging()

check(
    "setup_logging applies LOG_LEVEL even if a handler already exists",
    observability.logger.level == logging.WARNING
)

os.environ["LOG_LEVEL"] = "INFO"

observability.setup_logging()

check(
    "LOG_LEVEL can be changed back",
    observability.logger.level == logging.INFO
)

# ============================================================
# 4) إعدادات الـ LLM
# ============================================================

def load_settings(**env):

    for key in ("LLM_TIMEOUT_SECONDS", "LLM_MAX_RETRIES"):
        os.environ.pop(key, None)

    os.environ.update(env)

    import models.llm_settings as settings

    return importlib.reload(settings)


defaults = load_settings()

check(
    "LLM settings default: 45s timeout, 2 retries",
    defaults.LLM_TIMEOUT_SECONDS == 45.0 and defaults.LLM_MAX_RETRIES == 2
)

custom = load_settings(LLM_TIMEOUT_SECONDS="20", LLM_MAX_RETRIES="0")

check(
    "LLM settings can be overridden",
    custom.LLM_TIMEOUT_SECONDS == 20.0 and custom.LLM_MAX_RETRIES == 0
)

broken = load_settings(LLM_TIMEOUT_SECONDS="abc", LLM_MAX_RETRIES="-5")

check(
    "LLM settings: garbage falls back / is clamped",
    broken.LLM_TIMEOUT_SECONDS == 45.0 and broken.LLM_MAX_RETRIES == 0
)

load_settings()

# ============================================================
# Summary
# ============================================================

print()
print(f"{sum(RESULTS)}/{len(RESULTS)} passed")
print()
print("--- Tests Completed ---")

if not all(RESULTS):
    sys.exit(1)
