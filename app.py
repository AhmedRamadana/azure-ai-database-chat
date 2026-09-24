import streamlit as st
import pandas as pd

from pipeline import run_pipeline


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
    st.session_state.selected_model = "nano"


if "messages" not in st.session_state:
    st.session_state.messages = []


# =========================================================
# Sidebar
# =========================================================

with st.sidebar:

    st.title("🎵 Chinook AI Chat")

    st.divider()

    st.subheader("Model Settings")

    # -----------------------------------------------------
    # Model Selector
    # -----------------------------------------------------

    selected_model = st.selectbox(
        "Select Model",
        options=["nano", "mini"],
        index=[
            "nano",
            "mini"
        ].index(
            st.session_state.selected_model
        ),
        format_func=lambda model: model_display_name[model]
    )

    # -----------------------------------------------------
    # Update Selected Model Immediately
    # -----------------------------------------------------

    st.session_state.selected_model = selected_model

    st.divider()

    # -----------------------------------------------------
    # Current Model
    # -----------------------------------------------------

    st.caption("Current model")

    st.markdown(
        f"**{model_display_name[st.session_state.selected_model]}**"
    )


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

        # -------------------------------------------------
        # Message Content
        # -------------------------------------------------

        st.markdown(
            message["content"]
        )


        # -------------------------------------------------
        # Assistant Message
        # -------------------------------------------------

        if message["role"] == "assistant":

            # =============================================
            # Model Used
            # =============================================

            if "model_name" in message:

                st.caption(
                    f"Model used: "
                    f"**{model_display_name[message['model_name']]}**"
                )


            # =============================================
            # Database Result
            # =============================================

            if message.get("type") == "database":

                columns = message.get(
                    "columns",
                    []
                )

                rows = message.get(
                    "rows",
                    []
                )


                # =========================================
                # Convert to DataFrame
                # =========================================

                if rows:

                    dataframe = pd.DataFrame(
                        rows,
                        columns=columns
                    )


                    # =====================================
                    # Result Count
                    # =====================================

                    st.caption(
                        f"{len(dataframe)} result(s) found."
                    )


                    # =====================================
                    # Display Table
                    # =====================================

                    st.dataframe(
                        dataframe,
                        use_container_width=True,
                        hide_index=True
                    )


                    # =====================================
                    # Download CSV
                    # =====================================

                    csv_data = dataframe.to_csv(
                        index=False
                    ).encode("utf-8-sig")


                    st.download_button(
                        label="Download CSV",
                        data=csv_data,
                        file_name="query_result.csv",
                        mime="text/csv",
                        key=message.get(
                            "message_id"
                        )
                    )


                else:

                    st.info(
                        "No matching data was found."
                    )


                # =====================================
                # Generated SQL
                # =====================================

                with st.expander(
                    "View Generated SQL"
                ):

                    st.code(
                        message.get(
                            "sql",
                            ""
                        ),
                        language="sql"
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

    # -----------------------------------------------------
    # Get Current Selected Model
    # -----------------------------------------------------

    model_name = st.session_state.selected_model


    # -----------------------------------------------------
    # Display User Message
    # -----------------------------------------------------

    with st.chat_message("user"):

        st.markdown(prompt)


    # -----------------------------------------------------
    # Save User Message
    # -----------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )


    # -----------------------------------------------------
    # Generate Assistant Response
    # -----------------------------------------------------

    with st.chat_message("assistant"):

        with st.spinner(
            f"{model_display_name[model_name]} is thinking..."
        ):

            try:

                result = run_pipeline(
                    user_question=prompt,
                    model_name=model_name
                )


                # =========================================
                # Display Answer
                # =========================================

                st.markdown(
                    result["answer"]
                )


                # =========================================
                # Display Model Used
                # =========================================

                st.caption(
                    f"Model used: "
                    f"**{model_display_name[model_name]}**"
                )


                # =========================================
                # Database Result
                # =========================================

                if result["type"] == "database":

                    columns = result["columns"]

                    rows = result["rows"]


                    # =====================================
                    # Display DataFrame
                    # =====================================

                    if rows:

                        dataframe = pd.DataFrame(
                            rows,
                            columns=columns
                        )


                        st.caption(
                            f"{len(dataframe)} result(s) found."
                        )


                        st.dataframe(
                            dataframe,
                            use_container_width=True,
                            hide_index=True
                        )


                        # =================================
                        # Download CSV
                        # =================================

                        csv_data = dataframe.to_csv(
                            index=False
                        ).encode("utf-8-sig")


                        st.download_button(
                            label="Download CSV",
                            data=csv_data,
                            file_name="query_result.csv",
                            mime="text/csv",
                            key=(
                                f"download_"
                                f"{len(st.session_state.messages)}"
                            )
                        )


                    else:

                        st.info(
                            "No matching data was found."
                        )


                    # =====================================
                    # Generated SQL
                    # =====================================

                    with st.expander(
                        "View Generated SQL"
                    ):

                        st.code(
                            result["sql"],
                            language="sql"
                        )


                # =========================================
                # Save Assistant Message
                # =========================================

                st.session_state.messages.append(
                    {
                        "role": "assistant",

                        "content": result["answer"],

                        # Model used for this answer
                        "model_name": model_name,

                        # Database information
                        "type": result["type"],

                        "columns": result.get(
                            "columns",
                            []
                        ),

                        "rows": result.get(
                            "rows",
                            []
                        ),

                        "sql": result.get(
                            "sql",
                            ""
                        ),

                        # Unique message ID
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