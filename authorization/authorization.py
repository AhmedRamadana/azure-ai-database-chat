import re

from authorization.access_policy import (
    get_data_sensitivity,
    is_access_allowed
)

from authorization.policy_builder import (
    resolve_policy
)

from sql_scan import (
    mask_sql,
    paren_depths,
    select_list_span,
    split_top_level_commas
)


# ============================================================
# Patterns
# ============================================================

QUALIFIED_RE = re.compile(
    r'"(?P<table>[^"]+)"\s*\.\s*"(?P<column>[^"]+)"'
)

QUOTED_RE = re.compile(
    r'"([^"]+)"'
)

WORD_RE = re.compile(
    r'\b[A-Za-z_][A-Za-z0-9_]*\b'
)

# عنصر في الـ SELECT list شكله: *  أو  "T".*  أو  t.*
STAR_ITEM_RE = re.compile(
    r'^(?:(?P<q>"[^"]+"|[A-Za-z_]\w*)\s*\.\s*)?\*$'
)

# أي "T".* أو t.* (بنستخدمها نكشف whole-row جوه دوال زي row_to_json)
DOT_STAR_RE = re.compile(
    r'(?P<q>"[^"]+"|[A-Za-z_]\w*)\s*\.\s*\*'
)

_ALIAS_STOPWORDS = (
    "JOIN|INNER|LEFT|RIGHT|FULL|CROSS|NATURAL|OUTER|ON|USING|WHERE|"
    "GROUP|ORDER|HAVING|LIMIT|OFFSET|FETCH|UNION|INTERSECT|EXCEPT|"
    "FOR|WINDOW|LATERAL"
)

# FROM "Table" [AS] [alias]
FROM_ENTRY_RE = re.compile(
    r'\b(?:FROM|JOIN)\s+"(?P<table>[^"]+)"'
    r'(?:\s+(?:AS\s+)?'
    r'(?!(?:' + _ALIAS_STOPWORDS + r')\b)'
    r'(?P<alias>"[^"]+"|[A-Za-z_]\w*))?',
    flags=re.IGNORECASE
)


# ============================================================
# Helpers: الجداول والـ aliases
# ============================================================

def _from_entries(no_strings: str):
    """
    كل جدول مذكور بعد FROM/JOIN، مع الـ alias بتاعه لو فيه.
    """

    entries = []

    for match in FROM_ENTRY_RE.finditer(no_strings):

        alias = match.group("alias")

        alias_name = None

        if alias:

            alias_name = (
                alias[1:-1]
                if alias.startswith('"')
                else alias
            )

        entries.append(
            {
                "table": match.group("table"),
                "alias": alias,
                "alias_name": alias_name,
                "alias_span": (
                    match.span("alias")
                    if alias
                    else None
                )
            }
        )

    return entries


def _referenced_tables(no_strings: str, entries, schema):
    """
    كل الجداول "المذكورة" في الاستعلام: اللي بعد FROM/JOIN، وكمان
    أي quoted identifier اسمه اسم جدول معروف (بيغطي الـ comma-joins
    والـ subqueries). مجموعة أوسع عن قصد (Fail-Safe).
    """

    tables = {entry["table"] for entry in entries}

    for match in QUOTED_RE.finditer(no_strings):

        if match.group(1) in schema:

            tables.add(match.group(1))

    return tables


def _disallowed_columns(table_name, role, schema, policy):
    """
    أعمدة الجدول ده اللي الـ role مش مسموحله بيها (حسب policy).
    """

    if table_name not in schema:
        return []

    return [
        column["name"]
        for column in schema[table_name]["columns"]
        if not is_access_allowed(
            role,
            get_data_sensitivity(
                table_name,
                column["name"],
                policy
            )
        )
    ]


def _inside_any(spans, position):

    for start, end in spans:

        if start <= position < end:
            return True

    return False


# ============================================================
# استخراج كل الـ references (table, column) من جزء من الاستعلام
# ============================================================

