"""
اختبارات المرحلة 2: الـ Policy التلقائية، وتمريرها في الـ Authorization،
والـ Resolvers، والـ Prompts.

مش محتاجة داتابيز ولا LLM ولا .env.

التشغيل (من روت المشروع):

    python -m tests.test_policy
"""

import os
import sys

# models/ بيرفض الـ import من غير مفاتيح Azure. الاختبار ده مش بينادي
# أي LLM، فبنحط قيم وهمية بس عشان الـ import يعدّي.
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

from authorization.access_policy import (
    ACCESS_POLICY,
    DENIED,
    PUBLIC,
    RESTRICTED,
    get_data_sensitivity,
    merge_policies
)

from authorization.policy_builder import (
    build_effective_policy,
    build_policy,
    classify_column,
    resolve_policy,
    summarize_policy
)

from authorization.authorization import (
    apply_column_authorization,
    authorize_sql
)

from schema import format_schema_summary

from prompts.classification_prompt import build_classification_prompt
from prompts.input_analysis_prompt import build_input_analysis_prompt
from prompts.data_discovery_prompt import build_data_discovery_prompt
from prompts.context_prompt import build_context_prompt
from prompts.entity_prompt import build_entity_prompt
from prompts.clarification_prompt import build_clarification_prompt
from prompts.answer_prompt import build_answer_prompt
from prompts.multiple_answer_prompt import build_multiple_answer_prompt
from prompts.multiple_question_prompt import build_multiple_question_prompt


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


USER = {"user_id": "t", "role": "USER"}
ADMIN = {"user_id": "t", "role": "ADMIN"}


def raises(function, *args, error=PermissionError, **kwargs):

    try:
        function(*args, **kwargs)
    except error:
        return True
    except Exception:
        return False

    return False


# ============================================================
# 1) classify_column
# ============================================================

EXPECTED = {

    # DENIED
    "Password": DENIED, "password_hash": DENIED, "PasswordHash": DENIED,
    "SSN": DENIED, "ssn": DENIED, "CreditCardNumber": DENIED,
    "credit_card": DENIED, "card_number": DENIED, "CVV": DENIED,
    "iban": DENIED, "api_key": DENIED, "APIKey": DENIED,
    "access_token": DENIED, "AccessToken": DENIED,
    "client_secret": DENIED, "national_id": DENIED,
    "NationalId": DENIED, "BankAccountNumber": DENIED, "hash": DENIED,

    # RESTRICTED
    "Email": RESTRICTED, "email_address": RESTRICTED,
    "UserEmail": RESTRICTED, "Phone": RESTRICTED,
    "phone_number": RESTRICTED, "PhoneNumber": RESTRICTED,
    "Mobile": RESTRICTED, "Fax": RESTRICTED, "Address": RESTRICTED,
    "BillingAddress": RESTRICTED, "ip_address": RESTRICTED,
    "BirthDate": RESTRICTED, "date_of_birth": RESTRICTED,
    "dob": RESTRICTED, "Salary": RESTRICTED, "card": RESTRICTED,
    "CardType": RESTRICTED,

    # PUBLIC (حماية من الإيجابيات الكاذبة)
    "Discard": PUBLIC, "Hashtag": PUBLIC, "SecretaryId": PUBLIC,
    "ClassName": PUBLIC, "Headphones": PUBLIC, "Saxophone": PUBLIC,
    "token_count": PUBLIC, "TokensUsed": PUBLIC, "BillingCity": PUBLIC,
    "BillingCountry": PUBLIC, "FirstName": PUBLIC, "Name": PUBLIC,
    "Total": PUBLIC, "UnitPrice": PUBLIC, "Title": PUBLIC,
    "HireDate": PUBLIC, "Company": PUBLIC, "PostalCode": PUBLIC,
    "Country": PUBLIC, "Milliseconds": PUBLIC,
}

