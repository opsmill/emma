import datetime
import io
import json
import os
import re
from typing import Dict, List

import streamlit as st
import yaml
from infrahub_sdk import GraphQLError
from langchain_community.agents.openai_assistant import OpenAIAssistantV2Runnable
from openai import OpenAI

from emma.infrahub import get_gql_schema, handle_reachability_error, run_gql_query
from emma.streamlit_utils import set_page_config
from menu import menu_with_redirect

api_key = "EmmaDefaultAuthMakingInfrahubEasierToUse!!!11"

client = OpenAI(base_url="https://emma.opsmill.cloud/v1", api_key=api_key)

agent = OpenAIAssistantV2Runnable(
    assistant_id=os.environ.get("OPENAI_ASSISTANT_ID", "asst_C3nvIFTrdcj6pVdA5jThL7JI"),
    as_agent=True,
    client=client,
    check_every_ms=1000,
)


def remove_none_values(d):
    if isinstance(d, dict):
        if d.get("isDeprecated") is False:
            del d["isDeprecated"]
        return {k: remove_none_values(v) for k, v in d.items() if v is not None}
    if isinstance(d, list):
        return [remove_none_values(v) for v in d if v is not None]
    return d


ERROR_PROMPT = """We've generated the following query, but when running it against Infrahub we ran into some problems.
Regenerate the query so that it will work.

Query:
```gql
{query}
```

Errors:
```
{errors}
```"""


# YAML generator with custom string presenter
def generate_yaml(conversation: List[Dict]):
    def str_presenter(dumper, data):
        if "\n" in data:
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)

    yaml.add_representer(str, str_presenter)
    return yaml.dump(conversation, default_flow_style=False)


# Set Streamlit page configuration
set_page_config(title="Query Builder")

# Initialize session state
if "query_messages" not in st.session_state:
    st.session_state.query_messages = []

buttons_disabled = not st.session_state.query_messages

# UI Elements
st.markdown("# Query Builder")
menu_with_redirect()

# Sidebar for exporting conversation and starting a new chat
yaml_buffer = generate_yaml(st.session_state.query_messages)
st.sidebar.download_button(
    label="Export Conversation",
    data=yaml_buffer,
    file_name=f"query_builder_log_{datetime.datetime.now(tz=datetime.timezone.utc)}.yml",
    mime="text/markdown",
    disabled=buttons_disabled,
)

if st.sidebar.button("New Chat", disabled=buttons_disabled):
    if "thread_id" in st.session_state:
        del st.session_state.thread_id

    if "prompt_input" in st.session_state:
        del st.session_state.prompt_input

    st.session_state.query_messages = []

    st.rerun()

# Fetch GraphQL schema
if "infrahub_query_fid" not in st.session_state:
    with st.spinner(text="Processing the schema! Just a second."):
        gql_schema = get_gql_schema(st.session_state.infrahub_branch)

        if not gql_schema:
            handle_reachability_error()

        else:
            clean_schema = remove_none_values(gql_schema)

            yaml_schema = yaml.dump(clean_schema, default_flow_style=False)
            file_like_object = io.BytesIO(yaml_schema.encode("utf-8"))
            file_like_object.name = "graphql_schema.yaml.txt"
            message_file = client.files.create(file=file_like_object, purpose="assistants", chunking_strategy={})
            st.session_state.infrahub_query_fid = message_file.id

# Demo prompts
demo_prompts = [
    "I need a query to grab all the info I need to template VRF configs.",
    "Can you show a helpful IPAM query for getting started?",
    "How would I query ip prefixes per location? And filter by location?",
]

if not st.session_state.query_messages:
    st.markdown("### Try me!")
    for demo in demo_prompts:
        if st.button(demo):
            st.session_state.prompt_input = demo
    st.markdown("Or enter a message below to start.")

# Handle user input
prompt = st.chat_input("What is up?")
if "prompt_input" in st.session_state:
    prompt = st.session_state.prompt_input
    del st.session_state.prompt_input

for message in st.session_state.query_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt:
    st.session_state.query_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        chat_input = {"content": prompt}
        if "query_thread_id" in st.session_state:
            chat_input["thread_id"] = st.session_state.query_thread_id

        with st.spinner(text="Thinking! Just a moment..."):
            response = agent.invoke(
                input=chat_input,
                attachments=[
                    {
                        "file_id": st.session_state.infrahub_query_fid,
                        "tools": [{"type": "file_search"}],
                    }
                ],
            )

        if "query_thread_id" not in st.session_state:
            st.session_state.query_thread_id = response.return_values["thread_id"]  # type: ignore[union-attr]

        output = response.return_values["output"]  # type: ignore[union-attr]

        st.write(output)

    st.session_state.query_messages.append({"role": "assistant", "content": output})
    st.session_state.combined_code = "\n\n".join(re.findall(r"```graphql(.*?)```", output, re.DOTALL)).lstrip("\n")
    st.rerun()

col1, col2, col3 = st.columns([2, 2, 2])

# Check query button
with col1:
    if st.button(
        "Check query",
        disabled=buttons_disabled or st.session_state.query_messages[-1]["role"] == "ai",
        help="Check the query with your Infrahub instance",
    ):
        assistant_messages = [m for m in st.session_state.query_messages if m["role"] == "assistant"]
        try:
            query_check_result = run_gql_query(
                branch=st.session_state.infrahub_branch, query=st.session_state.combined_code
            )

            message = f"""Query is valid!

Here's a sample of your data:

```json
{json.dumps(query_check_result, indent=4)[:500]}...
```

Want to download it? Or refine it?"""

            st.session_state.check_query_errors = False

        except GraphQLError as e:
            st.session_state.query_errors = e.errors  # Store errors in session state

            message = "Hmm, looks like we've got some problems.\n\n```json" + json.dumps(e.errors, indent=4)

        st.session_state.query_messages.append({"role": "ai", "content": message})
        st.rerun()

if st.session_state.get("combined_code"):
    code = st.session_state.combined_code.splitlines()
    filename = (
        code[0].replace("#", "").lstrip()
        if code[0].lstrip().startswith("#")
        else f"query_generated_{str(datetime.datetime.now(tz=datetime.timezone.utc))[:16]}.gql"
    )
    code = "\n".join(code[1:] if filename != code[0] else code)

    with col2:
        st.download_button(
            label="Download query",
            data=code,
            file_name=filename,
            mime="text/gql",
        )

# Fix query button
with col1:
    if st.session_state.get("query_errors"):
        if st.button("Fix query", help="Send the generated query and errors to our query builder"):
            st.session_state.prompt_input = ERROR_PROMPT.format(
                errors=st.session_state.query_errors, query=st.session_state.combined_code
            )
            st.session_state.query_errors = False
            st.rerun()
