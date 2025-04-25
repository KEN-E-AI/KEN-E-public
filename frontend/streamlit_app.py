# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# mypy: disable-error-code="arg-type"
import json
import uuid
import os
from collections.abc import Sequence
from functools import partial
from typing import Any

import streamlit as st
from langchain_core.messages import HumanMessage
from streamlit_feedback import streamlit_feedback

from frontend.side_bar import SideBar
from frontend.style.app_markdown import MARKDOWN_STR
from frontend.utils.local_chat_history import LocalChatMessageHistory
from frontend.utils.message_editing import MessageEditing
from frontend.utils.multimodal_utils import format_content, get_parts_from_files
from frontend.utils.stream_handler import Client, StreamHandler, get_chain_response

from firebase_admin import credentials, auth, initialize_app
import mysql.connector

from dotenv import load_dotenv
load_dotenv()

@st.cache_resource
def init_firebase():
    import firebase_admin

    firebase_json = os.getenv("FIREBASE_KEY_JSON")
    if not firebase_json:
        st.error("🛑 FIREBASE_KEY_JSON environment variable is missing.")
        st.stop()

    if not firebase_admin._apps:
        try:
            cred_dict = json.loads(firebase_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"🛑 Firebase initialization failed: {e}")
            st.stop()

USER = "my_user"
EMPTY_CHAT_NAME = "Empty chat"


def build_header():
    header_container = st.container()
    with header_container:
        col_left, col_right = st.columns([0.82, 0.18])

        with col_left:
            st.title("KEN-E")
        with col_right:
            c1, c2, c3, c4 = st.columns(4)
            c1.button(
                "",
                icon=":material/share:",
                key="share"
            )
            c2.button(
                "",
                icon=":material/notifications:",
                key="notifications"
            )
            c3.button(
                "",
                icon=":material/account_circle:",
                key="account"
            )
            c4.button(
                "",
                icon=":material/logout:",
                key="logout"
            )

init_firebase()

# --- Identity Platform auth guard ---
if "user" not in st.session_state:
    st.title("Login Required")
    id_token = st.text_input("Enter your Firebase ID token:")
    if st.button("Login") and id_token:
        try:
            decoded = auth.verify_id_token(id_token)
            st.session_state["user"] = {
                "uid": decoded["uid"],
                "email": decoded["email"]
            }
            st.success("Logged in successfully")
            st.rerun()
        except Exception as e:
            st.error(f"Invalid token: {e}")
    st.stop()

