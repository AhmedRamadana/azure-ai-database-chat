from auth.roles import Roles


PUBLIC = "PUBLIC"
RESTRICTED = "RESTRICTED"
DENIED = "DENIED"


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


def get_data_sensitivity(
    table_name: str,
    column_name: str
):

    table_policy = ACCESS_POLICY.get(
        table_name,
        {}
    )

    return table_policy.get(
        column_name,
        PUBLIC
    )


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