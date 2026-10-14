import hmac
import time
import os

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from pipeline import run_pipeline
from auth.mock_auth import get_mock_user
from db_context import (
    DBConnectionError,
    connect_custom,
    connect_demo,
    connect_sqlite
)
from dialects import DIALECTS
from errors import handle_error
from language_utils import detect_language
from observability import log_request, setup_logging

load_dotenv()

# باسورد الـ ADMIN للداتابيز التجريبية بس. الداتابيز المخصصة بتاخد
# الباسورد من شاشة الاتصال (لكل Session لوحدها).
DEMO_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")


# =========================================================
# Configuration
# =========================================================

DISPLAY_CAP = 200

# نص محايد بيتخزن في الـ History لما يحصل Error (التفاصيل التقنية
# بتتعرض لوحدها، ومش بتدخل في سياق الأسئلة اللي بعده)
ERROR_HISTORY_TEXT = (
    "⚠️ I couldn't complete this request. "
    "تعذّر إكمال الطلب."
)


# =========================================================
# Page Configuration
# =========================================================

setup_logging()

st.set_page_config(
    page_title="AI Chat with Database",
    page_icon="🗄️",
    layout="wide"
)


# =========================================================
# Model Display Names
# =========================================================

model_display_name = {
    "nano": "GPT-4.1 nano",
    "mini": "GPT-4.1 mini"
}


# =========================================================
# Initialize Session State
#
# كل ده خاص بالـ Session دي بس (st.session_state مش مشترك بين
# المستخدمين)، ومنها الاتصال بالداتابيز نفسه.
# =========================================================

if "db" not in st.session_state:

    st.session_state.db = None


if "admin_secret" not in st.session_state:

    st.session_state.admin_secret = None


if "selected_model" not in st.session_state:

    st.session_state.selected_model = "mini"


if "selected_role" not in st.session_state:

    st.session_state.selected_role = "USER"


if "admin_authenticated" not in st.session_state:

    st.session_state.admin_authenticated = False


if "messages" not in st.session_state:

    st.session_state.messages = []


# =========================================================
# Connection helpers
# =========================================================

def _clear_session_widgets():

    for key in (
        "role_choice",
        "admin_password_input"
    ):

        st.session_state.pop(key, None)


def activate_database(db, admin_secret):
    """
    بتفعّل الاتصال الجديد وبتصفّر كل حاجة مرتبطة بالداتابيز
    القديمة (الشات، الـ Role، الـ Admin).
    """

    old_db = st.session_state.get("db")

    if old_db is not None:

        old_db.dispose()

    st.session_state.db = db
    st.session_state.admin_secret = admin_secret or None
    st.session_state.admin_authenticated = False
    st.session_state.selected_role = "USER"
    st.session_state.messages = []

    _clear_session_widgets()


def disconnect_database():
    """
    on_click callback لزرار Change database.
    """

    old_db = st.session_state.get("db")

    if old_db is not None:

        old_db.dispose()

    st.session_state.db = None
    st.session_state.admin_secret = None
    st.session_state.admin_authenticated = False
    st.session_state.selected_role = "USER"
    st.session_state.messages = []

    _clear_session_widgets()


def render_connection_error(error: DBConnectionError):

    st.error(error.message)

    if error.kind == "connect":

        with st.expander("Troubleshooting tips"):

            st.markdown(
                "- Check the **host** and **port** "
                "(PostgreSQL usually uses `5432`, MySQL `3306`).\n"
                "- Make sure the **database type** matches the "
                "server (PostgreSQL, MySQL / MariaDB or SQLite).\n"
                "- Managed providers (Railway, Neon, Supabase, "
                "Azure) usually require **SSL mode = require**.\n"
                "- Make sure the database allows connections "
                "from this server (firewall / IP allow list).\n"
                "- Double-check the user, password and "
                "database name."
            )


