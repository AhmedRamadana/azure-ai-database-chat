"""
اختبارات الـ Authorization لحالات SELECT * والصف الكامل والرفض الجزئي.

مش محتاجة داتابيز ولا .env — بتستخدم Schema وهمي على شكل Chinook.

التشغيل (من روت المشروع):

    python -m tests.test_star_authorization
"""

import os
import sys

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from authorization.authorization import (
    apply_column_authorization
)


def _table(*columns):

    return {
        "columns": [
            {"name": name, "type": "TEXT"}
            for name in columns
        ],
        "foreign_keys": []
    }


FAKE_SCHEMA = {

    "Customer": _table(
        "CustomerId", "FirstName", "LastName", "Company",
        "Address", "City", "State", "Country", "PostalCode",
        "Phone", "Fax", "Email", "SupportRepId"
    ),

    "Employee": _table(
        "EmployeeId", "LastName", "FirstName", "Title",
        "ReportsTo", "BirthDate", "HireDate", "Address", "City",
        "State", "Country", "PostalCode", "Phone", "Fax", "Email"
    ),

    "Invoice": _table(
        "InvoiceId", "CustomerId", "InvoiceDate", "BillingCountry",
        "Total"
    ),

    "Artist": _table("ArtistId", "Name"),

    "Track": _table("TrackId", "Name", "AlbumId", "UnitPrice"),
}

USER = {"user_id": "t", "role": "USER"}
ADMIN = {"user_id": "t", "role": "ADMIN"}

RESULTS = []


def check(name, condition):

    RESULTS.append(bool(condition))

    print(("PASS: " if condition else "FAIL: ") + name)


def run(sql, user):

    return apply_column_authorization(sql, user, FAKE_SCHEMA)


def denied(sql, user):

    try:

        run(sql, user)

    except PermissionError:

        return True

    return False


