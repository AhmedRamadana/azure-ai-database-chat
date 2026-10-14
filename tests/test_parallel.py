"""
اختبار تشغيل مراحل التحليل (فحص الوضوح / تفكيك الأسئلة / فحص توفّر الداتا)
مع بعض. موديل مُمثَّل، من غير LLM حقيقي ولا داتابيز.

التشغيل (من روت المشروع):

    python -m tests.test_parallel
"""

import json
import os
import sys
import threading
import time

for _name in (
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_DEPLOYMENT",
    "AZURE_OPENAI_MINI_DEPLOYMENT"
):
    os.environ.setdefault(_name, "test-only")

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

import classifier
import clarification_generator
import answer_generator
import context_resolver
import data_discovery
import input_analyzer
import multiple_answer_generator
import multiple_question_analyzer
import pipeline
import schema_answer
import text_to_sql

from dialects import get_dialect
from authorization.policy_builder import build_effective_policy

RESULTS = []


def check(name, condition):

    RESULTS.append(bool(condition))

    print(("PASS: " if condition else "FAIL: ") + name)


SCHEMA = {
    "Customer": {
        "columns": [
            {"name": "CustomerId", "type": "INTEGER"},
            {"name": "FirstName", "type": "TEXT"},
        ],
        "foreign_keys": []
    }
}


class FakeDB:

    def __init__(self):

        self.schema = SCHEMA
        self.policy = build_effective_policy(SCHEMA)
        self.value_cache = {}
        self.entity_catalog = None
        self.is_demo = False
        self.dialect = get_dialect()
        self.display_name = "store"
        self.pg_schema = "public"

    def execute(self, query):

        if "count_subquery" in query:
            return ["count"], [(1,)]

        return ["FirstName"], [("Ann",)]


DB = FakeDB()
USER = {"user_id": "u", "role": "USER"}

LOCK = threading.Lock()

STATE = {}

ACTIVE = {"now": 0, "max": 0}


def fake_llm(prompt):

    if "intent classifier" in prompt:
        kind = "classify"
    elif "intent analysis assistant" in prompt:
        kind = "input"
    elif "question decomposition" in prompt:
        kind = "multiple"
    elif "data availability analyzer" in prompt:
        kind = "availability"
    elif "ask ONE clarification question" in prompt:
        return "Which?\n1. a\n2. b"
    elif "conversation context resolver" in prompt:
        return "q"
    elif "You are a database assistant for the" in prompt:
        return "ANSWER"
    else:
        return 'SELECT "FirstName" FROM "Customer"'

    with LOCK:
        ACTIVE["now"] += 1
        ACTIVE["max"] = max(ACTIVE["max"], ACTIVE["now"])
        STATE.setdefault("calls", []).append(kind)

    try:

        time.sleep(STATE.get("delay", {}).get(kind, 0))

        fail = STATE.get("fail", {}).get(kind)

        if fail:
            raise fail

        with LOCK:
            once = STATE.get("fail_once", {}).pop(kind, None)

        if once:
            raise once

        return STATE["responses"][kind]

    finally:

        with LOCK:
            ACTIVE["now"] -= 1


for module in (
    classifier, input_analyzer, context_resolver, data_discovery,
    text_to_sql, clarification_generator, answer_generator,
    multiple_answer_generator, multiple_question_analyzer, schema_answer
):
    module.get_model = lambda name: fake_llm


def reset(**overrides):

    STATE.clear()

    ACTIVE.update({"now": 0, "max": 0})

    STATE["responses"] = {
        "classify": "DATABASE",
        "input": "CLEAR",
        "multiple": json.dumps({"type": "SINGLE", "questions": ["q"]}),
        "availability": json.dumps(
            {"status": "AVAILABLE", "missing_items": []}
        ),
    }

    STATE.update(overrides)


def ask(history=None):

    return pipeline.run_pipeline(
        "how many customers?", "nano", history or [], USER, db=DB
    )


# ============================================================
# 1) فعلًا بتشتغل مع بعض، والزمن أقل
# ============================================================

DELAY = 0.4

reset(delay={"input": DELAY, "multiple": DELAY, "availability": DELAY})

pipeline.PARALLEL_ANALYSIS = True

started = time.perf_counter()

result = ask()

parallel_time = time.perf_counter() - started

check(
    "parallel: the three analysis calls overlap",
    ACTIVE["max"] == 3
)

check(
    "parallel: the question is answered normally",
    result["type"] == "database" and result["rows"] == [("Ann",)]
)

reset(delay={"input": DELAY, "multiple": DELAY, "availability": DELAY})

