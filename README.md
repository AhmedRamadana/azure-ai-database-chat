# AI Chat with Database

Ask questions about **your own database** in plain language (English, Arabic, or mixed)
and get answers in the same language. The app turns each question into a SQL query with
Azure OpenAI, **validates and restricts it in code** (the LLM is never trusted), runs it
read-only, and explains the result.

```text
"كام customer موجود في البرازيل؟"   →   SELECT COUNT(*) ...   →   "في 5 عملاء من البرازيل."
```

> Looking for the original design notes? They are archived in
> [`docs/ARCHIVE_README_v1.md`](docs/ARCHIVE_README_v1.md) (outdated in places).
> Security details: [`SECURITY.md`](SECURITY.md).

---

## Features

| Area | What it does |
|---|---|
| **Bring your own database** | Each browser session connects to its own **PostgreSQL**, **MySQL / MariaDB** or **SQLite** database. No global connection, nothing shared between sessions. |
| **Column-level access control** | Sensitive columns (email, phone, address, passwords, tokens, cards, …) are detected automatically from their names. Role `USER` never sees them; `ADMIN` sees `RESTRICTED` ones; `DENIED` ones are hidden from everyone. |
| **Partial answers** | If a question asks for an allowed column and a restricted one, the restricted column is removed and the user is told. `SELECT *` is expanded and filtered the same way. |
| **Discovery** | "What tables do you have?", "ايه الأعمدة اللي في Customer؟" are answered from the real schema (filtered by role), not guessed by the LLM. |
| **Clarification (once)** | A genuinely vague request ("Show me the data") gets **one** question with numbered options. Replies like `2` or `الاتنين` are merged with the original request. After that the app answers with the most reasonable interpretation and says what it assumed. |
| **Conversation context** | Follow-ups ("and in 2022?") are rewritten into standalone questions (last 6 messages). |
| **Multiple questions** | One message with several questions is split, answered separately, and combined. |
| **Value correction** | `Brazill` → `Brazil`, `AC DC` → `AC/DC`, matched against real values of *public* columns only. |
| **Self-correction** | If the generated SQL fails, the error is fed back to the model for a bounded number of retries. |
| **Data availability check** | Asking for data that does not exist ("customer salaries") gets a clear "not available" answer instead of a wrong query. |

---

## Quick start

```bash
git clone <your-repo>
cd "chat with db"
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in the Azure OpenAI values
streamlit run app.py
```

Open the app, choose a **Database type**, enter the connection details, and click **Connect**.
No database to try? Click **Use demo database (Chinook)** (needs `DATABASE_URL`, see below).

### Optional: load the Chinook demo data into PostgreSQL

```bash
# DATABASE_URL in .env must point to an empty PostgreSQL database
python load_data.py
```

---

## Connection form

Pick the type first; the fields change with it.

| Field | Meaning |
|---|---|
| **Host / Port** | Server address and port (PostgreSQL `5432`, MySQL `3306`). Managed providers (Railway, Neon, Supabase, Azure) show them on their **Connect** page. |
| **Database** | Database name on that server. |
| **User / Password** | Database credentials. **Use a read-only user** whenever the data is real. |
| **SSL mode** | Encrypts the connection. `disable` = no encryption (local only). `prefer` = try encryption, fall back to plain. `require` = encryption mandatory — **use this for any online database**. `verify-ca` / `verify-full` also verify the server certificate (PostgreSQL). MySQL offers `disable` / `require`. |
| **Schema** *(PostgreSQL)* | Schema to read, normally `public`. |
| **SQLite file** | Upload a `.db` / `.sqlite` file. It is stored under a random temporary name, opened **read-only**, and deleted when the session ends. |
| **Admin password** *(optional)* | A password **you choose** to unlock the `ADMIN` role for this session. Empty = ADMIN disabled. |

---

## How a question is processed

```text
user message
   │
   ▼
Context resolver ──► Classifier ──┬─ GREETING / UNRELATED → short reply
 (merge follow-ups,               ├─ DISCOVERY → schema_answer (facts from code, LLM only phrases them)
  clarification replies)          └─ DATABASE
                                         │
                                         ▼
                                  Input analysis ── AMBIGUOUS ─► ask ONE question (or assume if already asked)
                                         │ CLEAR
                                         ▼
                              Multiple-question analysis (split if needed)
                                         │   (for each question)
                                         ▼
                              Data availability check ── missing ─► "not available"
                                         │
                                         ▼
        SQL generation ► validate (scanner + schema check + dialect rules) ► value correction
                                         │ (retry with the error on failure)
                                         ▼
                 Column authorization (policy) ► execute READ ONLY with timeout ► answer
```

