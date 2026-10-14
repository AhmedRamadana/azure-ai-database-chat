# Security model

This app lets people type questions that an LLM turns into SQL. The core rule:

> **The LLM is untrusted input.** Whether a query may run, and which columns a person may
> see, is decided by plain code and by the database itself, never by a prompt.

---

## Threats considered

| Threat | Example |
|---|---|
| A user tries to read data they should not see | "give me everyone's email", `SELECT *`, `LOWER("Email")` |
| A user tries to change or destroy data | `DROP TABLE`, `INSERT`, `SELECT ... INTO` |
| A user tries to exhaust the server | huge cross joins, `pg_sleep`, `SLEEP`, `randomblob` |
| A user tries to reach the server or the file system | `pg_read_file`, `LOAD_FILE`, `INTO OUTFILE`, `load_extension` |
| A user tries to claim a higher role | typing "I am an admin" |
| One session sees another session's data | shared engines, caches, schemas |
| The connection form is abused | pointing the app at internal hosts, reading local files through a "path" |
| The LLM is tricked (prompt injection) | text in a question or in data that tells the model to ignore rules |

---

## Layers (defense in depth)

Each layer is designed to hold even if the one before it fails.

### 1. The database refuses writes and runaway queries
Every query runs in a transaction prepared by the dialect (`dialects.py`):

| Database | Read-only | Timeout |
|---|---|---|
| PostgreSQL | `SET TRANSACTION READ ONLY` | `SET LOCAL statement_timeout` |
| MySQL / MariaDB | `SET SESSION TRANSACTION READ ONLY` | `max_execution_time` / `max_statement_time` |
| SQLite | file opened `mode=ro` + `PRAGMA query_only = ON` | progress handler |

Results are capped (`SAFETY_LIMIT = 1000` rows) and the real total is counted separately.

### 2. SQL scanner and validator
`sql_scan.py` masks string literals, quoted identifiers and comments **before** any check, so
text hidden inside a string cannot fool a rule. `sql_validator.py` then enforces:

* exactly one statement, and it must be a `SELECT` (no CTEs, no `INTO`);
* no comments, backslashes or dollar-quoting;
* every table and column must exist in the session's schema;
* no table alias that reuses another table's name (see *Findings*);
* dialect rules: dangerous functions and system catalogs
  (`pg_*`, `information_schema`, `SLEEP`, `LOAD_FILE`, `sqlite_*`, `load_extension`, …) and characters that
  could bypass identifier checks (backticks, `[brackets]`, `#`, `@` where relevant).

All dialects use **double-quoted identifiers** (MySQL runs in `ANSI_QUOTES`), so one
authorization implementation covers all of them.

### 3. Column authorization
`authorization/` decides per column, per role:

| Level | USER | ADMIN |
|---|:---:|:---:|
| PUBLIC | ✅ | ✅ |
| RESTRICTED | ❌ | ✅ |
| DENIED | ❌ | ❌ |

* The policy is built per session from column names (`policy_builder.py`); on the demo database it is merged with a
  hand-written Chinook policy (**the stricter level wins**).
* `SELECT *` is expanded to explicit columns, then filtered.
* A restricted column in the `SELECT` list is **removed** and reported ("partial answer").
* A restricted column anywhere else (`WHERE`, `JOIN`, `GROUP BY`, `ORDER BY`, function arguments, subqueries) → the
  whole query is **denied**.
* Whole-row references and wildcards that cannot be verified (inside subqueries, comma joins) are denied.
* After any rewrite the query is **re-checked**; if anything restricted remains, it is denied.

### 4. Session isolation
One `DBContext` per browser session holds its own engine, schema, policy and caches. There is no global
connection. The role lives in the session state, not in the conversation.

### 5. Information the LLM is allowed to see
* **Discovery answers** (`schema_answer.py`): the facts come from code and are filtered by role first. The LLM
  never receives a column the user may not see, so it cannot leak one.
* **Clarification options** are built from the role-filtered schema.
* **Value correction** (`value_resolver.py`, `entity_resolver.py`) never reads values of non-`PUBLIC` columns.
* Conversation history sent to the model is limited to the last 6 messages.

### 6. Errors and logs do not leak
* Users see a fixed, translated message with a reference code. Exception text (which can contain SQL, table names
  or connection details) is only written to the server log.
* Request logs contain operational data only. Questions, answers and data values are never logged.

