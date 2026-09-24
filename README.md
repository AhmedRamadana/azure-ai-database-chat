# Chinook AI Database Chat

An AI-powered chat application that allows users to interact with a PostgreSQL database using natural language.

The system converts user questions into SQL queries, validates the generated SQL against the actual database schema, executes safe queries, and converts the results back into natural-language answers.

The application supports English, Arabic, and mixed Arabic-English questions.

---

## Project Overview

This project implements a **Text-to-SQL / Natural Language Database Querying** system using Azure OpenAI and PostgreSQL.

Instead of writing SQL manually, users can ask questions such as:

* How many artists are there?
* Which albums belong to AC/DC?
* Which customers purchased tracks by Metallica?
* كام artist موجود؟
* مين أكتر 5 artists عندهم tracks؟

The system understands the question, determines whether it is related to the database, generates SQL, validates it, executes it, and produces a natural-language response.

---

## Architecture

```text
User
  ↓
Streamlit UI
  ↓
Pipeline
  ↓
Question Classification
  ├── GREETING
  │      ↓
  │   Response
  │
  ├── UNRELATED
  │      ↓
  │   Response
  │
  └── DATABASE
         ↓
     Text-to-SQL
         ↓
     SQL Cleaning
         ↓
     SQL Validation
         ↓
     SQL Executor
         ↓
     PostgreSQL
         ↓
     SQL Result
         ↓
     Answer Generator
         ↓
     Model Layer
         ↓
     Natural Language Answer
```

---

## Main Features

* Natural-language interaction with a PostgreSQL database
* Text-to-SQL generation using Azure OpenAI
* Support for English, Arabic, and mixed-language questions
* Question classification
* Schema-aware SQL validation
* SQL safety checks
* Automatic SQL correction and retry
* Multiple Azure OpenAI models
* Model selection from the UI
* PostgreSQL database integration
* Streamlit chat interface
* SQL result visualization
* CSV result download
* Model evaluation framework
* Database schema caching

---

## Technologies

### AI / LLM

* Azure OpenAI
* GPT-4.1 nano
* GPT-4.1 mini

### Backend

* Python
* SQLAlchemy
* PostgreSQL
* psycopg2

### Frontend

* Streamlit

### Data Processing

* Pandas

### Configuration

* python-dotenv

---

## Database

The project uses the **Chinook database** loaded into PostgreSQL.

The database contains 11 tables:

```text
Album
Artist
Customer
Employee
Genre
Invoice
InvoiceLine
MediaType
Playlist
PlaylistTrack
Track
```

CSV files are loaded into PostgreSQL using the ETL script:

```text
load_data.py
```

The application then uses SQLAlchemy to connect to PostgreSQL and execute generated SQL queries.

---

# Project Structure

```text
project_1_chat with database/
│
├── app.py
├── pipeline.py
├── classifier.py
├── text_to_sql.py
├── sql_validator.py
├── sql_executor.py
├── answer_generator.py
├── schema.py
├── database.py
├── load_data.py
│
├── models/
│   ├── azure_gpt41_nano.py
│   ├── azure_gpt41_mini.py
│   └── model_manager.py
│
├── prompts/
│   ├── classification_prompt.py
│   ├── sql_prompt.py
│   ├── sql_correction_prompt.py
│   └── answer_prompt.py
│
├── data/
│   ├── Album.csv
│   ├── Artist.csv
│   ├── Customer.csv
│   ├── Employee.csv
│   ├── Genre.csv
│   ├── Invoice.csv
│   ├── InvoiceLine.csv
│   ├── MediaType.csv
│   ├── Playlist.csv
│   ├── PlaylistTrack.csv
│   └── Track.csv
│
├── tests/
│   ├── test_validator.py
│   ├── test_retry.py
│   ├── test_sql_speed.py
│   │
│   └── evaluation/
│       ├── test_cases.py
│       └── evaluate_models.py
│
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

---

# How the System Works

## 1. Question Classification

The first step determines the type of user question.

The classifier returns exactly one of:

```text
GREETING
DATABASE
UNRELATED
```

Examples:

```text
Hello
→ GREETING

How many artists are there?
→ DATABASE

What is the weather today?
→ UNRELATED
```

The classifier also handles Arabic and mixed Arabic-English questions.

---

# 2. Database Schema

For database questions, the system retrieves the database schema.

The schema contains:

* Table names
* Column names
* Column types
* Foreign-key relationships

The schema is provided to the LLM as context for Text-to-SQL generation.

The schema is cached using:

```python
@lru_cache(maxsize=1)
```

This prevents repeated database schema inspection during the same application process.

---

# 3. Text-to-SQL

The system sends the user question together with the database schema to the selected Azure OpenAI model.

For example:

```text
User:
How many artists are there?
```

The model generates:

```sql
SELECT COUNT("ArtistId") AS "ArtistCount"
FROM "Artist";
```

The generated query is then cleaned and validated before execution.

---

# 4. SQL Validation

The generated SQL is not executed immediately.

The validation layer checks that:

* The query is not empty.
* The query starts with `SELECT`.
* Dangerous SQL commands are rejected.
* Tables exist in the actual database schema.
* Columns exist in the actual database schema.
* Identifiers use the correct PostgreSQL names.
* Unknown tables and columns are rejected.

Blocked operations include:

```text
INSERT
UPDATE
DELETE
DROP
ALTER
TRUNCATE
CREATE
GRANT
REVOKE
```

This provides an additional safety layer between the LLM and the database.

---

# 5. SQL Correction & Retry

If the generated SQL fails validation or database execution, the system can send the failed query and the error message back to the model.

The correction prompt contains:

```text
User Question
Database Schema
Previous SQL
Validation / Database Error
```

The model then generates a corrected SQL query.

The pipeline allows a limited number of retries:

```python
MAX_SQL_RETRIES = 2
```

This prevents uncontrolled retry loops.

---

# 6. SQL Execution

After successful validation, the query is passed to the Database Layer.

```text
sql_executor.py
        ↓
