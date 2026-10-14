"""
اختبار الـ multiple_question_analyzer بموديل مُمثَّل (من غير LLM حقيقي).

التشغيل (من روت المشروع):

    python -m tests.test_multiple_analyzer
"""

import json
import os
import sys

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

import multiple_question_analyzer as analyzer

RESULTS = []


def check(name, condition):

    RESULTS.append(bool(condition))

    print(("PASS: " if condition else "FAIL: ") + name)


def run(response, question="Which customers bought songs from Metallica?"):

    analyzer.get_model = lambda name: (lambda prompt: response)

    return analyzer.analyze_multiple_questions(question)


def raises(response):

    try:
        run(response)
    except ValueError:
        return True

    return False


# هو نفس الغلط اللي بيطلع من nano في التقييم (Tests 6 و 11)
check(
    "MULTIPLE with one question falls back to SINGLE (original wording)",
    run(
        json.dumps({"type": "MULTIPLE", "questions": ["something else"]})
    ) == {
        "type": "SINGLE",
        "questions": ["Which customers bought songs from Metallica?"]
    }
)

check(
    "SINGLE with several questions falls back to SINGLE (original wording)",
    run(
        json.dumps({"type": "SINGLE", "questions": ["a", "b"]})
    )["type"] == "SINGLE"
)

check(
    "a correct MULTIPLE is kept",
    run(
        json.dumps({"type": "MULTIPLE", "questions": [" a ", "b"]})
    ) == {"type": "MULTIPLE", "questions": ["a", "b"]}
)

check(
    "a correct SINGLE is kept",
    run(
        json.dumps({"type": "SINGLE", "questions": ["q"]})
    ) == {"type": "SINGLE", "questions": ["q"]}
)

check("invalid JSON is still an error", raises("not json"))
check("unknown type is still an error", raises(
    json.dumps({"type": "MANY", "questions": ["a"]})
))
check("empty list is still an error", raises(
    json.dumps({"type": "SINGLE", "questions": []})
))
check("non-string question is still an error", raises(
    json.dumps({"type": "SINGLE", "questions": [1]})
))
check("too many questions is still an error", raises(
    json.dumps({"type": "MULTIPLE", "questions": list("abcdef")})
))

print()
print(f"{sum(RESULTS)}/{len(RESULTS)} passed")
print()
print("--- Tests Completed ---")

if not all(RESULTS):
    sys.exit(1)
