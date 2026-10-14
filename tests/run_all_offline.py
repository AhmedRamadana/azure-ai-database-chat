"""
run_all_offline.py

بيشغّل كل الـ suites اللي بتتحقق تلقائيًا (PASS/FAIL) ويطلّع ملخص واحد.
مش محتاجة LLM ولا مفاتيح Azure.

    python -m tests.run_all_offline

بعض الـ suites محتاجة Postgres (الداتابيز التجريبية) عن طريق DATABASE_URL
(test_db_context). لو DATABASE_URL مش متحدد، بتتخطى وتتسجّل SKIP.
وجزء MySQL في test_dialects بيتفعّل بمتغيرات MYSQL_TEST_* (انظر الملف).

الاختبارات اللي بتنادي LLM حقيقي (test_pipeline وأخواتها وtests/evaluation)
مش هنا: دي بتتشغّل يدويًا لأنها بتكلّف وبتتغير نتايجها.
"""

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except ImportError:
    pass

# (module, needs DATABASE_URL)
SUITES = [
    ("tests.test_policy", False),
    ("tests.test_phase3", False),
    ("tests.test_multiple_analyzer", False),
    ("tests.test_errors", False),
    ("tests.test_parallel", False),
    ("tests.test_dialects", False),
    ("tests.test_star_authorization", False),
    ("tests.test_sql_safety", False),
    ("tests.test_db_context", True),
]

PASSED = re.compile(r"(\d+)/(\d+) passed")


def run(module):

    process = subprocess.run(
        [sys.executable, "-m", module],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=600
    )

    output = process.stdout + process.stderr

    matches = PASSED.findall(output)

    if matches:
        passed, total = map(int, matches[-1])
    else:
        passed, total = 0, 0

    ok = process.returncode == 0 and total > 0 and passed == total

    return ok, passed, total, output


def main():

    failures = 0

    for module, needs_db in SUITES:

        if needs_db and not os.getenv("DATABASE_URL"):

            print(f"SKIP  {module} (DATABASE_URL is not set)")

            continue

        ok, passed, total, output = run(module)

        print(f"{'OK  ' if ok else 'FAIL'}  {module}: {passed}/{total}")

        if not ok:

            failures += 1

            print("      last lines of output:")

            for line in output.strip().splitlines()[-8:]:
                print("      " + line)

    print()
    print("ALL SUITES PASSED" if not failures else f"{failures} suite(s) failed")

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