database.py
        ↓
PostgreSQL
```

The database layer returns:

```text
Columns
Rows
```

---

# 7. Answer Generation

The SQL result is passed to the Answer Generator.

The model receives:

* User question
* Generated SQL
* Result columns
* Result rows

It then generates a natural-language answer.

For example:

```text
User:
How many artists are there?

SQL Result:
275

Answer:
There are 275 artists in the database.
```

The answer language follows the user's input:

```text
English → English
Arabic → Arabic
Mixed → Natural Arabic with technical English terms
```

---

# Model Layer

The project uses a dedicated Model Layer so multiple models can be used without changing the rest of the pipeline.

```text
model_manager.py
        ↓
 ┌───────────────┐
 │               │
nano            mini
 │               │
GPT-4.1 nano    GPT-4.1 mini
```

The selected model is passed through the pipeline.

This makes the architecture easier to extend with additional models in the future.

---

# Streamlit Interface

The application provides a chat interface where users can:

* Ask database questions
* Select the Azure OpenAI model
* View generated SQL
* View query results
* Download results as CSV
* Continue a conversation while preserving previous responses

Each response retains the model used to generate it.

---

# Evaluation

A dedicated evaluation framework was implemented to compare the models.

The evaluation contains **13 test cases** covering:

* Database counting queries
* Multi-table queries
* JOIN operations
* Aggregations
* Top-N queries
* English questions
* Arabic questions
* Mixed Arabic-English questions
* Greetings
* Unrelated questions

The tests compare the generated results against predefined ground-truth SQL results.

---

## Final Evaluation Results

| Model        | Passed | Failed | Accuracy | Average Latency |
| ------------ | -----: | -----: | -------: | --------------: |
| GPT-4.1 nano |     13 |      0 |     100% |           7.64s |
| GPT-4.1 mini |     13 |      0 |     100% |           5.80s |

Both evaluated models successfully passed all 13 test cases.

---

# Performance

The database schema is inspected only once per running Python process and then cached.

Initial schema loading:

```text
~25 seconds
```

Subsequent schema access:

```text
~0.000004 seconds
```

After schema caching, typical Streamlit requests were observed around:

```text
5–10 seconds
```

The first request can be slower because of the initial schema inspection.

---

# Running the Project

## 1. Clone the project

```bash
git clone <repository-url>
cd "project_1_chat with database"
```

## 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it on Windows:

```powershell
venv\Scripts\activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure environment variables

Create a `.env` file:

```text
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_DEPLOYMENT=your_gpt41_nano_deployment
AZURE_OPENAI_MINI_DEPLOYMENT=your_gpt41_mini_deployment
DATABASE_URL=your_postgresql_connection_string
```

Never commit `.env` to Git.

---

# Load the Database

If the PostgreSQL database needs to be populated from the Chinook CSV files:

```bash
python load_data.py
```

The script uploads the CSV files and verifies the `Artist` table.

---

# Run the Application

Start Streamlit:

```bash
streamlit run app.py
```

Then open the local Streamlit URL shown in the terminal.

---

# Run Evaluation

The evaluation must be executed from the project root:

```bash
python -m tests.evaluation.evaluate_models
```

---

# Testing

Individual tests are available under:

```text
tests/
```

Examples:

```text
test_validator.py
test_retry.py
test_sql_speed.py
```

These tests verify SQL validation, SQL correction/retry behavior, and performance.

---

# Key Engineering Decisions

### Why Text-to-SQL?

The main problem is querying structured relational data using natural language.

The system therefore focuses on:

```text
Natural Language
        ↓
SQL
        ↓
Database
        ↓
Natural Language
```

rather than retrieving documents using a RAG architecture.

### Why a Model Layer?

Separating model integrations allows different Azure OpenAI models to be evaluated and compared without modifying the core pipeline.

### Why Schema-Aware Validation?

LLMs can generate syntactically valid SQL containing incorrect table or column names.

Schema-aware validation catches these errors before execution.

### Why Retry?

Some generated SQL errors can be automatically corrected by giving the model the original query and the validation/database error.

### Why Schema Caching?

Database metadata inspection can be relatively expensive. Caching avoids repeatedly querying PostgreSQL for the same schema during the application's lifetime.

---

# Future Improvements

Possible future extensions include:

* Additional Azure OpenAI models
* More comprehensive evaluation datasets
* Query result caching
* Conversation memory
* Authentication
* Database permission isolation
* More advanced SQL validation
* Query timeout handling
* Production deployment
* Monitoring and logging

---

# Project Classification

This project is primarily a:

**Text-to-SQL / Natural Language Database Querying System**

It is not primarily a RAG system because the core workflow does not retrieve document chunks and generate answers from retrieved documents.

The system directly translates natural-language questions into SQL queries and executes them against structured relational data.