def main():

    print("--- Star / Whole-row / Partial Authorization Tests ---\n")

    # ---------------------------------------------------------
    # SELECT *  (الحالة اللي سرّبت بيانات العميل رقم 6)
    # ---------------------------------------------------------

    sql, removed = run(
        'SELECT * FROM "Customer" '
        'WHERE "Customer"."CustomerId" = 6;',
        USER
    )

    check(
        "USER: SELECT * hides Email/Phone/Address/Fax",
        sorted(removed) == [
            "Customer.Address",
            "Customer.Email",
            "Customer.Fax",
            "Customer.Phone",
        ]
        and '"Email"' not in sql
        and '"Phone"' not in sql
        and '"Address"' not in sql
        and '"Fax"' not in sql
        and '"FirstName"' in sql
        and "*" not in sql
    )

    sql, removed = run(
        'SELECT * FROM "Customer" '
        'WHERE "Customer"."CustomerId" = 6;',
        ADMIN
    )

    check(
        "ADMIN: SELECT * is allowed (nothing removed)",
        removed == [] and "*" in sql
    )

    sql, removed = run(
        'SELECT "Customer".* FROM "Customer";',
        USER
    )

    check(
        'USER: "Customer".* hides restricted columns',
        "Customer.Email" in removed
        and '"Email"' not in sql
    )

    sql, removed = run(
        'SELECT c.* FROM "Customer" c WHERE c."CustomerId" = 6;',
        USER
    )

    check(
        "USER: alias.* hides restricted columns",
        "Customer.Email" in removed
        and '"Email"' not in sql
    )

    sql, removed = run(
        'SELECT * FROM "Customer" AS c;',
        USER
    )

    check(
        "USER: SELECT * with 'AS alias' hides restricted columns",
        "Customer.Phone" in removed
        and '"Phone"' not in sql
    )

    sql, removed = run(
        'SELECT * FROM "Employee";',
        USER
    )

    check(
        "USER: Employee SELECT * keeps only non-sensitive columns",
        '"FirstName"' in sql
        and '"HireDate"' in sql
        and '"Email"' not in sql
        and '"BirthDate"' not in sql
        and '"Phone"' not in sql
    )

    sql, removed = run(
        'SELECT * FROM "Customer" JOIN "Invoice" '
        'ON "Customer"."CustomerId" = "Invoice"."CustomerId";',
        USER
    )

    check(
        "USER: SELECT * with JOIN expands both, hides Email, "
        "aliases duplicate names",
        "Customer.Email" in removed
        and '"Customer_CustomerId"' in sql
        and '"Invoice_CustomerId"' in sql
        and '"Total"' in sql
    )

    sql, removed = run('SELECT * FROM "Artist";', USER)

    check(
        "USER: SELECT * on a table with no restricted columns "
        "is untouched",
        removed == [] and sql == 'SELECT * FROM "Artist";'
    )

    # ---------------------------------------------------------
    # الصف كامل (whole-row)
    # ---------------------------------------------------------

    check(
        'USER: SELECT "Customer" (whole row) is denied',
        denied('SELECT "Customer" FROM "Customer";', USER)
    )

    check(
        'USER: row_to_json("Customer") is denied',
        denied(
            'SELECT row_to_json("Customer") FROM "Customer";',
            USER
        )
    )

    check(
        'USER: row_to_json("Customer".*) is denied',
        denied(
            'SELECT row_to_json("Customer".*) FROM "Customer";',
            USER
        )
    )

    check(
        'USER: whole row through alias (SELECT c FROM "Customer" c) '
        'is denied',
        denied('SELECT c FROM "Customer" c;', USER)
    )

    check(
        'USER: "Customer"::text is denied',
        denied('SELECT "Customer"::text FROM "Customer";', USER)
    )

    # ---------------------------------------------------------
    # الرفض الجزئي (الحالة اللي كانت شغالة وبنتأكد إنها لسه كده)
    # ---------------------------------------------------------

    sql, removed = run(
        'SELECT "Customer"."FirstName", "Customer"."Email" '
        'FROM "Customer" WHERE "Customer"."CustomerId" = 13;',
        USER
    )

    check(
        "USER: name + email -> name only, Email reported",
        removed == ["Customer.Email"]
        and '"FirstName"' in sql
        and '"Email"' not in sql
    )

    sql, removed = run(
        'SELECT "FirstName", MAX("Email") FROM "Customer" '
        'GROUP BY "FirstName";',
        USER
    )

    check(
        "USER: MAX(Email) is removed, other columns kept",
        removed == ["Customer.Email"]
        and 'MAX' not in sql
        and '"FirstName"' in sql
    )

    check(
        "USER: only restricted column requested -> denied",
        denied('SELECT DISTINCT "Email" FROM "Customer";', USER)
    )

    check(
        "USER: COUNT(Email) alone -> denied",
        denied('SELECT COUNT("Email") FROM "Customer";', USER)
    )

    # ---------------------------------------------------------
    # عمود ممنوع بره الـ SELECT list -> رفض كامل
    # ---------------------------------------------------------

    check(
        "USER: restricted column in WHERE -> denied",
        denied(
            'SELECT "FirstName" FROM "Customer" '
            'WHERE "Email" LIKE \'a%\';',
            USER
        )
    )

    check(
        "ADMIN: restricted column in WHERE -> allowed",
        not denied(
            'SELECT "FirstName" FROM "Customer" '
            'WHERE "Email" LIKE \'a%\';',
            ADMIN
        )
    )

    check(
        "USER: restricted column in ORDER BY -> denied",
        denied(
            'SELECT "FirstName" FROM "Customer" '
            'ORDER BY "Customer"."Email";',
            USER
        )
    )

    check(
        "USER: restricted column inside a subquery -> denied",
        denied(
            'SELECT "FirstName" FROM "Customer" WHERE "CustomerId" '
            'IN (SELECT "CustomerId" FROM "Customer" '
            'WHERE "Email" = \'x\');',
            USER
        )
    )

    check(
        "USER: UNION with a restricted column -> denied",
        denied(
            'SELECT "FirstName" FROM "Customer" '
            'UNION SELECT "Email" FROM "Customer";',
            USER
        )
    )

    check(
        "USER: alias of a removed column used in ORDER BY -> denied",
        denied(
            'SELECT "Customer"."Email" AS "Contact", '
            '"Customer"."FirstName" FROM "Customer" '
            'ORDER BY "Contact";',
            USER
        )
    )

    check(
        "USER: positional ORDER BY with a removed column -> denied",
        denied(
            'SELECT "FirstName", "Email" FROM "Customer" ORDER BY 1;',
            USER
        )
    )

    check(
        "USER: quoted alias hiding a restricted column -> denied",
        denied(
            'SELECT "c"."Email" FROM "Customer" AS "c";',
            USER
        )
    )

    check(
        "USER: SELECT * with comma-join is denied (cannot verify)",
        denied(
            'SELECT * FROM "Customer", "Invoice";',
            USER
        )
    )


    # ---------------------------------------------------------
    # subqueries + SELECT *
    # ---------------------------------------------------------

    check(
        "USER: SELECT * FROM (SELECT * FROM Customer) is denied",
        denied(
            'SELECT * FROM (SELECT * FROM "Customer") t;',
            USER
        )
    )

    check(
        "USER: t.* over a derived table is denied",
        denied(
            'SELECT t.* FROM (SELECT * FROM "Customer") t;',
            USER
        )
    )

    check(
        "USER: wildcard inside EXISTS on a restricted table "
        "is denied",
        denied(
            'SELECT "FirstName" FROM "Customer" WHERE EXISTS '
            '(SELECT * FROM "Customer" c);',
            USER
        )
    )

    check(
        "USER: normal public subquery is allowed",
        not denied(
            'SELECT "FirstName" FROM "Customer" WHERE "CustomerId" '
            'IN (SELECT "CustomerId" FROM "Invoice");',
            USER
        )
    )

    check(
        "USER: wildcard inside EXISTS on public tables is allowed",
        not denied(
            'SELECT "Name" FROM "Artist" WHERE EXISTS '
            '(SELECT * FROM "Track");',
            USER
        )
    )

    sql, removed = run(
        'SELECT *, "Email" FROM "Customer";',
        USER
    )

    check(
        "USER: SELECT *, Email -> both expansion and strip apply",
        "Customer.Email" in removed
        and '"Email"' not in sql
        and '"FirstName"' in sql
    )

    # ---------------------------------------------------------
    # لازم تعدّي زي ما هي (مفيش False Positives)
    # ---------------------------------------------------------

    sql, removed = run('SELECT COUNT(*) FROM "Customer";', USER)

    check(
        "USER: COUNT(*) is untouched",
        removed == [] and sql == 'SELECT COUNT(*) FROM "Customer";'
    )

    sql, removed = run(
        'SELECT "Customer"."FirstName", "Invoice"."Total" '
        'FROM "Customer" JOIN "Invoice" '
        'ON "Customer"."CustomerId" = "Invoice"."CustomerId";',
        USER
    )

    check(
        "USER: normal public JOIN is untouched",
        removed == []
    )

    check(
        "USER: a restricted column name inside a string literal "
        "is not a column reference",
        not denied(
            'SELECT "FirstName" FROM "Customer" '
            'WHERE "FirstName" = \'Email\';',
            USER
        )
    )

    check(
        "USER: EXTRACT(YEAR FROM ...) in SELECT list is parsed "
        "correctly",
        not denied(
            'SELECT EXTRACT(YEAR FROM "Invoice"."InvoiceDate"), '
            'COUNT(*) FROM "Invoice" GROUP BY 1;',
            USER
        )
    )

    print()

    passed = sum(RESULTS)

    print(f"{passed}/{len(RESULTS)} passed")

    print("\n--- Tests Completed ---")

    if passed != len(RESULTS):

        sys.exit(1)


if __name__ == "__main__":

    main()