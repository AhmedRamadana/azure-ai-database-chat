"""
sql_scan.py

أدوات مساعدة صغيرة لتحليل شكل الـ SQL من غير ما نعتمد على Regex
مباشر على النص الخام (اللي بيتلخبط مع الـ strings والأقواس).

الفكرة: نعمل "قناع" (mask) للنص بنفس الطول بالظبط:

    structure   -> محتوى الـ string literals بيتحوّل لـ ~
                   ومحتوى الـ "quoted identifiers" بيتحوّل لـ #
                   (بنستخدمه للبحث عن الكلمات المفتاحية وحساب الأقواس)

    no_strings  -> محتوى الـ string literals بس بيتحوّل لمسافات
                   والـ "quoted identifiers" بتفضل زي ما هي
                   (بنستخدمه لاستخراج أسماء الجداول والأعمدة)

لأن الطولين ثابتين، أي موقع (index) في الـ mask هو نفس الموقع في
الـ SQL الأصلي.
"""

import re


def mask_sql(sql: str):
    """
    بترجّع: (structure, no_strings, balanced)

    balanced = False لو فيه quote مش مقفول.
    """

    structure = []
    no_strings = []

    state = None  # None | "'" | '"'

    i = 0
    n = len(sql)

    while i < n:

        ch = sql[i]

        if state is None:

            if ch == "'":

                state = "'"
                structure.append("'")
                no_strings.append(" ")

            elif ch == '"':

                state = '"'
                structure.append('"')
                no_strings.append('"')

            else:

                structure.append(ch)
                no_strings.append(ch)

        elif state == "'":

            if ch == "'":

                if i + 1 < n and sql[i + 1] == "'":

                    # '' جوه string = علامة اقتباس عادية
                    structure.append("~~")
                    no_strings.append("  ")
                    i += 1

                else:

                    state = None
                    structure.append("'")
                    no_strings.append(" ")

            else:

                structure.append("~")
                no_strings.append(" ")

        else:  # جوه "quoted identifier"

            if ch == '"':

                if i + 1 < n and sql[i + 1] == '"':

                    structure.append("##")
                    no_strings.append('""')
                    i += 1

                else:

                    state = None
                    structure.append('"')
                    no_strings.append('"')

            else:

                structure.append("#")
                no_strings.append(ch)

        i += 1

    return (
        "".join(structure),
        "".join(no_strings),
        state is None
    )


def paren_depths(structure: str):
    """
    بترجّع قايمة بنفس طول النص: عمق الأقواس عند كل حرف.
    """

    depths = []
    depth = 0

    for ch in structure:

        if ch == "(":

            depths.append(depth)
            depth += 1

        elif ch == ")":

            depth -= 1
            depths.append(depth)

        else:

            depths.append(depth)

    return depths


def select_list_span(structure: str, depths=None):
    """
    بترجّع (start, end) لقايمة الأعمدة بتاعة أول SELECT:
    من بعد كلمة SELECT (وبعد DISTINCT لو موجودة) لحد أول FROM
    على المستوى الأساسي (مش جوه أقواس، عشان EXTRACT(.. FROM ..)
    وما شابه).

    لو ملقتش، بترجّع None.
    """

    match = re.search(
        r"\bSELECT\b",
        structure,
        flags=re.IGNORECASE
    )

    if not match:
        return None

    start = match.end()

    distinct = re.match(
        r"\s+DISTINCT\b",
        structure[start:],
        flags=re.IGNORECASE
    )

    if distinct:
        start += distinct.end()

    if depths is None:
        depths = paren_depths(structure)

    for from_match in re.finditer(
        r"\bFROM\b",
        structure[start:],
        flags=re.IGNORECASE
    ):

        position = start + from_match.start()

        if depths[position] == 0:
            return start, position

    return None


def split_top_level_commas(
    structure: str,
    depths,
    start: int,
    end: int
):
    """
    بتقسم المدى [start, end) على الفواصل اللي على المستوى الأساسي
    بس (مش جوه أقواس). بترجّع قايمة (s, e).
    """

    spans = []
    current = start

    for i in range(start, end):

        if structure[i] == "," and depths[i] == 0:

            spans.append((current, i))
            current = i + 1

    if structure[current:end].strip():
        spans.append((current, end))

    return spans