Every step that decides *permissions* or *safety* is plain Python. The LLM only
classifies, writes SQL, and phrases answers.

**Speed:** after the classifier, three independent analyses (input clarity, question splitting, data
availability) run **in parallel**, so a typical question needs about 5 sequential model stages instead of 7.
The prompts and inputs are unchanged, so results are the same as running them one by one.
(`PARALLEL_ANALYSIS=false` turns this off. For a vague question, or one that gets split into several
questions, one or two of those calls are not needed and are discarded: slightly more cost, no wrong answers.)

### Result types returned by `run_pipeline`

`greeting`, `unrelated`, `discovery`, `clarification`, `unavailable`, `unauthorized`,
`database`, `multiple`.

---

## Supported databases

| Database | Driver | Read-only enforcement | Timeout | Tested on |
|---|---|---|---|---|
| PostgreSQL | `psycopg2` | `SET TRANSACTION READ ONLY` | `statement_timeout` | PostgreSQL 16 |
| MySQL / MariaDB | `pymysql` | `SET SESSION TRANSACTION READ ONLY` | `max_execution_time` / `max_statement_time` | MariaDB 10.11 |
| SQLite | built-in | file opened `mode=ro` + `PRAGMA query_only` | progress handler | SQLite (Python) |

All differences live in [`dialects.py`](dialects.py). Identifiers are **always double-quoted**
(`"Table"."Column"`) in every dialect — MySQL runs in `ANSI_QUOTES` mode — so the validator,
the authorization layer and the policy are shared by all databases. Backticks, `[brackets]`,
`#` comments and `@` variables are rejected where they could bypass that.

Not supported yet: SQL Server, Oracle (no read-only transaction / `LIMIT` differences),
MongoDB and Redis (not SQL).

---

## Access control in one minute

| Level | `USER` | `ADMIN` | Examples |
|---|:---:|:---:|---|
| `PUBLIC` | ✅ | ✅ | names, titles, countries, totals |
| `RESTRICTED` | ❌ | ✅ | email, phone, address, birth date, salary |
| `DENIED` | ❌ | ❌ | password, token, api key, card number, SSN |

* The policy is built per session from column names ([`authorization/policy_builder.py`](authorization/policy_builder.py)).
  The demo database also uses a hand-written Chinook policy; the **stricter** rule wins.
* Name-based detection is a **heuristic** — it can miss an oddly named column. Always combine it
  with a database user that cannot read those columns.
* The role comes from the session (not from the chat text): typing "I am an admin" changes nothing.

See [`SECURITY.md`](SECURITY.md) for the full model.

---

## Configuration

| Variable | Required | Purpose |
|---|:---:|---|
| `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT` | ✅ | Azure OpenAI access |
| `AZURE_OPENAI_DEPLOYMENT` | ✅ | Deployment name for the **nano** model |
| `AZURE_OPENAI_MINI_DEPLOYMENT` | ✅ | Deployment name for the **mini** model |
| `DATABASE_URL` | demo only | PostgreSQL URL for the Chinook demo and `load_data.py` |
| `ADMIN_PASSWORD` | demo only | Unlocks ADMIN on the demo database |
| `BLOCK_PRIVATE_HOSTS` | no | `true` = refuse connections to localhost / private networks (**set on any deployed server**) |
| `MAX_SQLITE_UPLOAD_MB` | no | SQLite upload limit (default 100) |
| `LLM_TIMEOUT_SECONDS` | no | Timeout for each Azure OpenAI call (default 45) |
| `LLM_MAX_RETRIES` | no | Automatic retries for 429 / 5xx / network errors (default 2) |
| `PARALLEL_ANALYSIS` | no | `false` runs the analysis stages one after another (debugging, tight rate limits). Default `true` |
| `LOG_LEVEL` | no | `DEBUG` / `INFO` / `WARNING` / `ERROR` (default `INFO`) |

Never commit `.env`. `.env.example` lists everything.

---

## Project structure

