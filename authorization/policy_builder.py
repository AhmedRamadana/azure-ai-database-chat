"""
policy_builder.py

بناء سياسة وصول (Access Policy) تلقائية لأي داتابيز، بالاعتماد على
أسماء الأعمدة بس.

    DENIED      -> محدش يشوفه، حتى الـ ADMIN (باسوردات، توكنز، كروت، هويات)
    RESTRICTED  -> الـ ADMIN بس (إيميل، تليفون، عنوان، تاريخ ميلاد، مرتب)

⚠️ ده كشف تقريبي (Heuristic). مش بيعرف معنى العمود ولا شوية بيانات
فعلًا. ممكن يفوّت عمود حساس اسمه غريب (مثلًا "col7")، وممكن يحجب
عمود بريء. فهو شبكة أمان إضافية فوق صلاحيات الداتابيز نفسها
(يوزر Read-Only بصلاحيات أعمدة)، مش بديل ليها. التطبيق بيوضّح ده
للمستخدم في الـ Sidebar.

شكل السياسة (نفس شكل ACCESS_POLICY اليدوية):

    { "TableName": { "ColumnName": "RESTRICTED" | "DENIED" } }

أي عمود مش مذكور = PUBLIC.
"""

import re

from authorization.access_policy import (
    ACCESS_POLICY,
    DENIED,
    PUBLIC,
    RESTRICTED,
    merge_policies
)


# ============================================================
# Rules
#
# بنقسّم اسم العمود لكلمات (tokens) علشان نتجنب الإيجابيات
# الكاذبة: "Discard" مش "card"، و"Hashtag" مش "hash"،
# و"SecretaryId" مش "secret". بينما "BillingAddress" =
# [billing, address] فبيتمسك.
#
# "squashed" = الاسم متلزّق وحروفه صغيرة ("billingaddress")، بنستخدمه
# للكلمات الطويلة اللي مفيش خطر إنها تظهر جوه كلمة بريئة.
# ============================================================

# --- DENIED: كلمات كاملة (token) ---------------------------------
DENIED_TOKENS = {
    "password", "passwd", "pwd", "passphrase",
    "secret",
    "token",
    "apikey",
    "cvv", "cvc",
    "iban",
    "ssn",
    "hash",
}

# --- DENIED: جوه الاسم المتلزّق ----------------------------------
DENIED_SQUASHED = (
    "password",
    "passwd",
    "apikey",
    "creditcard",
    "debitcard",
    "cardnumber",
    "nationalid",
    "socialsecurity",
    "accesstoken",
    "authtoken",
    "refreshtoken",
    "secretkey",
    "privatekey",
    "bankaccount",
    "accountnumber",
    "routingnumber",
)

# كلمة "card" لوحدها مش دايمًا بطاقة دفع (كروت لعبة مثلًا)، فبتبقى
# DENIED بس لو معاها كلمة بتدل على الدفع، وغير كده RESTRICTED.
PAYMENT_COMPANIONS = {
    "credit", "debit", "payment", "bank",
    "number", "no", "num", "expiry", "expiration",
    "holder", "cvv", "cvc", "pan",
}

# "token" في عمود زي token_count هو عدّاد مش مفتاح سري.
NON_SECRET_COMPANIONS = {
    "count", "len", "length", "size", "total", "num", "limit",
    "usage", "used", "max", "min", "avg",
}

# --- RESTRICTED: كلمات كاملة -------------------------------------
RESTRICTED_TOKENS = {
    "email", "emails", "mail",
    "phone", "telephone", "tel", "mobile", "cell", "msisdn",
    "fax",
    "dob",
    "salary", "salaries", "wage", "wages", "payroll",
}

# --- RESTRICTED: جوه الاسم المتلزّق ------------------------------
# (كلها كلمات طويلة بما يكفي. "phone" مش هنا عشان "headphones" و
# "saxophone" في داتابيز موسيقى.)
RESTRICTED_SQUASHED = (
    "email",
    "address",
    "birth",
    "salary",
    "phonenumber",
    "telephone",
    "mobilenumber",
)


# ============================================================
# Column classification
# ============================================================

_CAMEL_1 = re.compile(r"([a-z0-9])([A-Z])")
_CAMEL_2 = re.compile(r"([A-Z]+)([A-Z][a-z])")


def tokenize_column_name(name: str) -> list:
    """
    "BillingAddress" -> ["billing", "address"]
    "password_hash"  -> ["password", "hash"]
    "SSN"            -> ["ssn"]
    "APIKey"         -> ["api", "key"]
    """

    spaced = _CAMEL_1.sub(r"\1 \2", name)
    spaced = _CAMEL_2.sub(r"\1 \2", spaced)

    return [
        token
        for token in re.split(r"[^A-Za-z0-9]+", spaced.lower())
        if token
    ]


