import os

import streamlit as st
import yaml
from langchain_community.agents.openai_assistant import OpenAIAssistantV2Runnable

from emma.infrahub import add_branch_selector, get_client

st.set_page_config(page_title="Schema Generator")

add_branch_selector(st.sidebar)


def display_actions(context):
    col1, col2, _ = context.columns(3)
    col1.button("Validate Schema", on_click=validate_candidate_schema)
    col2.button("Load Schema")


def validate_candidate_schema():
    message_content = ""

    if "candidate_schema" not in st.session_state:
        message_content = "No candidate schema to validate"
    else:
        client = get_client()
        success, response = client.schema.check(
            schemas=[st.session_state["candidate_schema"]], branch=st.session_state["infrahub_branch"]
        )

        assistant_msg = st.chat_message("assistant")
        if success:
            message_content = "Schema is Valid !!"
        else:
            message_content = response

    assistant_msg.write(message_content)
    st.session_state.messages.append({"role": "assistant", "content": message_content})


def extract_yaml_block(input: str) -> str | None:
    start_line: int | None = None
    end_line: int | None = None
    lines = input.split("\n")
    for idx, line in enumerate(lines):
        if start_line is None and line == "```yaml":
            start_line = idx
        if start_line and end_line is None and line == "```":
            end_line = idx

    if not start_line and end_line:
        return None

    yaml_lines = lines[start_line + 1 : end_line]
    return "\n".join(yaml_lines)


st.markdown("# Schema Generator")

if not os.environ.get("OPENAI_API_KEY"):
    st.error("You must provide a valid OpenAI API Key to use this application : OPENAI_API_KEY")

else:
    agent = OpenAIAssistantV2Runnable(assistant_id="asst_64Z6tLrMIpitG2MXoXLFwlGC", as_agent=True)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("What is up?"):
        st.session_state.messages.append({"role": "user", "content": prompt})

        user_msg = st.chat_message("user")
        user_msg.markdown(prompt)

        assistant_msg = st.chat_message("assistant")
        input = {"content": prompt}

        if "thread_id" in st.session_state:
            input["thread_id"] = st.session_state["thread_id"]

        response = agent.invoke(input=input)

        if "thread_id" not in st.session_state:
            st.session_state["thread_id"] = response.return_values["thread_id"]

        assistant_msg.write(response.return_values["output"])
        generated_schema = extract_yaml_block(response.return_values["output"])

        if generated_schema:
            data = yaml.safe_load(generated_schema)
            st.session_state.candidate_schema = data
            # display_actions(context=assistant_msg)

        st.session_state.messages.append({"role": "assistant", "content": response.return_values["output"]})