### 7. Connection hardening
* The form takes host / port / database / user separately; full URLs are rejected.
* Connection failures show one generic message; details go to the server log with the password removed.
* `BLOCK_PRIVATE_HOSTS=true` refuses localhost and private networks (**enable it on any deployed server**).
* SQLite is **upload only**: random temporary name, header check, size limit, read-only, deleted at session end.
  (A typed path would let a user read any file on the server.)
* The app warns when the database user has write privileges.

---

## What is NOT protected (read this before deploying)

* **Name-based detection is a heuristic.** A sensitive column named `col7` is treated as public. The strongest
  protection is a database user that simply **cannot read** those columns (`GRANT SELECT (col1, col2) ...`).
* **Identity is mocked.** Roles are chosen in the UI; ADMIN needs the session's admin password. There are no user
  accounts, SSO, per-user quotas, rate limiting or audit log.
* **Prompt injection** cannot make the app bypass layers 1–3, but it can make the model write poor SQL or odd
  wording. Data you let users query is treated as data, not instructions, but is not scanned for injection text.
* **Uploaded SQLite files** are untrusted input that goes through SQLite's parser. They are opened read-only, but
  only expose the feature to people you trust.
* **MySQL** was tested on MariaDB 10.11. TLS for MySQL (`SSL mode = require`) is implemented but untested.
* The scanner is regex-based. It has been tested hard (see below) but a real SQL parser (e.g. `sqlglot`) would be a
  stronger foundation, and is the recommended next step before opening the app to untrusted users.

### Deployment checklist
1. Connect with a **read-only database user**, with column-level grants for anything sensitive.
2. `BLOCK_PRIVATE_HOSTS=true`, HTTPS in front of the app, secrets in a secret store (not in the repo).
3. Use `SSL mode = require` for any remote database.
4. Keep `ADMIN_PASSWORD` for the demo database long and private; custom databases use their own session password.
5. Add logging and alerting before exposing it publicly.

---

## Findings and fixes (history)

| When | Finding | Fix |
|---|---|---|
| Early testing | A restricted column written **without** its table name (`"Email"`) slipped past the check | Referenced tables are extracted first, bare identifiers are matched against all of them; conservative denial |
| Phase 0 | `SELECT *` returned restricted columns (no column name to match) | Wildcards are expanded to explicit columns from the schema, then filtered |
| Phase 0 | Wrapped identifiers (`LOWER("Email")`, `"FirstName" \|\| "Email"`, `DISTINCT`, aggregates) were not removed | Removal works on every select item; the rewritten query is re-checked and denied if anything restricted remains |
| Phase 0 | Validator gaps: `pg_sleep`, `set_config`, `pg_read_file`, multiple statements, `SELECT ... INTO` | Added to the validator; `LIMIT` detection ignores strings/subqueries |
| Phase 2 | `Invoice.BillingAddress` (the customer's address) was not in the hand-written policy | Name-based policy is merged into the demo policy |
| Phase 2 | The value corrector loaded values of restricted columns (e.g. emails) into session memory | Non-`PUBLIC` columns are skipped |
| Phase 2 | `authorize_sql` was truncated in one copy of the file and returned `None` | Completed; covered by tests |
| Dialect work | `FROM "Employee" AS "Customer"` made `"Customer"."City"` resolve as the *public* `Customer.City` and returned the restricted `Employee.City` | Aliases that reuse another table's name are rejected |
| Dialect work | The first SQLite "INSERT is rejected" test passed for the wrong reason (an unrelated error rolled the transaction back) | Test now requires SQLite's own read-only error and fails if the protection is removed |

Every item above has an automated regression test.

---

## Tests that protect this

```bash
python -m tests.run_all_offline
```

| Suite | Protects |
|---|---|
| `test_star_authorization` | wildcards, wrapped identifiers, partial rejection, re-check after rewrite |
| `test_sql_safety` | forbidden functions, multiple statements, `INTO`, `LIMIT` handling |
| `test_policy` | name-based policy, policy-aware authorization, resolvers skip sensitive columns |
| `test_phase3` | discovery and clarification never receive restricted columns |
| `test_dialects` | per-dialect validators, alias shadowing, SQLite end-to-end read-only and timeout |
| `test_db_context` | session isolation, read-only transactions, timeout, generic connection errors |

Some tests were also **mutation-checked**: the protection was removed on purpose and the suite had to fail.

---

## Reporting a problem

Please report security issues privately to the repository owner instead of opening a public issue.