def render_connection_screen():

    st.title("🗄️ AI Chat with Database")

    st.write(
        "Connect to a database to start asking questions "
        "in natural language."
    )

    st.info(
        "🔒 **Recommended:** connect with a **read-only** "
        "database user (and, if possible, grant it access only "
        "to non-sensitive columns). The app only runs read-only "
        "transactions, but database permissions are the "
        "strongest protection."
    )

    # برّه الـ form عشان تغيير النوع يعيد رسم الحقول فورًا
    dialect_key = st.selectbox(
        "Database type",
        options=list(DIALECTS),
        format_func=lambda key: DIALECTS[key].label
    )

    dialect = DIALECTS[dialect_key]

    with st.form(f"connection_form_{dialect.key}"):

        if dialect.file_based:

            uploaded_file = st.file_uploader(
                f"{dialect.label} file",
                type=["db", "sqlite", "sqlite3", "db3"],
                help=(
                    "The file is opened read-only and deleted "
                    "when your session ends."
                )
            )

        else:

            host_column, port_column = st.columns([3, 1])

            host = host_column.text_input(
                "Host",
                placeholder="db.example.com"
            )

            port = port_column.text_input(
                "Port",
                value=str(dialect.default_port)
            )

            database = st.text_input(
                "Database"
            )

            user = st.text_input(
                "User"
            )

            password = st.text_input(
                "Password",
                type="password"
            )

            sslmode = None

            pg_schema = "public"

            if dialect.ssl_modes and dialect.has_schemas:

                ssl_column, schema_column = st.columns(2)

            else:

                ssl_column = schema_column = st

            if dialect.ssl_modes:

                sslmode = ssl_column.selectbox(
                    "SSL mode",
                    options=list(dialect.ssl_modes),
                    index=dialect.ssl_modes.index(
                        dialect.default_ssl_mode
                    )
                )

            if dialect.has_schemas:

                pg_schema = schema_column.text_input(
                    "Schema (optional)",
                    value="public"
                )

        admin_password = st.text_input(
            "Admin password (optional)",
            type="password",
            help=(
                "Choose a password to unlock the ADMIN role "
                "for this session. If left empty, ADMIN access "
                "is disabled."
            )
        )

        submitted = st.form_submit_button(
            "Connect",
            type="primary"
        )

    if submitted:

        try:

            with st.spinner("Connecting..."):

                if dialect.file_based:

                    if uploaded_file is None:

                        raise DBConnectionError(
                            "Please choose a file first.",
                            "form"
                        )

                    new_db = connect_sqlite(
                        uploaded_file.getvalue(),
                        uploaded_file.name
                    )

                else:

                    new_db = connect_custom(
                        host=host,
                        port=port,
                        database=database,
                        user=user,
                        password=password,
                        sslmode=sslmode,
                        pg_schema=pg_schema,
                        dialect=dialect.key
                    )

        except DBConnectionError as error:

            render_connection_error(error)

        else:

            activate_database(
                new_db,
                admin_password
            )

            st.rerun()

    st.divider()

    st.caption(
        "No database to connect? Try the demo (Chinook music store)."
    )

    if st.button("Use demo database (Chinook)"):

        try:

            with st.spinner("Connecting to the demo database..."):

                demo_db = connect_demo()

        except DBConnectionError as error:

            render_connection_error(error)

        else:

            activate_database(
                demo_db,
                DEMO_ADMIN_PASSWORD
            )

            st.rerun()


# =========================================================
# Gate: no database, no chat
# =========================================================

if st.session_state.db is None:

    render_connection_screen()

    st.stop()


db = st.session_state.db


# =========================================================
# Helper: عرض نتيجة سؤال واحد (Database Result)
# =========================================================

def render_database_result(
    columns,
    rows,
    real_total,
    sql,
    restricted_fields,
    download_key
):

    if restricted_fields:

        fields_text = ", ".join(restricted_fields)

        st.warning(
            f"🔒 Some requested fields were not shown due to "
            f"insufficient permissions: **{fields_text}**"
        )


    if not rows:

        st.info(
            "No matching data was found."
        )

    else:

        display_rows = rows[:DISPLAY_CAP]

        display_dataframe = pd.DataFrame(
            display_rows,
            columns=columns
        )


        if real_total > len(rows):

            st.caption(
                f"⚠️ Showing {len(display_rows)} of "
                f"{real_total} total matching results "
                f"(fetched up to {len(rows)} for safety)."
            )

        elif len(rows) > DISPLAY_CAP:

            st.caption(
                f"Showing first {DISPLAY_CAP} of "
                f"{len(rows)} result(s)."
            )

        else:

            st.caption(
                f"{len(rows)} result(s) found."
            )


        st.dataframe(
            display_dataframe,
            use_container_width=True,
            hide_index=True
        )


        full_dataframe = pd.DataFrame(
            rows,
            columns=columns
        )

        csv_data = full_dataframe.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            label=(
                f"Download CSV ({len(rows)} rows)"
            ),
            data=csv_data,
            file_name="query_result.csv",
            mime="text/csv",
            key=download_key
        )


    with st.expander(
        "View Generated SQL"
    ):

        st.code(
            sql or "",
            language="sql"
        )


# =========================================================
# Sidebar
# =========================================================