def _references(
    ns_segment: str,
    st_segment: str,
    tables,
    schema,
    alias_to_table
):
    """
    بترجّع مجموعة (table, column) اللي الجزء ده من الاستعلام بيشاور
    عليها. الأعمدة الغير مؤهلة بتتفحص ضد كل الجداول المذكورة
    (Conservative).
    """

    refs = set()

    qualified_spans = []

    for match in QUALIFIED_RE.finditer(ns_segment):

        qualified_spans.append(match.span())

        table = match.group("table")
        column = match.group("column")

        if table in schema:

            refs.add((table, column))

        elif table in alias_to_table:

            refs.add((alias_to_table[table], column))

        else:

            # مش جدول ولا alias معروف: نعامله كعمود غير مؤهل
            for candidate in tables:
                refs.add((candidate, column))

    for match in QUOTED_RE.finditer(ns_segment):

        if _inside_any(qualified_spans, match.start()):
            continue

        name = match.group(1)

        if name in schema:
            continue

        for candidate in tables:
            refs.add((candidate, name))

    # كلمات من غير quotes: Postgres بيحوّلها lowercase، فمش هتطابق
    # غير أعمدة اسمها lowercase أصلاً. مهم للداتابيز المخصصة.
    for match in WORD_RE.finditer(st_segment):

        word = match.group(0).lower()

        for candidate in tables:
            refs.add((candidate, word))

    return refs


class _Parsed:
    """
    نتيجة تحليل استعلام واحد، عشان منكررش الشغل.
    """

    def __init__(self, sql, schema, policy):

        self.sql = sql
        self.schema = schema
        self.policy = policy

        self.structure, self.ns, self.balanced = mask_sql(sql)

        self.depths = paren_depths(self.structure)

        self.entries = _from_entries(self.ns)

        self.tables = _referenced_tables(
            self.ns,
            self.entries,
            schema
        )

        self.alias_to_table = {
            entry["alias_name"]: entry["table"]
            for entry in self.entries
            if entry["alias_name"]
        }

        self.span = select_list_span(
            self.structure,
            self.depths
        )

    def refs(self, a, b):

        return _references(
            self.ns[a:b],
            self.structure[a:b],
            self.tables,
            self.schema,
            self.alias_to_table
        )

    def select_and_rest_refs(self):

        if not self.span:

            return set(), self.refs(0, len(self.sql))

        a, b = self.span

        select_refs = self.refs(a, b)

        rest_ns = self.ns[:a] + " " + self.ns[b:]
        rest_st = self.structure[:a] + " " + self.structure[b:]

        rest_refs = _references(
            rest_ns,
            rest_st,
            self.tables,
            self.schema,
            self.alias_to_table
        )

        return select_refs, rest_refs


# ============================================================
# Subqueries: SELECT جوه أقواس
# ============================================================

NESTED_STAR_RE = re.compile(
    r'\bSELECT\b\s+(?:DISTINCT\s+)?'
    r'(?:(?:"#+"|[A-Za-z_]\w*)\s*\.\s*)?\*',
    flags=re.IGNORECASE
)


def _has_nested_select(parsed):

    return any(
        parsed.depths[match.start()] > 0
        for match in re.finditer(
            r"\bSELECT\b",
            parsed.structure,
            flags=re.IGNORECASE
        )
    )


def _has_nested_star(parsed):

    return any(
        parsed.depths[match.start()] > 0
        for match in NESTED_STAR_RE.finditer(parsed.structure)
    )


def _any_disallowed(parsed, role):

    return any(
        _disallowed_columns(
            table,
            role,
            parsed.schema,
            parsed.policy
        )
        for table in parsed.tables
    )


# ============================================================
# 1) Star Expansion
#
# SELECT *  ->  SELECT "T"."Col1", "T"."Col2", ...
#
# من غير الخطوة دي، "SELECT *" كان بيعدّي من الـ Authorization لأن
# مفيش اسم عمود مكتوب يتفحص.
# ============================================================

