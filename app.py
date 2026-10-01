import os

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from pipeline import run_pipeline
from auth.mock_auth import get_mock_user

load_dotenv()

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")


# =========================================================
# Configuration
# =========================================================

DISPLAY_CAP = 200


# =========================================================
# Page Configuration
# =========================================================

st.set_page_config(
    page_title="Chinook AI Chat",
    page_icon="🎵",
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
# =========================================================

if "selected_model" not in st.session_state:

    st.session_state.selected_model = "mini"


if "selected_role" not in st.session_state:

    st.session_state.selected_role = "USER"


if "admin_authenticated" not in st.session_state:

    st.session_state.admin_authenticated = False


if "messages" not in st.session_state:

    st.session_state.messages = []


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

    # -----------------------------------------------------
    # لو فيه أعمدة اتشالت بسبب نقص الصلاحية، نوضحها بصريًا
    # -----------------------------------------------------

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

    st.title("🎵 Chinook AI Chat")

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


    role_choice = st.selectbox(
        "Select Role",
        options=["USER", "ADMIN"]
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

                if not ADMIN_PASSWORD:

                    st.error(
                        "ADMIN_PASSWORD is not configured "
                        "on the server (.env)."
                    )

                elif admin_password_input == ADMIN_PASSWORD:

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

st.title("🎵 Chinook AI Assistant")

st.write(
    "Ask questions about the Chinook database."
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

            try:

                result = run_pipeline(
                    user_question=prompt,
                    model_name=model_name,
                    conversation_history=conversation_history,
                    user=current_user
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

                error_message = (
                    f"An error occurred: {e}"
                )

                st.error(
                    error_message
                )