wrong = {
    name: (expected, classify_column(name))
    for name, expected in EXPECTED.items()
    if classify_column(name) != expected
}

check(
    f"classify_column: {len(EXPECTED)} names classified correctly",
    not wrong
)

if wrong:
    print("   mismatches:", wrong)


# ============================================================
# 2) merge / lookup
# ============================================================

merged = merge_policies(
    {"T": {"A": RESTRICTED, "B": DENIED}},
    {"T": {"A": DENIED, "B": RESTRICTED}, "U": {"C": RESTRICTED}}
)

check(
    "merge_policies: the stricter level wins",
    merged == {"T": {"A": DENIED, "B": DENIED}, "U": {"C": RESTRICTED}}
)

check(
    "get_data_sensitivity: case-insensitive fallback is fail-safe",
    get_data_sensitivity("T", "EMAIL", {"T": {"Email": RESTRICTED}})
    == RESTRICTED
)

check(
    "get_data_sensitivity: unknown column is PUBLIC",
    get_data_sensitivity("T", "Name", {"T": {"Email": RESTRICTED}})
    == PUBLIC
)


# ============================================================
# 3) build_policy / overrides / effective policy
# ============================================================

SHOP = {
    "users": table("id", "name", "email", "password_hash", "phone_number"),
    "orders": table("id", "user_id", "total", "billing_address", "card_number"),
    "notes": table("id", "mail_id", "token_count"),
}

policy = build_policy(SHOP)

check(
    "build_policy: custom schema gets automatic rules",
    policy == {
        "users": {
            "email": RESTRICTED,
            "password_hash": DENIED,
            "phone_number": RESTRICTED,
        },
        "orders": {
            "billing_address": RESTRICTED,
            "card_number": DENIED,
        },
        "notes": {
            "mail_id": RESTRICTED,
        },
    }
)

policy = build_policy(
    SHOP,
    overrides={
        "notes.mail_id": PUBLIC,
        "users.name": RESTRICTED,
    }
)

check(
    "overrides: can both open and close a column",
    "notes" not in policy
    and policy["users"]["name"] == RESTRICTED
)

check(
    "overrides: unknown column is rejected",
    raises(
        build_policy,
        SHOP,
        overrides={"users.nope": RESTRICTED},
        error=ValueError
    )
)

check(
    "overrides: invalid level is rejected",
    raises(
        build_policy,
        SHOP,
        overrides={"users.name": "SECRET"},
        error=ValueError
    )
)

CHINOOK = {
    "Customer": table(
        "CustomerId", "FirstName", "LastName", "Company", "Address",
        "City", "State", "Country", "PostalCode", "Phone", "Fax",
        "Email", "SupportRepId"
    ),
    "Employee": table(
        "EmployeeId", "LastName", "FirstName", "Title", "BirthDate",
        "HireDate", "Address", "City", "State", "Country", "PostalCode",
        "Phone", "Fax", "Email"
    ),
    "Invoice": table(
        "InvoiceId", "CustomerId", "InvoiceDate", "BillingAddress",
        "BillingCity", "BillingState", "BillingCountry",
        "BillingPostalCode", "Total"
    ),
    "Artist": table("ArtistId", "Name"),
}

effective = build_effective_policy(CHINOOK, is_demo=True)

check(
    "demo policy keeps the manual Chinook rules (Employee.City)",
    effective["Employee"]["City"] == RESTRICTED
)

check(
    "demo policy adds Invoice.BillingAddress (was not covered before)",
    effective["Invoice"]["BillingAddress"] == RESTRICTED
)

check(
    "demo policy: BillingCity / Customer.City stay public",
    "BillingCity" not in effective["Invoice"]
    and "City" not in effective["Customer"]
)

check(
    "custom (non-demo) policy does NOT include Chinook manual rules",
    "City" not in build_effective_policy(
        CHINOOK, is_demo=False
    ).get("Employee", {})
)

