from auth.roles import Roles


PUBLIC = "PUBLIC"
RESTRICTED = "RESTRICTED"
DENIED = "DENIED"


# سياسة الداتابيز التجريبية (Chinook) المكتوبة يدويًا. أي داتابيز تانية
# بتاخد سياسة تلقائية من authorization/policy_builder.py. شكل أي سياسة:
#
#     { "TableName": { "ColumnName": RESTRICTED | DENIED } }
#
# أي عمود مش مذكور = PUBLIC.
ACCESS_POLICY = {

    # -----------------------------------------------------
    # Customer table
    # -----------------------------------------------------
    "Customer": {

        # Contact info - ADMIN يقدر يشوفها، USER لأ
        "Email": RESTRICTED,
        "Phone": RESTRICTED,
        "Address": RESTRICTED,
        "Fax": RESTRICTED,

        # -------------------------------------------------
        # Defensive entries: أعمدة مش موجودة فعليًا في
        # Chinook دلوقتي، لكن لو اتضافت مستقبلاً هتتمنع
        # تلقائيًا حتى من الـ ADMIN
        # -------------------------------------------------
        "Password": DENIED,
        "CreditCardNumber": DENIED,
        "BankAccountNumber": DENIED,
        "SSN": DENIED,
        "NationalId": DENIED,
    },

    # -----------------------------------------------------
    # Employee table
    # -----------------------------------------------------
    "Employee": {

        # Personal/contact info - ADMIN يقدر يشوفها
        "Address": RESTRICTED,
        "City": RESTRICTED,
        "State": RESTRICTED,
        "Country": RESTRICTED,
        "PostalCode": RESTRICTED,
        "Phone": RESTRICTED,
        "Fax": RESTRICTED,
        "Email": RESTRICTED,
        "BirthDate": RESTRICTED,

        # -------------------------------------------------
        # Defensive entries (لأعمدة مش موجودة دلوقتي)
        # -------------------------------------------------
        "Password": DENIED,
        "SSN": DENIED,
        "SalaryAmount": DENIED,
        "BankAccountNumber": DENIED,
    },

    # -----------------------------------------------------
    # Invoice table - defensive entry للـ Financial data
    # لو اتضافت بيانات دفع تفصيلية مستقبلاً
    # -----------------------------------------------------
    "Invoice": {
        "CreditCardNumber": DENIED,
        "PaymentToken": DENIED,
    },
}


ROLE_PERMISSIONS = {

    Roles.USER: {
        PUBLIC: True,
        RESTRICTED: False,
        DENIED: False,
    },

    Roles.ADMIN: {
        PUBLIC: True,
        RESTRICTED: True,
        DENIED: False,   # لاحظ: False حتى للـ ADMIN — ده المقصود
    }
}


# ترتيب الصرامة: PUBLIC < RESTRICTED < DENIED (الأشد بيكسب في الدمج)
SENSITIVITY_RANK = {
    PUBLIC: 0,
    RESTRICTED: 1,
    DENIED: 2,
}


def merge_policies(*policies):
    """
    بتدمج أكتر من سياسة. لو نفس العمود ظهر في أكتر من واحدة، الأشد
    صرامة بيكسب (مفيش سياسة تقدر "تفتح" عمود قفلته سياسة تانية).
    """

    merged = {}

    for policy in policies:

        for table_name, columns in (policy or {}).items():

            target = merged.setdefault(table_name, {})

            for column_name, sensitivity in columns.items():

                current = target.get(column_name, PUBLIC)

                if (
                    SENSITIVITY_RANK[sensitivity]
                    > SENSITIVITY_RANK[current]
                ):
                    target[column_name] = sensitivity

    return merged


def get_data_sensitivity(
    table_name: str,
    column_name: str,
    policy: dict = None
):
    """
    policy=None -> السياسة اليدوية بتاعة Chinook (للتوافق).
    في التطبيق، authorization.py دايمًا بيمرّر السياسة الفعلية
    بتاعة الـ Session.

    البحث بيتم بالاسم الحرفي الأول، وبعدين من غير حساسية لحالة
    الحروف (Fail-Safe: لو فيه عمود "email" و"Email" نعتبرهم نفس
    الشيء ونطبّق الأشد).
    """

    if policy is None:
        policy = ACCESS_POLICY

    table_policy = policy.get(
        table_name,
        {}
    )

    exact = table_policy.get(
        column_name,
        PUBLIC
    )

    folded = column_name.casefold()

    for name, sensitivity in table_policy.items():

        if (
            name.casefold() == folded
            and SENSITIVITY_RANK[sensitivity]
            > SENSITIVITY_RANK[exact]
        ):
            exact = sensitivity

    return exact


def is_access_allowed(
    role: str,
    sensitivity: str
):

    role = role.upper()

    if role not in ROLE_PERMISSIONS:

        raise ValueError(
            f"Unknown role: {role}"
        )

    permissions = ROLE_PERMISSIONS[
        role
    ]

    return permissions.get(
        sensitivity,
        False
    )


def visible_schema(
    schema: dict,
    role: str,
    policy: dict = None
) -> dict:
    """
    نسخة من الـ Schema فيها بس الأعمدة المسموحة للـ role ده.

    بتتستخدم لأي حاجة بتتعرض للمستخدم أو بتتبعت للـ LLM علشان يصيغها
    (Discovery، أسئلة التوضيح)، فأسماء الأعمدة الحساسة ما بتظهرش أصلًا.
    جدول كل أعمدته ممنوعة بيتشال بالكامل.
    """

    visible = {}

    for table_name, table_info in schema.items():

        columns = [
            column
            for column in table_info["columns"]
            if is_access_allowed(
                role,
                get_data_sensitivity(
                    table_name,
                    column["name"],
                    policy
                )
            )
        ]

        if not columns:
            continue

        allowed_names = {column["name"] for column in columns}

        visible[table_name] = {
            "columns": columns,
            "foreign_keys": [
                foreign_key
                for foreign_key in table_info.get("foreign_keys", [])
                if set(foreign_key["column"]) <= allowed_names
            ]
        }

    return visible