def expand_star_select_items(
    sql_query: str,
    role: str,
    schema: dict,
    policy: dict = None
):

    policy = resolve_policy(schema, policy)

    parsed = _Parsed(sql_query, schema, policy)

    if not parsed.span:
        return sql_query

    a, b = parsed.span

    spans = split_top_level_commas(
        parsed.structure,
        parsed.depths,
        a,
        b
    )

    items = [
        (s, e, parsed.ns[s:e].strip())
        for s, e in spans
    ]

    if not any(
        STAR_ITEM_RE.match(text)
        for _, _, text in items
    ):
        return sql_query

    # لو مفيش أي جدول في الاستعلام فيه عمود ممنوع على الـ role ده،
    # الـ * مش بتكشف حاجة، ونسيب الاستعلام زي ما هو.
    if not _any_disallowed(parsed, role):
        return sql_query

    # SELECT * مع subquery (derived table): مش قادرين نحدد الأعمدة
    # بأمان، فالأأمن نرفض (بنوصل هنا بس لو فيه أعمدة ممنوعة أصلاً)
    if _has_nested_select(parsed):

        raise PermissionError(
            "Access denied. This wildcard query form "
            "cannot be verified safely."
        )

    entry_tables = {
        entry["table"]
        for entry in parsed.entries
    }

    if parsed.tables - entry_tables:

        raise PermissionError(
            "Access denied. This wildcard query form "
            "cannot be verified safely."
        )

    new_items = []

    for s, e, text in items:

        match = STAR_ITEM_RE.match(text)

        if not match:

            new_items.append(sql_query[s:e].strip())
            continue

        qualifier = match.group("q")

        if qualifier is None:

            targets = parsed.entries

        else:

            targets = _entries_for_qualifier(
                qualifier,
                parsed.entries
            )

            if not targets:

                raise PermissionError(
                    "Access denied. This wildcard query form "
                    "cannot be verified safely."
                )

        name_counts = {}

        for entry in targets:

            for column in schema[entry["table"]]["columns"]:

                name_counts[column["name"]] = (
                    name_counts.get(column["name"], 0) + 1
                )

        for entry in targets:

            if entry["alias"]:

                qualifier_text = entry["alias"]

            else:

                qualifier_text = f'"{entry["table"]}"'

            for column in schema[entry["table"]]["columns"]:

                item = f'{qualifier_text}."{column["name"]}"'

                if name_counts[column["name"]] > 1:

                    item += (
                        f' AS "{entry["table"]}_{column["name"]}"'
                    )

                new_items.append(item)

    return (
        sql_query[:a]
        + " "
        + ", ".join(new_items)
        + " "
        + sql_query[b:]
    )


def _entries_for_qualifier(qualifier, entries):

    if qualifier.startswith('"'):

        name = qualifier[1:-1]
        exact = True

    else:

        name = qualifier
        exact = False

    matched = []

    for entry in entries:

        candidate = (
            entry["alias_name"]
            if entry["alias"]
            else entry["table"]
        )

        if candidate == name or (
            not exact
            and candidate.lower() == name.lower()
        ):

            matched.append(entry)

    return matched


# ============================================================
# 2) Whole-row references (Fail Closed)
#
# SELECT "Customer" FROM "Customer"
# SELECT row_to_json("Customer") ...
# SELECT row_to_json("Customer".*) ...
#
# بترجّع قايمة جداول اتطلبت كصف كامل وفيها أعمدة ممنوعة على الـ role.
# ============================================================

def _whole_row_tables(parsed: _Parsed, role: str):

    found = set()

    ns = parsed.ns

    for match in QUOTED_RE.finditer(ns):

        name = match.group(1)

        if name not in parsed.schema:
            continue

        after = ns[match.end():].lstrip()

        if after.startswith("."):
            continue

        before = ns[:match.start()]

        if re.search(
            r"\b(?:FROM|JOIN|AS)\s*$",
            before,
            flags=re.IGNORECASE
        ):
            continue

        found.add(name)

    # alias من غير quotes اتستخدم كصف كامل: SELECT c FROM "Customer" c
    declaration_starts = {
        entry["alias_span"][0]
        for entry in parsed.entries
        if entry["alias_span"]
    }

    for entry in parsed.entries:

        alias = entry["alias"]

        if not alias or alias.startswith('"'):
            continue

        for match in re.finditer(
            r"\b" + re.escape(alias) + r"\b",
            parsed.structure,
            flags=re.IGNORECASE
        ):

            if match.start() in declaration_starts:
                continue

            after = parsed.structure[match.end():].lstrip()

            if after.startswith("."):
                continue

            found.add(entry["table"])

    # t.*  أو  "T".*  جوه دالة (لأن الـ * اللي على المستوى الأساسي
    # اتوسّعت بالفعل قبل كده)
    for match in DOT_STAR_RE.finditer(ns):

        targets = _entries_for_qualifier(
            match.group("q"),
            parsed.entries
        )

        if targets:

            for entry in targets:
                found.add(entry["table"])

        else:

            found.update(parsed.tables)

    return sorted(
        table
        for table in found
        if _disallowed_columns(
            table,
            role,
            parsed.schema,
            parsed.policy
        )
    )