with st.sidebar:

    st.title(
        f"{'🎵' if db.is_demo else '🗄️'} {db.display_name}"
    )

    schema_line = (
        f"Schema: **{db.pg_schema}**  \n"
        if db.pg_schema
        else ""
    )

    st.caption(
        f"Type: **{db.dialect.label}**  \n"
        f"Database: **{db.db_name}**  \n"
        f"{schema_line}"
        f"Tables: **{len(db.schema)}**"
    )

    st.button(
        "Change database",
        on_click=disconnect_database
    )

    protected = db.policy_summary

    protected_count = (
        len(protected["RESTRICTED"])
        + len(protected["DENIED"])
    )

    if not db.is_demo:

        st.info(
            "🛡️ Sensitive columns are detected automatically "
            "from their **names** (email, phone, address, "
            "passwords, tokens, ...). This is approximate: it can "
            "miss a column with an unusual name. For real data, "
            "also connect with a read-only database user that can "
            "only see non-sensitive columns."
        )

    with st.expander(
        f"Protected columns ({protected_count})"
    ):

        if protected["DENIED"]:

            st.markdown(
                "**Hidden from everyone:**  \n"
                + ", ".join(
                    f"`{name}`" for name in protected["DENIED"]
                )
            )

        if protected["RESTRICTED"]:

            st.markdown(
                "**Hidden from USER (visible to ADMIN):**  \n"
                + ", ".join(
                    f"`{name}`" for name in protected["RESTRICTED"]
                )
            )

        if not protected_count:

            st.caption("No sensitive column names were detected.")

    if not db.is_demo:

        if db.has_write_access:

            st.warning(
                "⚠️ This database user has write permissions. "
                "The app runs read-only transactions, but a "
                "read-only user is strongly recommended."
            )

    st.divider()

    st.subheader("Model Settings")


    selected_model = st.selectbox(
        "Select Model",
        options=["nano", "mini"],
        index=[
            "nano",
            "mini"
        ].index(
            st.session_state.selected_model
        ),
        format_func=lambda model:
            model_display_name[model]
    )


    st.session_state.selected_model = selected_model

    st.divider()


    st.caption("Current model")

    st.markdown(
        f"**{model_display_name[st.session_state.selected_model]}**"
    )

    st.divider()


    st.subheader("User Settings")


    admin_secret = st.session_state.admin_secret


    if not admin_secret:

        # مفيش باسورد Admin متظبط للـ Session دي: ADMIN معطّل والـ
        # Role Selector مخفي.
        st.session_state.admin_authenticated = False

        st.session_state.selected_role = "USER"

        st.caption(
            "🔒 ADMIN access is disabled for this session "
            "(no admin password was set)."
        )


    else:

        role_choice = st.selectbox(
            "Select Role",
            options=["USER", "ADMIN"],
            key="role_choice"
        )


        if role_choice == "USER":

            st.session_state.admin_authenticated = False

            st.session_state.selected_role = "USER"


        else:

            if not st.session_state.admin_authenticated:

                admin_password_input = st.text_input(
                    "Admin Password",
                    type="password",
                    key="admin_password_input"
                )

                if admin_password_input:

                    # مقارنة Constant-time
                    if hmac.compare_digest(
                        admin_password_input.encode("utf-8"),
                        admin_secret.encode("utf-8")
                    ):

                        st.session_state.admin_authenticated = True

                        st.success("Admin access granted.")

                    else:

                        st.error("Incorrect password.")

            if st.session_state.admin_authenticated:

                st.session_state.selected_role = "ADMIN"

            else:

                st.session_state.selected_role = "USER"

                st.caption(
                    "🔒 Enter the correct admin password "
                    "to unlock ADMIN access."
                )


    st.divider()

    st.caption("Current role")

    st.markdown(
        f"**{st.session_state.selected_role}**"
    )

    st.caption(
        "⚠️ Demo purposes only — in production, "
        "role comes from real authentication, not a password field."
    )

    st.divider()


# =========================================================
# Main Header
# =========================================================

st.title(
    f"{'🎵' if db.is_demo else '🗄️'} "
    f"{db.display_name} AI Assistant"
)

st.write(
    f"Ask questions about the {db.display_name} database."
)

st.divider()


# =========================================================
# Display Chat History
# =========================================================

