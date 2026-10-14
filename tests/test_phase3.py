"""
اختبارات المرحلة 3: Discovery، وجولة التوضيح الواحدة، ودمج الردود
القصيرة، والـ assume-and-answer.

مش محتاجة داتابيز ولا LLM حقيقي ولا .env. الـ LLM بيتستبدل بـ
function بترد حسب نوع الـ prompt، والداتابيز بـ FakeDB.

التشغيل (من روت المشروع):

    python -m tests.test_phase3
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

from authorization.access_policy import visible_schema
from authorization.policy_builder import build_effective_policy

from prompts.answer_prompt import build_answer_prompt
from prompts.classification_prompt import build_classification_prompt
from prompts.clarification_prompt import build_clarification_prompt
from prompts.context_prompt import build_context_prompt
from prompts.input_analysis_prompt import build_input_analysis_prompt


RESULTS = []


def check(name, condition):

    RESULTS.append(bool(condition))

    print(("PASS: " if condition else "FAIL: ") + name)


def table(*columns):

    return {
        "columns": [
            {"name": name, "type": "TEXT"}
            for name in columns
        ],
        "foreign_keys": []
    }


SCHEMA = {
    "Customer": {
        **table(
            "CustomerId", "FirstName", "LastName", "Country",
            "Phone", "Email"
        ),
        "foreign_keys": [
            {
                "column": ["SupportRepId"],
                "references_table": "Employee",
                "references_column": ["EmployeeId"]
            },
            {
                "column": ["Email"],
                "references_table": "Secret",
                "references_column": ["Email"]
            }
        ]
    },
    "InvoiceLine": table("InvoiceLineId", "InvoiceId", "UnitPrice"),
    "Track": table("TrackId", "Name"),
    "Vault": table("Password", "SSN"),
}

SCHEMA["Customer"]["columns"].append(
    {"name": "SupportRepId", "type": "INTEGER"}
)

POLICY = build_effective_policy(SCHEMA, is_demo=True)

USER = {"user_id": "u", "role": "USER"}
ADMIN = {"user_id": "a", "role": "ADMIN"}


class FakeDB:

    def __init__(self):

        self.schema = SCHEMA
        self.policy = POLICY
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


# ============================================================
# 1) visible_schema
# ============================================================

visible_user = visible_schema(SCHEMA, "USER", POLICY)
visible_admin = visible_schema(SCHEMA, "ADMIN", POLICY)

user_columns = {c["name"] for c in visible_user["Customer"]["columns"]}
admin_columns = {c["name"] for c in visible_admin["Customer"]["columns"]}

check(
    "visible_schema: USER does not see Email / Phone",
    "Email" not in user_columns
    and "Phone" not in user_columns
    and "FirstName" in user_columns
)

check(
    "visible_schema: ADMIN sees RESTRICTED columns",
    {"Email", "Phone"} <= admin_columns
)

check(
    "visible_schema: a table with only DENIED columns disappears (all roles)",
    "Vault" not in visible_user and "Vault" not in visible_admin
)

check(
    "visible_schema: foreign keys on hidden columns are dropped",
    all(
        "Email" not in fk["column"]
        for fk in visible_user["Customer"]["foreign_keys"]
    )
    and len(visible_user["Customer"]["foreign_keys"]) == 1
)

check(
    "visible_schema: does not modify the original schema",
    any(c["name"] == "Email" for c in SCHEMA["Customer"]["columns"])
)


# ============================================================
# 2) build_schema_facts  (الحقائق اللي بتتبعت للـ LLM)
# ============================================================

facts_overview = schema_answer.build_schema_facts(
    "what data do you have", DB, "USER"
)

check(
    "facts (overview, USER): lists tables, hides Email / Phone / Vault",
    "- Customer:" in facts_overview
    and "Email" not in facts_overview
    and "Phone" not in facts_overview
    and "Vault" not in facts_overview
    and "Password" not in facts_overview
)

facts_admin = schema_answer.build_schema_facts(
    "what data do you have", DB, "ADMIN"
)

check(
    "facts (overview, ADMIN): includes Email, never Password / SSN",
    "Email" in facts_admin
    and "Password" not in facts_admin
    and "SSN" not in facts_admin
)

facts_detail = schema_answer.build_schema_facts(
    "what columns does the Customer table have?", DB, "USER"
)

check(
    "facts (detail): only the asked table, still no Email",
    "TABLE: Customer" in facts_detail
    and "TABLE: Track" not in facts_detail
    and "Email" not in facts_detail
    and "FirstName (TEXT)" in facts_detail
)

check(
    "facts (detail): foreign key on a visible column is shown",
    "SupportRepId -> Employee.EmployeeId" in facts_detail
)

check(
    "facts: CamelCase and plural names are matched (invoice lines)",
    "TABLE: InvoiceLine" in schema_answer.build_schema_facts(
        "what is in invoice lines?", DB, "USER"
    )
)

check(
    "facts: 'Tracking' does not match the Track table",
    "TABLE: Track" not in schema_answer.build_schema_facts(
        "tell me about tracking", DB, "USER"
    )
)

check(
    "facts: asking directly for a hidden table reveals nothing about it",
    "Password" not in schema_answer.build_schema_facts(
        "what columns does the Vault table have?", DB, "ADMIN"
    )
)


# ============================================================
# 3) Prompts
# ============================================================

classification_prompt = build_classification_prompt(
    "q", "store", "TABLES:\n- Customer: CustomerId"
)

check(
    "classification prompt defines DISCOVERY with examples",
    "DISCOVERY" in classification_prompt
    and "What columns does the Customer table have?"
    in classification_prompt
    and "ايه الداتا الموجودة؟" in classification_prompt
)

clarification_prompt = build_clarification_prompt(
    "show me data", "store", "TABLES:\n- Customer: CustomerId"
)

check(
    "clarification prompt: ONE question + numbered options format",
    "ONE short clarification question" in clarification_prompt
    and "1. <option>" in clarification_prompt
    and "2 to 4" in clarification_prompt
    and "Ask only ONE question" in clarification_prompt
)

context_prompt = build_context_prompt(
    "2",
    [
        {"role": "user", "content": "show me data"},
        {"role": "assistant", "content": "What?\n1. a\n2. b"}
    ],
    "store"
)

check(
    "context prompt: has the clarification-reply rule and shows the options",
    "REPLIES TO A CLARIFICATION QUESTION" in context_prompt
    and "ASSISTANT: What?\n1. a\n2. b" in context_prompt
    and "الاتنين" in context_prompt
)

analysis_prompt = build_input_analysis_prompt("q", "store", "TABLES:")

clear_part, ambiguous_part = analysis_prompt.split("AMBIGUOUS:\n", 1)

check(
    "input analysis: 'Show me customers' moved to CLEAR",
    '"Show me customers."' in clear_part
    and '"Show me customers."' not in ambiguous_part
)

check(
    "input analysis: AMBIGUOUS is limited to 3 explicit cases",
    "NO SUBJECT" in ambiguous_part
    and "NO SENSIBLE DEFAULT" in ambiguous_part
    and "BROKEN REFERENCE" in ambiguous_part
    and "When in doubt, choose CLEAR" in analysis_prompt
)

args = dict(
    user_question="q", sql_query="SELECT 1", columns=["a"],
    rows=[(1,)], real_total=1, restricted_fields=[], language="english"
)

check(
    "answer prompt: assumed=True adds the interpretation note",
    "ASSUMED INTERPRETATION" in build_answer_prompt(**args, assumed=True)
    and "ASSUMED INTERPRETATION" not in build_answer_prompt(**args)
)


# ============================================================
# 4) Pipeline flows (LLM مستبدل)
# ============================================================

STATE = {
    "classification": "DATABASE",
    "input": "CLEAR",
    "context": None,
    "sql": 'SELECT "FirstName" FROM "Customer"',
}

PROMPTS = []


def fake_llm(prompt):

    PROMPTS.append(prompt)

    if "intent classifier" in prompt:
        return STATE["classification"]

    if "intent analysis assistant" in prompt:
        return STATE["input"]

    if "conversation context resolver" in prompt:
        return STATE["context"]

    if "question decomposition" in prompt:
        return json.dumps({"type": "SINGLE", "questions": ["q"]})

    if "data availability analyzer" in prompt:
        return json.dumps({"status": "AVAILABLE", "missing_items": []})

    if "ask ONE clarification question" in prompt:
        return "Which one?\n1. Customers by country\n2. Top tracks"

    if "asking what the database contains" in prompt:
        return "SCHEMA ANSWER"

    if "You are a database assistant for the" in prompt:
        return "ANSWER"

    return STATE["sql"]


for module in (
    classifier, input_analyzer, context_resolver, data_discovery,
    text_to_sql, clarification_generator, answer_generator,
    multiple_answer_generator, multiple_question_analyzer, schema_answer
):
    module.get_model = lambda name: fake_llm


def ask(question, user=USER, history=None, **state):

    PROMPTS.clear()

    STATE.update(
        {
            "classification": "DATABASE",
            "input": "CLEAR",
            "context": question,
            "sql": 'SELECT "FirstName" FROM "Customer"',
        }
    )

    STATE.update(state)

    return pipeline.run_pipeline(
        question, "nano", history or [], user, db=DB
    )


def prompt_with(marker):

    return next((p for p in PROMPTS if marker in p), "")


# --- a) DISCOVERY ------------------------------------------------

result = ask(
    "what data do you have?",
    classification="DISCOVERY"
)

check(
    "pipeline: DISCOVERY -> type 'discovery' with the LLM's phrasing",
    result["type"] == "discovery" and result["answer"] == "SCHEMA ANSWER"
)

discovery_prompt = prompt_with("asking what the database contains")

check(
    "pipeline: discovery prompt carries facts without restricted columns",
    "Customer" in discovery_prompt
    and "Email" not in discovery_prompt
    and "Vault" not in discovery_prompt
)

check(
    "pipeline: discovery never reaches SQL generation or the DB",
    not prompt_with("Text-to-SQL")
    and not prompt_with("intent analysis assistant")
)

admin_result = ask(
    "what data do you have?", user=ADMIN, classification="DISCOVERY"
)

check(
    "pipeline: ADMIN discovery sees Email but still never Password",
    "Email" in prompt_with("asking what the database contains")
    and "Password" not in prompt_with("asking what the database contains")
)

# --- b) clarification (أول مرة) ----------------------------------

result = ask("show me data", input="AMBIGUOUS")

check(
    "pipeline: first AMBIGUOUS -> clarification with options",
    result["type"] == "clarification"
    and "1. Customers by country" in result["answer"]
    and result["resolved_question"] == "show me data"
)

clarification_prompt_text = prompt_with("ask ONE clarification question")

check(
    "pipeline: clarification options come from the USER-visible schema",
    "Customer" in clarification_prompt_text
    and "Email" not in clarification_prompt_text
    and "Phone" not in clarification_prompt_text
)

# --- c) الرد على التوضيح -> مفيش جولة تانية ------------------------

HISTORY_AFTER_CLARIFICATION = [
    {"role": "user", "content": "show me data"},
    {
        "role": "assistant",
        "type": "clarification",
        "content": "Which one?\n1. Customers by country\n2. Top tracks"
    },
]

result = ask(
    "2",
    history=HISTORY_AFTER_CLARIFICATION,
    context="Show me the top tracks.",
    input="AMBIGUOUS"
)

check(
    "pipeline: second AMBIGUOUS after a clarification -> answers, no 2nd question",
    result["type"] == "database"
)

check(
    "pipeline: the assumption note reaches the SQL prompt only",
    "Do NOT ask for clarification" in prompt_with("Text-to-SQL")
)

check(
    "pipeline: the answer is told to state the interpretation",
    "ASSUMED INTERPRETATION" in prompt_with(
        "You are a database assistant for the"
    )
)

check(
    "pipeline: returned resolved_question has no internal note",
    result["resolved_question"] == "Show me the top tracks."
    and "Do NOT ask" not in result["resolved_question"]
)

# --- d) context merge: الـ resolver شايف الخيارات ------------------

context_prompt_text = prompt_with("conversation context resolver")

check(
    "pipeline: context resolver sees the clarification options",
    "1. Customers by country" in context_prompt_text
    and "2. Top tracks" in context_prompt_text
    and "CURRENT USER QUESTION" in context_prompt_text
)

# --- e) آخر رد مش توضيح -> نسأل عادي ------------------------------

result = ask(
    "show me stuff",
    history=[
        {"role": "user", "content": "how many customers"},
        {"role": "assistant", "type": "database", "content": "59"},
    ],
    input="AMBIGUOUS"
)

check(
    "pipeline: AMBIGUOUS after a normal answer -> clarification again",
    result["type"] == "clarification"
)

# history من غير حقل type (callers تانيين)
result = ask(
    "show me stuff",
    history=[
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ],
    input="AMBIGUOUS"
)

check(
    "pipeline: history without 'type' keys is handled (clarifies)",
    result["type"] == "clarification"
)

# --- f) سؤال واضح: مفيش assume ولا ملاحظة -------------------------

result = ask(
    "how many customers?",
    history=HISTORY_AFTER_CLARIFICATION
)

check(
    "pipeline: a CLEAR question after a clarification has no assumption note",
    result["type"] == "database"
    and "Do NOT ask for clarification" not in prompt_with("Text-to-SQL")
    and "ASSUMED INTERPRETATION" not in prompt_with(
        "You are a database assistant for the"
    )
)

# --- g) رفض الصلاحيات لسه شغال مع assume --------------------------

result = ask(
    "2",
    history=HISTORY_AFTER_CLARIFICATION,
    context="Show customers' emails.",
    input="AMBIGUOUS",
    sql='SELECT "Email" FROM "Customer"'
)

check(
    "pipeline: assume-and-answer never bypasses authorization",
    result["type"] == "unauthorized"
)

# --- h) classifier + GREETING/UNRELATED ما اتأثروش ------------------

check(
    "pipeline: GREETING still works",
    ask("hi", classification="GREETING")["type"] == "greeting"
)

check(
    "pipeline: UNRELATED still works",
    ask("tell me a joke", classification="UNRELATED")["type"]
    == "unrelated"
)

classifier.get_model = lambda name: (lambda prompt: "NONSENSE")

try:

    classifier.classify_question("q", DB)

    invalid_rejected = False

except ValueError:

    invalid_rejected = True

finally:

    classifier.get_model = lambda name: fake_llm

classifier.get_model = lambda name: (lambda prompt: "DISCOVERY")

check(
    "classifier: DISCOVERY is an accepted label",
    classifier.classify_question("q", DB) == "DISCOVERY"
)

classifier.get_model = lambda name: fake_llm

check(
    "classifier: an unknown label is still rejected",
    invalid_rejected
)


# ============================================================
# Summary
# ============================================================

print()
print(f"{sum(RESULTS)}/{len(RESULTS)} passed")
print()
print("--- Tests Completed ---")

if not all(RESULTS):
    sys.exit(1)