# ============================================================
# 3) الأعمدة الممنوعة في الاستعلام
# ============================================================

def get_restricted_identifiers(
    sql_query: str,
    user: dict,
    schema: dict,
    policy: dict = None
):
    """
    بترجّع كل الأعمدة الممنوعة على المستخدم ده في الاستعلام، ولكل
    واحد منها select_only=True لو ظهر في الـ SELECT list بس (يعني
    ينفع نشيله بأمان)، أو False لو ظهر كمان في WHERE/ORDER BY/...
    """

    role = user.get("role")

    policy = resolve_policy(schema, policy)

    parsed = _Parsed(sql_query, schema, policy)

    select_refs, rest_refs = parsed.select_and_rest_refs()

    restricted = []

    for table, column in sorted(select_refs | rest_refs):

        sensitivity = get_data_sensitivity(
            table,
            column,
            policy
        )

        if is_access_allowed(role, sensitivity):
            continue

        restricted.append(
            {
                "table": table,
                "column": column,
                "sensitivity": sensitivity,
                "select_only": (
                    (table, column) in select_refs
                    and (table, column) not in rest_refs
                )
            }
        )

    return restricted


# ============================================================
# 4) شيل الأعمدة الممنوعة من الـ SELECT list
# ============================================================

def strip_restricted_select_items(
    sql_query: str,
    restricted_columns: list,
    schema: dict
):

    # مفيش فحص حساسية هنا (القايمة جاهزة)، فالـ policy مش مستخدمة
    parsed = _Parsed(sql_query, schema, {})

    if not parsed.span:
        return sql_query, []

    a, b = parsed.span

    restricted_keys = {
        (col["table"], col["column"])
        for col in restricted_columns
        if col["select_only"]
    }

    spans = split_top_level_commas(
        parsed.structure,
        parsed.depths,
        a,
        b
    )

    kept = []
    removed = []
    removed_aliases = []

    for s, e in spans:

        item_text = sql_query[s:e].strip()

        hits = parsed.refs(s, e) & restricted_keys

        if not hits:

            kept.append(item_text)
            continue

        for table, column in sorted(hits):

            label = f"{table}.{column}"

            if label not in removed:
                removed.append(label)

        alias_match = re.search(
            r'\bAS\s+("([^"]+)"|[A-Za-z_]\w*)\s*$',
            parsed.ns[s:e].strip(),
            flags=re.IGNORECASE
        )

        if alias_match:

            removed_aliases.append(
                alias_match.group(2)
                or alias_match.group(1)
            )

    if not kept:

        raise PermissionError(
            "Access denied. "
            "All requested fields are restricted: "
            + ", ".join(removed)
        )

    rest_ns = parsed.ns[:a] + " " + parsed.ns[b:]
    rest_st = parsed.structure[:a] + " " + parsed.structure[b:]

    # لو في عمود اتشال كان له alias واتستخدم بعد كده (ORDER BY alias)
    # الاستعلام هيبوظ أو يتغير معناه، فالأأمن نرفض.
    for alias in removed_aliases:

        if (
            f'"{alias}"' in rest_ns
            or re.search(
                r"\b" + re.escape(alias) + r"\b",
                rest_st,
                flags=re.IGNORECASE
            )
        ):

            raise PermissionError(
                "Access denied. "
                "A restricted field is used elsewhere "
                "in the query."
            )

    # ORDER BY / GROUP BY بالترتيب الرقمي (ORDER BY 2) بيتغير معناه
    # لو شيلنا عمود من الـ SELECT list.
    if removed:

        for clause in re.finditer(
            r"\b(?:ORDER|GROUP)\s+BY\b(.*?)"
            r"(?=\bLIMIT\b|\bOFFSET\b|\bHAVING\b|\bORDER\b|"
            r"\bFETCH\b|$)",
            rest_st,
            flags=re.IGNORECASE | re.DOTALL
        ):

            if re.search(r"\b\d+\b", clause.group(1)):

                raise PermissionError(
                    "Access denied. "
                    "Positional ORDER BY/GROUP BY cannot be "
                    "combined with restricted fields."
                )

    new_query = (
        sql_query[:a]
        + " "
        + ", ".join(kept)
        + " "
        + sql_query[b:]
    )

    return new_query, removed