for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(
            message["content"]
        )


        if message["role"] == "assistant":

            if "model_name" in message:

                st.caption(
                    f"Model used: "
                    f"**{model_display_name[message['model_name']]}**"
                )


            if message.get("type") == "error":

                st.error(
                    message.get("error_detail", "")
                )


            if message.get("type") == "database":

                render_database_result(
                    columns=message.get("columns", []),
                    rows=message.get("rows", []),
                    real_total=message.get(
                        "real_total",
                        len(message.get("rows", []))
                    ),
                    sql=message.get("sql", ""),
                    restricted_fields=message.get(
                        "restricted_fields", []
                    ),
                    download_key=message.get("message_id")
                )


            if message.get("type") == "multiple":

                for sub_result in message.get(
                    "results",
                    []
                ):

                    with st.expander(
                        f"🔍 {sub_result['question']}"
                    ):

                        st.caption(
                            f"Status: {sub_result['status']}"
                        )

                        if sub_result.get("sql"):

                            st.code(
                                sub_result["sql"],
                                language="sql"
                            )

                        else:

                            st.info(
                                "No SQL was generated "
                                "for this sub-question."
                            )


# =========================================================
# User Input
# =========================================================

prompt = st.chat_input(
    "Ask something about the database..."
)


# =========================================================
# Handle User Question
# =========================================================

if prompt:

    model_name = (
        st.session_state.selected_model
    )


    current_user = get_mock_user(
        user_id="streamlit_user",
        role=st.session_state.selected_role
    )


    conversation_history = (
        st.session_state.messages.copy()
    )


    with st.chat_message("user"):

        st.markdown(
            prompt
        )


    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )


    with st.chat_message("assistant"):

        with st.spinner(
            f"{model_display_name[model_name]} is thinking..."
        ):

            started_at = time.perf_counter()

            try:

                result = run_pipeline(
                    user_question=prompt,
                    model_name=model_name,
                    conversation_history=conversation_history,
                    user=current_user,
                    db=db
                )

                log_request(
                    result_type=result["type"],
                    model=model_name,
                    role=current_user["role"],
                    dialect=db.dialect.key,
                    latency_seconds=time.perf_counter() - started_at,
                    rows=len(result.get("rows", [])),
                    restricted_fields=result.get(
                        "restricted_fields", []
                    )
                )


                st.markdown(
                    result["answer"]
                )


                st.caption(
                    f"Model used: "
                    f"**{model_display_name[model_name]}**"
                )


                if result["type"] == "database":

                    render_database_result(
                        columns=result.get("columns", []),
                        rows=result.get("rows", []),
                        real_total=result.get(
                            "real_total",
                            len(result.get("rows", []))
                        ),
                        sql=result.get("sql", ""),
                        restricted_fields=result.get(
                            "restricted_fields", []
                        ),
                        download_key=(
                            f"download_"
                            f"{len(st.session_state.messages)}"
                        )
                    )


                if result["type"] == "multiple":

                    for sub_result in result.get(
                        "results",
                        []
                    ):

                        with st.expander(
                            f"🔍 {sub_result['question']}"
                        ):

                            st.caption(
                                f"Status: {sub_result['status']}"
                            )

                            if sub_result.get("sql"):

                                st.code(
                                    sub_result["sql"],
                                    language="sql"
                                )

                            else:

                                st.info(
                                    "No SQL was generated "
                                    "for this sub-question."
                                )


                st.session_state.messages.append(
                    {
                        "role": "assistant",

                        "content": result["answer"],

                        "model_name": model_name,

                        "type": result["type"],

                        "columns": result.get(
                            "columns", []
                        ),

                        "rows": result.get(
                            "rows", []
                        ),

                        "sql": result.get(
                            "sql", ""
                        ),

                        "real_total": result.get(
                            "real_total",
                            len(result.get("rows", []))
                        ),

                        "restricted_fields": result.get(
                            "restricted_fields", []
                        ),

                        "results": result.get(
                            "results", []
                        ),

                        "resolved_question": result.get(
                            "resolved_question",
                            prompt
                        ),

                        "message_id": len(
                            st.session_state.messages
                        )
                    }
                )


            except Exception as e:

                # المستخدم بيشوف رسالة آمنة + Ref، والتفاصيل في اللوج بس
                error_info = handle_error(
                    e,
                    language=detect_language(prompt),
                    context={
                        "model": model_name,
                        "role": current_user["role"],
                        "db": db.dialect.key
                    }
                )

                error_detail = error_info["message"]

                st.error(
                    error_detail
                )

                # بنسجّل رد assistant في الـ History حتى لو حصل Error،
                # عشان ما يبقاش فيه رسالتين user ورا بعض (وده كان
                # بيلخبط فهم السؤال اللي بعده)
                st.session_state.messages.append(
                    {
                        "role": "assistant",

                        "content": ERROR_HISTORY_TEXT,

                        "model_name": model_name,

                        "type": "error",

                        "error_detail": error_detail,

                        "message_id": len(
                            st.session_state.messages
                        )
                    }
                )