def get_user_accounts(user_email):
    conn = mysql.connector.connect(
        host=os.environ["SQL_HOST"],
        user=os.environ["SQL_USER"],
        password=os.environ["SQL_PASSWORD"],
        database=os.environ["SQL_DATABASE"]
    )
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT
        a.account_id, 
        a.account_name,
        o.organization_name
    FROM user_account_access ua
    JOIN account_details a ON ua.account_id = a.account_id
    JOIN organization_details o ON a.organization_id = o.organization_id
    WHERE ua.user_email = %s
    """
    cursor.execute(query, (user_email,))
    return cursor.fetchall()

if "account_options" not in st.session_state:
    accounts = get_user_accounts(st.session_state["user"]["email"])
    if not accounts:
        st.error("No accounts assigned to your user.")
        st.stop()

    st.session_state["accounts"] = accounts
    st.session_state["account_options"] = [
        f'{a["account_name"]} ({a["organization_name"]})'
        for a in accounts
    ]
    st.session_state["selected_account"] = accounts[0]  # default

def setup_page() -> None:
    """Configure the Streamlit page settings."""
    st.set_page_config(
        page_title="KEN-E",
        layout="wide",
        initial_sidebar_state="auto",
        menu_items=None,
    )
    st.markdown(MARKDOWN_STR, unsafe_allow_html=True)


def initialize_session_state() -> None:
    """Initialize the session state with default values."""
    if "user_chats" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())
        st.session_state.uploader_key = 0
        st.session_state.run_id = None
        st.session_state.user_id = USER
        st.session_state["gcs_uris_to_be_sent"] = ""
        st.session_state.modified_prompt = None
        st.session_state.session_db = LocalChatMessageHistory(
            session_id=st.session_state["session_id"],
            user_id=st.session_state["user_id"],
        )
        st.session_state.user_chats = (
            st.session_state.session_db.get_all_conversations()
        )
        st.session_state.user_chats[st.session_state["session_id"]] = {
            "title": EMPTY_CHAT_NAME,
            "messages": [],
        }
    
    if "page" not in st.session_state:
        st.session_state["page"] = "home"


def display_messages() -> None:
    """Display all messages in the current chat session."""
    messages = st.session_state.user_chats[st.session_state["session_id"]]["messages"]
    tool_calls_map = {}  # Map tool_call_id to tool call input

    for i, message in enumerate(messages):
        if message["type"] in ["ai", "human"] and message["content"]:
            display_chat_message(message, i)
        elif message.get("tool_calls"):
            # Store each tool call input mapped by its ID
            for tool_call in message["tool_calls"]:
                tool_calls_map[tool_call["id"]] = tool_call
        elif message["type"] == "tool":
            # Look up the corresponding tool call input by ID
            tool_call_id = message["tool_call_id"]
            if tool_call_id in tool_calls_map:
                display_tool_output(tool_calls_map[tool_call_id], message)
            else:
                st.error(f"Could not find tool call input for ID: {tool_call_id}")
        else:
            st.error(f"Unexpected message type: {message['type']}")
            st.write("Full messages list:", messages)
            raise ValueError(f"Unexpected message type: {message['type']}")


def display_chat_message(message: dict[str, Any], index: int) -> None:
    """Display a single chat message with edit, refresh, and delete options."""
    chat_message = st.chat_message(message["type"])
    with chat_message:
        st.markdown(format_content(message["content"]), unsafe_allow_html=True)
        col1, col2, col3 = st.columns([2, 2, 94])
        display_message_buttons(message, index, col1, col2, col3)


def display_message_buttons(
    message: dict[str, Any], index: int, col1: Any, col2: Any, col3: Any
) -> None:
    """Display edit, refresh, and delete buttons for a chat message."""
    edit_button = f"{index}_edit"
    refresh_button = f"{index}_refresh"
    delete_button = f"{index}_delete"
    content = (
        message["content"]
        if isinstance(message["content"], str)
        else message["content"][-1]["text"]
    )

    with col1:
        st.button(label="✎", key=edit_button, type="primary")
    if message["type"] == "human":
        with col2:
            st.button(
                label="⟳",
                key=refresh_button,
                type="primary",
                on_click=partial(MessageEditing.refresh_message, st, index, content),
            )
        with col3:
            st.button(
                label="X",
                key=delete_button,
                type="primary",
                on_click=partial(MessageEditing.delete_message, st, index),
            )

    if st.session_state[edit_button]:
        st.text_area(
            "Edit your message:",
            value=content,
            key=f"edit_box_{index}",
            on_change=partial(MessageEditing.edit_message, st, index, message["type"]),
        )


def display_tool_output(
    tool_call_input: dict[str, Any], tool_call_output: dict[str, Any]
) -> None:
    """Display the input and output of a tool call in an expander."""
    tool_expander = st.expander(label="Tool Calls:", expanded=False)
    with tool_expander:
        msg = (
            f"\n\nEnding tool: `{tool_call_input}` with\n **args:**\n"
            f"```\n{json.dumps(tool_call_input, indent=2)}\n```\n"
            f"\n\n**output:**\n "
            f"```\n{json.dumps(tool_call_output, indent=2)}\n```"
        )
        st.markdown(msg, unsafe_allow_html=True)


def handle_user_input(side_bar: SideBar) -> None:
    """Process user input, generate AI response, and update chat history."""
    prompt = st.chat_input() or st.session_state.modified_prompt
    if prompt:
        st.session_state.modified_prompt = None
        parts = get_parts_from_files(
            upload_gcs_checkbox=st.session_state.checkbox_state,
            uploaded_files=side_bar.uploaded_files,
            gcs_uris=side_bar.gcs_uris,
        )
        st.session_state["gcs_uris_to_be_sent"] = ""
        parts.append({"type": "text", "text": prompt})
        st.session_state.user_chats[st.session_state["session_id"]]["messages"].append(
            HumanMessage(content=parts).model_dump()
        )

        display_user_input(parts)
        generate_ai_response(
            remote_agent_engine_id=side_bar.remote_agent_engine_id,
            agent_callable_path=side_bar.agent_callable_path,
            url=side_bar.url_input_field,
            authenticate_request=side_bar.should_authenticate_request,
        )
        update_chat_title()
        if len(parts) > 1:
            st.session_state.uploader_key += 1
        st.rerun()


def display_user_input(parts: Sequence[dict[str, Any]]) -> None:
    """Display the user's input in the chat interface."""
    human_message = st.chat_message("human")
    with human_message:
        existing_user_input = format_content(parts)
        st.markdown(existing_user_input, unsafe_allow_html=True)