```text
app.py                      Streamlit UI (connection screen, chat, sidebar)
pipeline.py                 Orchestrates the whole flow
db_context.py               One DBContext per session (engine, schema, policy, caches)
dialects.py                 Per-database differences (connect, read-only, timeout, rules)
database.py                 Executes a query inside a prepared read-only transaction
schema.py                   Schema reflection + prompt formatting + table summary
schema_answer.py            Discovery answers (facts from code, filtered by role)

classifier.py               GREETING / DATABASE / DISCOVERY / UNRELATED
context_resolver.py         Follow-ups and clarification replies → standalone question
input_analyzer.py           CLEAR vs AMBIGUOUS
clarification_generator.py  One question with numbered options (role-filtered)
multiple_question_analyzer.py / multiple_answer_generator.py
data_discovery.py           Is the requested data available?
text_to_sql.py              SQL generation + correction
value_resolver.py / entity_resolver.py   Typo correction against real (public) values
answer_generator.py         Natural-language answers

sql_scan.py                 Masks strings/identifiers/comments before any check
sql_validator.py            SELECT-only, single statement, schema-aware validation
sql_executor.py             validate → authorize → LIMIT → execute
authorization/              access_policy.py, policy_builder.py, authorization.py
auth/                       Roles (mock identity for now)
prompts/                    All prompts (demo-specific and generic/dialect-aware)
models/                     Azure OpenAI wrappers (nano / mini)
tests/                      Offline suites, live scripts, evaluation
docs/                       Archived v1 README, model comparison
```

---

## Errors and logging

* The user never sees an exception message. Failures map to a short fixed message (in the user's language)
  plus a reference code, e.g. `(Ref: 67083573)`. The full error and traceback are in the server log under the same
  reference ([`errors.py`](errors.py)).
* Every request writes one operational line (type, model, role, database type, latency, row count, hidden columns).
  **Questions, answers and data values are never logged** ([`observability.py`](observability.py)).
* Azure OpenAI calls have an explicit timeout and automatic retries.

---

## Testing

```bash
# Everything that is checked automatically (no LLM, no Azure keys):
python -m tests.run_all_offline
```

| Suite | Checks |
|---|---|
| `test_policy` | name-based policy, policy-aware authorization, resolvers, prompts |
| `test_phase3` | discovery, one clarification round, assume-and-answer, context merge |
| `test_dialects` | per-dialect validators, URLs, SQLite end-to-end (real file) |
| `test_errors` | safe user messages, no leaks, logging, LLM timeout settings |
| `test_parallel` | analysis stages really overlap, same outcomes as sequential, errors only raised when needed |
| `test_multiple_analyzer` | inconsistent question-splitting output falls back to a single question |
| `test_star_authorization`, `test_sql_safety` | `SELECT *`, partial rejection, injection patterns |
| `test_db_context` | session isolation, read-only, timeout, connection errors (needs `DATABASE_URL`) |

`test_dialects` also runs against a real MySQL/MariaDB when `MYSQL_TEST_*` variables are set
(see the file header).

The other `tests/test_*.py` files are **live scripts** that call the real model and the demo
database and print results for manual review (`python -m tests.test_pipeline`, …).

### Model evaluation

```bash
python -m tests.evaluation.evaluate_models
```

17 cases (counts, JOINs, Top-N, Arabic, greeting, unrelated, discovery, clarification).
Ground truth is computed live from verified SQL. Latest run (17 cases, see
[`docs/model_comparison.md`](docs/model_comparison.md)): **mini 17/17 (100%)**, nano 14/17 (82.4%).
mini is the recommended default. **Re-run the evaluation after changing prompts.**

---

## Known limitations

* **Identity is mocked.** The role is chosen in the UI (ADMIN needs a password). There are no real
  user accounts yet.
* **Name-based column protection is approximate.** Pair it with database-level grants.
* **No audit log, rate limiting or per-user quotas yet.**
* A question still makes several LLM calls (about 5 sequential stages, 6–7 calls in total).
* MySQL support was tested on MariaDB; MySQL TLS (`SSL mode = require`) is implemented but not tested.
* Uploaded SQLite files are untrusted input. They are opened read-only, but only upload files you trust
  on a shared server.

## Roadmap

1. Azure production setup: Entra ID (keyless), Key Vault, real authentication, logging/App Insights,
   fewer LLM calls, container deployment.
2. More databases: SQL Server, Oracle.
3. MongoDB as a separate pipeline.