# ============================================================
# 5) نقطة الدخول: رفض جزئي آمن
# ============================================================

def apply_column_authorization(
    sql_query: str,
    user: dict,
    schema: dict,
    policy: dict = None
):
    """
    بترجّع (query, restricted_fields):

    - مفيش حاجة ممنوعة         -> الاستعلام زي ما هو
    - ممنوع في SELECT بس       -> نشيله ونكمل بالباقي
    - ممنوع في WHERE/ORDER BY.. -> PermissionError
    - صف كامل (row_to_json..)   -> PermissionError
    - مفيش حاجة متبقية          -> PermissionError

    وبعد أي تعديل بنعيد الفحص على الاستعلام الجديد (Fail Closed):
    لو لسه فيه أي حاجة ممنوعة، نرفض.
    """

    if not isinstance(user, dict):
        raise ValueError("Invalid user identity.")

    role = user.get("role")

    if not role:
        raise ValueError("User role is missing.")

    policy = resolve_policy(schema, policy)

    expanded = expand_star_select_items(
        sql_query,
        role,
        schema,
        policy
    )

    parsed = _Parsed(expanded, schema, policy)

    if _has_nested_star(parsed) and _any_disallowed(parsed, role):

        raise PermissionError(
            "Access denied. "
            "Wildcard inside a subquery cannot be verified safely."
        )

    whole_row = _whole_row_tables(parsed, role)

    if whole_row:

        raise PermissionError(
            "Access denied. "
            "Whole-row access is not allowed for: "
            + ", ".join(whole_row)
        )

    restricted = get_restricted_identifiers(
        expanded,
        user,
        schema,
        policy
    )

    if not restricted:
        return expanded, []

    blocking = [
        col for col in restricted
        if not col["select_only"]
    ]

    if blocking:

        raise PermissionError(
            "Access denied. "
            "The requested data requires additional permissions: "
            + ", ".join(
                f'{col["table"]}.{col["column"]}'
                for col in restricted
            )
        )

    new_query, removed = strip_restricted_select_items(
        expanded,
        restricted,
        schema
    )

    # تحقق تاني على الاستعلام بعد التعديل
    if get_restricted_identifiers(new_query, user, schema, policy):

        raise PermissionError(
            "Access denied. "
            "The requested data requires additional permissions."
        )

    if _whole_row_tables(_Parsed(new_query, schema, policy), role):

        raise PermissionError(
            "Access denied. "
            "Whole-row access is not allowed."
        )

    return new_query, removed


# ============================================================
# authorize_sql — رفض كامل (للتوافق مع test_authorization.py)
# ============================================================

def authorize_sql(
    sql_query: str,
    user: dict,
    schema: dict = None,
    policy: dict = None
):
    """
    رفض كامل: أي عمود ممنوع على المستخدم (في أي مكان في الاستعلام،
    بما فيهم SELECT) بيرفع PermissionError. بترجّع True لو الاستعلام
    نضيف. (التنفيذ الفعلي بيستخدم apply_column_authorization اللي
    بتشيل الأعمدة الممنوعة من SELECT وتكمّل.)
    """

    if schema is None:
        raise ValueError("schema is required (pass db.schema).")

    _, removed = apply_column_authorization(
        sql_query,
        user,
        schema,
        policy
    )

    if removed:

        raise PermissionError(
            "Access denied. "
            "The requested data requires additional permissions: "
            + ", ".join(removed)
        )

    return True
