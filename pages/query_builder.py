import datetime
import io
import json
import os
import re

import streamlit as st
import yaml
from infrahub_sdk.exceptions import GraphQLError
from langchain_community.agents.openai_assistant import OpenAIAssistantV2Runnable
from langchain_core.agents import AgentFinish
from openai import OpenAI

from emma.assistant_utils import generate_yaml
from emma.gql_queries import generate_full_query, get_gql_schema
from emma.infrahub import run_gql_query, get_instance_branch
from emma.streamlit_utils import handle_reachability_error, set_page_config
from menu import menu_with_redirect


api_key = "EmmaDefaultAuthMakingInfrahubEasierToUse!!!11"

client = OpenAI(base_url="https://emma.opsmill.cloud/v1", api_key=api_key)

tools = [generate_full_query]

agent = OpenAIAssistantV2Runnable(
    assistant_id=os.environ.get("OPENAI_ASSISTANT_ID", "asst_6O5PoPYLqD8FuJPAI7A6Odbj"),
    as_agent=True,
    client=client,
    check_every_ms=1000,
)


def execute_agent(agent_runner, user_prompt):
    tool_map = {tool.name: tool for tool in tools}

    resp = agent_runner.invoke(
        user_prompt,
        attachments=[
            {
                "file_id": st.session_state.infrahub_query_fid,
                "tools": [{"type": "file_search"}],
            }
        ],
    )

    with st.spinner("Refining your query! Just another moment."):
        while not isinstance(resp, AgentFinish):
            tool_outputs = []
            for action in resp:
                print(f"Querying base object: {action.tool_input}")
                tool_output = tool_map[action.tool].invoke(action.tool_input)
                tool_outputs.append({"output": tool_output, "tool_call_id": action.tool_call_id})
            resp = agent.invoke(
                {"tool_outputs": tool_outputs, "run_id": action.run_id, "thread_id": action.thread_id}  # pylint: disable=undefined-loop-variable
            )

    return resp


def remove_extra_values(d):
    if isinstance(d, dict):
        schema_key = "__schema"
        if schema_key in d:
            return {schema_key: remove_extra_values(d[schema_key])}

        if d.get("isDeprecated") is False:
            del d["isDeprecated"]

        return {k: remove_extra_values(v) for k, v in d.items()}

    if isinstance(d, list):
        data = [obj for obj in d if isinstance(obj, dict) and "__" not in obj.get("name", "")]
        return [remove_extra_values(v) for v in data if v is not None]
    return d


INITIAL_PROMPT = """\n\nThe above is the user requirements spec!

Once you find the right root object, you MUST use the generate_full_query tool
to fetch all the fields that you can fetch data from for the given object.

Do not assume your search results are complete - that is what the tool is for!

You'll want to filter down the huge query you generated to what you're actually after!

*DO* use fragments to conditionally fetch extra data where present

*DO NOT* include internal attributes like:

is_default
is_inherited
is_protected
is_visible
updated_at
id
is_from_profile

unless the user specifically requests internal attributes.

Your query needs to be concise, and without any extra data outside of the users query."""

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
    if "query_thread_id" in st.session_state:
        del st.session_state.query_thread_id

    if "prompt_input" in st.session_state:
        del st.session_state.prompt_input

    st.session_state.query_messages = []

    st.rerun()

# Fetch GraphQL schema
if "infrahub_query_fid" not in st.session_state:
    with st.spinner(text="Processing the schema! Just a second."):
        gql_schema = get_gql_schema(st.session_state.infrahub_branch)
        # gql_schema = get_gql_schema(branch=get_instance_branch())

        if not gql_schema:
            handle_reachability_error()

        else:
            clean_schema = remove_extra_values(gql_schema)

            yaml_schema = yaml.dump(clean_schema, default_flow_style=False)

            # For testing schema output
            # with open("text.yml", "w") as f:
            #     f.write(yaml_schema)

            file_like_object = io.BytesIO(yaml_schema.encode("utf-8"))
            file_like_object.name = "graphql_schema.yaml.txt"
            message_file = client.files.create(file=file_like_object, purpose="assistants")
            st.session_state.infrahub_query_fid = message_file.id

# Demo prompts
demo_prompts = [
    "I need a query to grab all the info available to template VRF configs.",
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
        if not st.session_state.query_messages:
            prompt += INITIAL_PROMPT

        chat_input = {"content": prompt}
        if "query_thread_id" in st.session_state:
            chat_input["thread_id"] = st.session_state.query_thread_id

        with st.spinner(text="Thinking! Just a moment..."):
            response = execute_agent(agent, chat_input)

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