def classify_column(column_name: str) -> str:
    """
    بترجّع PUBLIC / RESTRICTED / DENIED بناءً على الاسم بس.
    """

    tokens = tokenize_column_name(column_name)

    if not tokens:
        return PUBLIC

    token_set = set(tokens)

    # "api" + "key" بتتقسم لكلمتين، فبنلصقهم تاني
    squashed = "".join(tokens)

    # ---------------- DENIED ----------------

    secret_like = token_set & DENIED_TOKENS

    if "token" in secret_like and (token_set & NON_SECRET_COMPANIONS):
        secret_like = secret_like - {"token"}

    if secret_like:
        return DENIED

    if any(word in squashed for word in DENIED_SQUASHED):
        return DENIED

    if "card" in token_set:

        if (token_set & PAYMENT_COMPANIONS):
            return DENIED

        return RESTRICTED

    if "national" in token_set and "id" in token_set:
        return DENIED

    # ---------------- RESTRICTED ----------------

    if token_set & RESTRICTED_TOKENS:
        return RESTRICTED

    if any(word in squashed for word in RESTRICTED_SQUASHED):
        return RESTRICTED

    return PUBLIC


# ============================================================
# Policy building
# ============================================================

_VALID_LEVELS = (PUBLIC, RESTRICTED, DENIED)


def _apply_overrides(policy: dict, schema: dict, overrides: dict):
    """
    بتطبّق overrides ({ "Table.Column": level }) على policy في مكانها.
    القرار الصريح بيغلب أي كشف تلقائي أو سياسة يدوية (في الاتجاهين).
    """

    for key, level in (overrides or {}).items():

        if level not in _VALID_LEVELS:

            raise ValueError(
                f"Invalid sensitivity for {key!r}: {level!r}"
            )

        table_name, _, column_name = key.partition(".")

        known_columns = {
            column["name"]
            for column in schema.get(table_name, {}).get("columns", [])
        }

        if column_name not in known_columns:

            raise ValueError(
                f"Unknown column in overrides: {key!r}"
            )

        if level == PUBLIC:

            policy.get(table_name, {}).pop(column_name, None)

        else:

            policy.setdefault(table_name, {})[column_name] = level

    return policy


def _drop_empty(policy: dict) -> dict:

    return {
        table: columns
        for table, columns in policy.items()
        if columns
    }


def build_policy(schema: dict, overrides: dict = None) -> dict:
    """
    schema: { table: {"columns": [{"name": ..., "type": ...}], ...} }

    overrides: { "Table.Column": "PUBLIC" | "RESTRICTED" | "DENIED" }
    (محتاجة لأن الكشف التقريبي ممكن يغلط. مثلًا عمود "mail_id" ممكن
    يكون رقم بريدي مش إيميل.)

    بترجّع بس الأعمدة اللي مش PUBLIC.
    """

    policy = {}

    for table_name, table_info in schema.items():

        for column in table_info["columns"]:

            level = classify_column(column["name"])

            if level != PUBLIC:

                policy.setdefault(table_name, {})[
                    column["name"]
                ] = level

    return _drop_empty(
        _apply_overrides(policy, schema, overrides)
    )


def build_effective_policy(
    schema: dict,
    is_demo: bool = False,
    overrides: dict = None
) -> dict:
    """
    السياسة الفعلية اللي بتتطبق على Session:

      الداتابيز التجريبية: السياسة اليدوية بتاعة Chinook + الكشف
                           التلقائي (الأشد بيكسب). ده بيغطي أعمدة
                           زي Invoice.BillingAddress اللي السياسة
                           اليدوية ما كانتش مغطياها.
      أي داتابيز تانية:   الكشف التلقائي بس.

    الـ overrides بتتطبق في الآخر وبتغلب على الاتنين.
    """

    policies = [build_policy(schema)]

    if is_demo:
        policies.insert(0, ACCESS_POLICY)

    merged = merge_policies(*policies)

    return _drop_empty(
        _apply_overrides(merged, schema, overrides)
    )


def resolve_policy(schema: dict, policy: dict = None) -> dict:
    """
    بتحدد السياسة المستخدمة لما حد ينادي authorization من غير ما
    يمرّر policy (توافق مع الكود القديم والاختبارات).

    الافتراضي = السياسة اليدوية + التلقائية (مش اليدوية لوحدها)،
    عشان نسيان تمرير الـ policy على داتابيز مخصصة ما يبقاش Fail-Open.
    """

    if policy is not None:
        return policy

    return build_effective_policy(
        schema,
        is_demo=True
    )


# ============================================================
# Presentation helpers (للـ Sidebar)
# ============================================================

def summarize_policy(policy: dict) -> dict:
    """
    بترجّع:
        {"RESTRICTED": ["Customer.Email", ...], "DENIED": [...]}
    """

    summary = {RESTRICTED: [], DENIED: []}

    for table_name in sorted(policy):

        for column_name in sorted(policy[table_name]):

            level = policy[table_name][column_name]

            if level in summary:
                summary[level].append(
                    f"{table_name}.{column_name}"
                )

    return summary