check(
    "resolve_policy(None) is never weaker than the demo policy",
    resolve_policy(CHINOOK, None) == effective
)

summary = summarize_policy(effective)

check(
    "summarize_policy lists restricted columns",
    "Customer.Email" in summary[RESTRICTED]
    and "Invoice.BillingAddress" in summary[RESTRICTED]
)


# ============================================================
# 4) Authorization يستخدم الـ policy الممرَّرة
# ============================================================

shop_policy = build_effective_policy(SHOP)


def run(sql, user, schema=SHOP, policy=shop_policy):

    return apply_column_authorization(sql, user, schema, policy)


# USER على داتابيز مخصصة (مفيش حاجة من Chinook فيها)
query, removed = run(
    'SELECT "name", "email" FROM "users"',
    USER
)

check(
    "custom DB: USER loses `email` automatically",
    removed == ["users.email"] and '"email"' not in query
)

check(
    "custom DB: SELECT * is expanded and the sensitive columns removed",
    (lambda r: (
        "email" not in r[0]
        and "password_hash" not in r[0]
        and "phone_number" not in r[0]
        and "users.email" in r[1]
        and "users.password_hash" in r[1]
    ))(run('SELECT * FROM "users"', USER))
)

check(
    "custom DB: ADMIN sees RESTRICTED but never DENIED",
    (lambda r: (
        '"email"' in r[0]
        and "password_hash" not in r[0]
        and r[1] == ["users.password_hash"]
    ))(run('SELECT * FROM "users"', ADMIN))
)

check(
    "custom DB: restricted column in WHERE is denied",
    raises(
        run,
        'SELECT "name" FROM "users" WHERE "email" = \'a@b.c\'',
        USER
    )
)

check(
    "custom DB: whole-row access is denied",
    raises(
        run,
        'SELECT row_to_json("users") FROM "users"',
        USER
    )
)

check(
    "custom DB: billing_address is hidden from USER",
    run('SELECT "id", "billing_address" FROM "orders"', USER)[1]
    == ["orders.billing_address"]
)

# الـ policy الافتراضية (من غير تمرير) أمان: مش Fail-Open
check(
    "no policy passed: automatic rules still apply (no fail-open)",
    run('SELECT "name", "email" FROM "users"', USER, policy=None)[1]
    == ["users.email"]
)

# الدمج مع Chinook: العمود اللي ماكانش مغطّى
chinook_query, chinook_removed = apply_column_authorization(
    'SELECT "InvoiceId", "BillingAddress", "BillingCity" FROM "Invoice"',
    USER,
    CHINOOK,
    effective
)

check(
    "Chinook: Invoice.BillingAddress no longer leaks to USER",
    chinook_removed == ["Invoice.BillingAddress"]
    and "BillingCity" in chinook_query
)

check(
    "Chinook: ADMIN can still read Invoice.BillingAddress",
    apply_column_authorization(
        'SELECT "BillingAddress" FROM "Invoice"',
        ADMIN,
        CHINOOK,
        effective
    )[1] == []
)


# ============================================================
# 5) authorize_sql (كانت مقطوعة وبترجّع None)
# ============================================================

check(
    "authorize_sql: returns True for a clean query",
    authorize_sql(
        'SELECT "name" FROM "users"',
        USER,
        SHOP,
        shop_policy
    ) is True
)

check(
    "authorize_sql: restricted SELECT item -> PermissionError",
    raises(
        authorize_sql,
        'SELECT "name", "email" FROM "users"',
        USER,
        SHOP,
        shop_policy
    )
)

check(
    "authorize_sql: SELECT * on a table with restricted columns -> denied",
    raises(
        authorize_sql,
        'SELECT * FROM "users"',
        USER,
        SHOP,
        shop_policy
    )
)

check(
    "authorize_sql: schema is required",
    raises(
        authorize_sql,
        'SELECT "name" FROM "users"',
        USER,
        error=ValueError
    )
)