pipeline.PARALLEL_ANALYSIS = False

started = time.perf_counter()

ask()

sequential_time = time.perf_counter() - started

check(
    "sequential mode (PARALLEL_ANALYSIS=false) never overlaps",
    ACTIVE["max"] == 1
)

check(
    f"parallel is clearly faster ({parallel_time:.2f}s vs {sequential_time:.2f}s)",
    parallel_time < sequential_time - 0.6 * DELAY * 2 / 2
)

pipeline.PARALLEL_ANALYSIS = True

# ============================================================
# 2) نفس النتيجة في الحالتين
# ============================================================

def outcome(parallel, **overrides):

    pipeline.PARALLEL_ANALYSIS = parallel

    reset(**overrides)

    try:
        result = ask()
    except Exception as error:
        return ("error", type(error).__name__)

    return (
        result["type"],
        result.get("answer"),
        result.get("columns"),
        result.get("rows")
    )


SCENARIOS = {
    "single question": {},
    "ambiguous": {"responses": {
        "classify": "DATABASE", "input": "AMBIGUOUS",
        "multiple": json.dumps({"type": "SINGLE", "questions": ["q"]}),
        "availability": json.dumps({"status": "AVAILABLE", "missing_items": []}),
    }},
    "multiple questions": {"responses": {
        "classify": "DATABASE", "input": "CLEAR",
        "multiple": json.dumps({"type": "MULTIPLE", "questions": ["a", "b"]}),
        "availability": json.dumps({"status": "AVAILABLE", "missing_items": []}),
    }},
    "data not available": {"responses": {
        "classify": "DATABASE", "input": "CLEAR",
        "multiple": json.dumps({"type": "SINGLE", "questions": ["q"]}),
        "availability": json.dumps(
            {"status": "UNAVAILABLE", "missing_items": ["salaries"]}
        ),
    }},
}

for name, overrides in SCENARIOS.items():

    check(
        f"same outcome in parallel and sequential: {name}",
        outcome(True, **overrides) == outcome(False, **overrides)
    )

pipeline.PARALLEL_ANALYSIS = True

# ============================================================
# 3) الأخطاء: بتتفجّر بس لو النتيجة مطلوبة
# ============================================================

boom = RuntimeError("analysis exploded")

reset(
    responses={
        **{
            "classify": "DATABASE",
            "input": "AMBIGUOUS",
            "multiple": "{}",
            "availability": "{}",
        }
    },
    fail={"multiple": boom, "availability": boom}
)

result = ask()

check(
    "ambiguous question still asks for clarification even if the other "
    "analyses fail (their results are not needed)",
    result["type"] == "clarification"
)

reset(fail={"input": boom})

try:
    ask()
    raised = None
except RuntimeError as error:
    raised = error

check(
    "an error in a NEEDED analysis (input) is raised",
    raised is boom
)

reset(fail={"availability": boom})

try:
    ask()
    raised = None
except RuntimeError as error:
    raised = error

check(
    "an error in the availability check is raised for a single question",
    raised is boom
)

reset(
    responses={
        "classify": "DATABASE",
        "input": "CLEAR",
        "multiple": json.dumps(
            {"type": "MULTIPLE", "questions": ["a", "b"]}
        ),
        "availability": json.dumps(
            {"status": "AVAILABLE", "missing_items": []}
        ),
    },
    # أول مكالمة availability هي الخاصة بالسؤال الكامل (وبتتشغّل مع
    # الباقي)، والأسئلة الفرعية بتعمل فحص لنفسها بعدها.
    fail_once={"availability": boom}
)

result = ask()

check(
    "for MULTIPLE questions the whole-question availability result is not "
    "needed (each sub-question runs its own check)",
    result["type"] == "multiple"
)

# ============================================================
# 4) المرحلة الأولى لسه متتابعة: مفيش مكالمات ملهاش لازمة
# ============================================================

reset(responses={
    "classify": "UNRELATED", "input": "x", "multiple": "x",
    "availability": "x"
})

result = ask()

check(
    "UNRELATED stops after classification (no analysis calls are made)",
    result["type"] == "unrelated" and STATE["calls"] == ["classify"]
)

reset(responses={
    "classify": "GREETING", "input": "x", "multiple": "x",
    "availability": "x"
})

result = ask()

check(
    "GREETING stops after classification",
    result["type"] == "greeting" and STATE["calls"] == ["classify"]
)

print()
print(f"{sum(RESULTS)}/{len(RESULTS)} passed")
print()
print("--- Tests Completed ---")

if not all(RESULTS):
    sys.exit(1)