def generate_ai_response(
    remote_agent_engine_id: str | None = None,
    agent_callable_path: str | None = None,
    url: str | None = None,
    authenticate_request: bool = False,
) -> None:
    """Generate and display the AI's response to the user's input."""
    ai_message = st.chat_message("ai")
    with ai_message:
        status = st.status("Generating answer🤖")
        stream_handler = StreamHandler(st=st)
        client = Client(
            remote_agent_engine_id=remote_agent_engine_id,
            agent_callable_path=agent_callable_path,
            url=url,
            authenticate_request=authenticate_request,
        )
        get_chain_response(st=st, client=client, stream_handler=stream_handler)
        status.update(label="Finished!", state="complete", expanded=False)


def update_chat_title() -> None:
    """Update the chat title if it's currently empty."""
    if (
        st.session_state.user_chats[st.session_state["session_id"]]["title"]
        == EMPTY_CHAT_NAME
    ):
        st.session_state.session_db.set_title(
            st.session_state.user_chats[st.session_state["session_id"]]
        )
    st.session_state.session_db.upsert_session(
        st.session_state.user_chats[st.session_state["session_id"]]
    )


def display_feedback(side_bar: SideBar) -> None:
    """Display a feedback component and log the feedback if provided."""
    if st.session_state.run_id is not None:
        feedback = streamlit_feedback(
            feedback_type="faces",
            optional_text_label="[Optional] Please provide an explanation",
            key=f"feedback-{st.session_state.run_id}",
        )
        if feedback is not None:
            client = Client(
                remote_agent_engine_id=side_bar.remote_agent_engine_id,
                agent_callable_path=side_bar.agent_callable_path,
                url=side_bar.url_input_field,
                authenticate_request=side_bar.should_authenticate_request,
            )
            client.log_feedback(
                feedback_dict=feedback,
                run_id=st.session_state.run_id,
            )


def main() -> None:
    """Main function to set up and run the Streamlit app."""
    setup_page()
    initialize_session_state()

    current_page = st.session_state["page"]

    build_header()
    side_bar = SideBar(st=st)
    side_bar.init_side_bar()

    if current_page == "home":
        display_messages()
        handle_user_input(side_bar=side_bar)
        display_feedback(side_bar=side_bar)

    elif current_page == "configure":
        st.header("Configure")

        selected = st.session_state["selected_account"]

        st.text_input(
            "Organization Name",
            value=selected["organization_name"],
            disabled=True
        )
        st.text_input(
            "Account Name",
            value=selected["account_name"],
            disabled=True
        )
        st.button("Back to Home", on_click=lambda: st.session_state.update({"page": "home"}))
    
    elif current_page == "program_overview":
        st.header("Program Overview")
        st.write("Placeholder for Program Overview...")
        st.button("Back to Home", on_click=lambda: st.session_state.update({"page": "home"}))

    elif current_page == "funnel_analysis":
        st.header("Funnel Analysis")
        st.write("Placeholder for Funnel Analysis...")
        st.button("Back to Home", on_click=lambda: st.session_state.update({"page": "home"}))

    elif current_page == "competitors":
        st.header("Competitors")
        st.write("Placeholder for Competitors...")
        st.button("Back to Home", on_click=lambda: st.session_state.update({"page": "home"}))

    elif current_page == "audiences":
        st.header("Audiences")
        st.write("Placeholder for Audiences...")
        st.button("Back to Home", on_click=lambda: st.session_state.update({"page": "home"}))

    elif current_page == "big_bets":
        st.header("Big Bets")
        st.write("Placeholder for Big Bets...")
        st.button("Back to Home", on_click=lambda: st.session_state.update({"page": "home"}))

    elif current_page == "exploration":
        st.header("Exploration & Ad Hoc Analysis")
        st.write("Placeholder for Exploration & Ad Hoc Analysis...")
        st.button("Back to Home", on_click=lambda: st.session_state.update({"page": "home"}))

    elif current_page == "support":
        st.header("Support")
        st.write("Placeholder for Support...")
        st.button("Back to Home", on_click=lambda: st.session_state.update({"page": "home"}))

    if current_page != "home":
        with side_bar.chat_placeholder.container():
            st.markdown("---")
            st.header("Chat")
            display_messages()
            handle_user_input(side_bar=side_bar)
            display_feedback(side_bar=side_bar)
            st.markdown("---")


if __name__ == "__main__":
    main()