# ============================================================
# 6) Resolvers: عمرهم ما بيحمّلوا قيم أعمدة حساسة
# ============================================================

class FakeDB:

    def __init__(self, schema, policy):

        self.schema = schema
        self.policy = policy
        self.value_cache = {}
        self.entity_catalog = None
        self.is_demo = False
        self.display_name = "shop"
        self.executed = []

    def execute(self, query):

        self.executed.append(query)

        return ["v"], [("alice@example.com",), ("bob@example.com",)]


from value_resolver import resolve_sql_values
from entity_resolver import build_entity_catalog

shop_db = FakeDB(
    {name: {**info, "columns": [
        {"name": c["name"], "type": "VARCHAR"} for c in info["columns"]
    ]} for name, info in SHOP.items()},
    shop_policy
)

resolve_sql_values(
    shop_db,
    'SELECT 1 FROM "users" WHERE "users"."email" = \'alice@exmple.com\''
)

check(
    "value_resolver: never queries a RESTRICTED column",
    not any('"email"' in q for q in shop_db.executed)
)

resolve_sql_values(
    shop_db,
    'SELECT 1 FROM "users" WHERE "users"."name" = \'alise\''
)

check(
    "value_resolver: still queries PUBLIC columns",
    any('"name"' in q for q in shop_db.executed)
)

shop_db.executed.clear()

build_entity_catalog(shop_db)

queried = " ".join(shop_db.executed)

check(
    "entity catalog: skips email / password_hash / phone_number / card_number",
    '"email"' not in queried
    and '"password_hash"' not in queried
    and '"phone_number"' not in queried
    and '"card_number"' not in queried
    and '"name"' in queried
)


# ============================================================
# 7) Prompts: مفيش افتراض Chinook على داتابيز تانية
# ============================================================

summary_text = format_schema_summary(SHOP)

check(
    "schema summary lists tables and columns",
    "- users: id, name, email" in summary_text
    and "- orders:" in summary_text
)

big = {f"t{i}": table(*[f"c{j}" for j in range(30)]) for i in range(60)}

big_summary = format_schema_summary(big)

check(
    "schema summary is capped for large databases",
    "(+20 more tables)" in big_summary
    and "(+20 more)" in big_summary
    and len(big_summary) < 6000
)

PROMPTS = {
    "classification": build_classification_prompt(
        "how many orders", "shop", summary_text
    ),
    "input_analysis": build_input_analysis_prompt(
        "how many orders", "shop", summary_text
    ),
    "data_discovery": build_data_discovery_prompt(
        "how many orders", "SCHEMA", "shop"
    ),
    "context": build_context_prompt(
        "and in 2024?",
        [{"role": "user", "content": "orders in 2023"}],
        "shop"
    ),
    "entity": build_entity_prompt("orders for alice", "shop"),
    "clarification": build_clarification_prompt(
        "show me data", "shop", summary_text
    ),
    "answer": build_answer_prompt(
        "q", "SELECT 1", ["a"], [(1,)], 1, [], "english", "shop"
    ),
    "multiple_answer": build_multiple_answer_prompt(
        "q", [], "english", "shop"
    ),
    "multiple_question": build_multiple_question_prompt("q", "shop"),
}

for name, text_value in PROMPTS.items():

    check(
        f"prompt[{name}]: no 'Chinook' and no unresolved placeholders",
        "Chinook" not in text_value
        and "{db_name}" not in text_value
        and "{schema_summary}" not in text_value
    )

check(
    "classification/input/clarification prompts include the table summary",
    all(
        "- users: id, name, email" in PROMPTS[key]
        for key in ("classification", "input_analysis", "clarification")
    )
)

check(
    "clarification prompt no longer hardcodes music categories",
    "Artists" not in PROMPTS["clarification"]
    and "Playlists" not in PROMPTS["clarification"]
)

check(
    "default db_name keeps the original Chinook wording (demo)",
    "Chinook" in build_classification_prompt("hi")
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
