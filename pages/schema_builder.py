import datetime
import io
import json
import os
import re

import streamlit as st
import yaml
from langchain_community.agents.openai_assistant import OpenAIAssistantV2Runnable
from openai import OpenAI

from emma.infrahub import check_schema, get_schema, handle_reachability_error
from emma.streamlit_utils import set_page_config
from menu import menu_with_redirect

api_key = "EmmaDefaultAuthMakingInfrahubEasierToUse!!!11"

client = OpenAI(base_url="https://emma.opsmill.cloud/v1", api_key=api_key)

agent = OpenAIAssistantV2Runnable(
    assistant_id=os.environ.get("OPENAI_ASSISTANT_ID", "asst_ftBgbXuXwdiMa8AyvMMSeIwU"),
    as_agent=True,
    client=client,
    check_every_ms=1000,
)

INITIAL_PROMPT_HEADER = """The following is a user request for a new schema, or a modification.
You are to generate a new schema segment that will work with the provided existing schema.

The file attached you've been provided is the existing schema.
Here is an overview of the nodes present, in `namespace: [node: [attribute: kind]]` format.

This is *not* the format we want back, just an idea of what is here already.

```yml
{overview}
```

User request:
"""

ERROR_PROMPT = """We've generated the following schema, but when validating with Infrahub we ran into some problems.
Regenerate the schema so that it will pass our checks.

Schema:
```yml
{schema}
```

Errors:
{errors}
"""


def transform_schema(schema_dict):
    transformed = {
        "name": schema_dict["name"],
        "namespace": schema_dict["namespace"],
        "label": schema_dict["label"],
        "description": schema_dict["description"],
        "default_filter": schema_dict.get("default_filter"),
        "human_friendly_id": schema_dict.get("human_friendly_id"),
        "attributes": [],
        "relationships": [],
    }

    for attr in schema_dict["attributes"]:
        transformed["attributes"].append(
            {
                "name": attr["name"],
                "kind": attr["kind"],
                "unique": attr.get("unique", False),
                "optional": attr.get("optional", False),
            }
        )

    for rel in schema_dict["relationships"]:
        transformed["relationships"].append(
            {
                "name": rel["name"],
                "peer": rel["peer"],
                "cardinality": rel["cardinality"],
                "kind": rel["kind"],
                "optional": rel.get("optional", False),
            }
        )

    return transformed


def transform_schema_overview(schema_dict):
    overview = {}
    namespace = schema_dict["namespace"]

    if namespace not in overview:
        overview[namespace] = {}

    node_name = schema_dict["name"]
    overview[namespace][node_name] = {}

    # Add attributes with their kinds
    for attr in schema_dict["attributes"]:
        overview[namespace][node_name][attr["name"]] = attr["kind"]

    return overview


def merge_overviews(overview_list):
    merged = {}
    for overview in overview_list:
        for namespace, nodes in overview.items():
            if namespace not in merged:
                merged[namespace] = {}
            for node_name, attrs in nodes.items():
                if node_name not in merged[namespace]:
                    merged[namespace][node_name] = {}
                merged[namespace][node_name].update(attrs)
    return merged


def generate_markdown(chat_log):
    buffer = io.BytesIO()
    for entry in chat_log:
        if entry["role"] == "user":
            out = f"## User\n\n{entry['content']}\n\n"
        else:
            out = f"## Assistant\n\n{entry['content']}\n\n"
        buffer.write(out.encode("utf-8"))
    buffer.seek(0)
    return buffer


def translate_errors(schema_errors):
    human_readable = []
    for error in schema_errors:
        if "loc" in error:
            location = " -> ".join(map(str, error["loc"][3:]))
            err_message = error["msg"]
            input_value = error["input"]
            human_readable.append(
                f"{err_message}\n\nLocation: {location}\n\nInput:\n```json\n{json.dumps(input_value, indent=2)}\n```"
            )
        else:
            err_message = error["message"]
            code = error["extensions"]["code"]
            human_readable.append(f"Error Message: {err_message}\n\n\tCode: {code}\n")
    return "\n\n".join(human_readable)


def translate_success(data):
    human_readable = []
    diff = data["diff"]

    if "added" in diff and diff["added"]:
        human_readable.append("Added:")
        for key, value in diff["added"].items():
            human_readable.append(f"  - {key}")

    if "changed" in diff and diff["changed"]:
        human_readable.append("\n\nChanged:")
        for key, value in diff["changed"].items():
            human_readable.append(f"  - {key}")
            if "relationships" in value["changed"] and value["changed"]["relationships"]["added"]:
                for rel_key in value["changed"]["relationships"]["added"]:
                    human_readable.append(f"    * Added relationship '{rel_key}'")

    if "removed" in diff and diff["removed"]:
        human_readable.append("Removed:")
        for key, value in diff["removed"].items():
            human_readable.append(f"  - {key}")

    return "\n".join(human_readable)


if "messages" not in st.session_state:
    st.session_state.messages = []

buttons_disabled = not st.session_state.messages

set_page_config(title="Schema Builder")
st.markdown("# Schema Builder")
menu_with_redirect()

markdown_buffer = generate_markdown(st.session_state.messages)

if st.sidebar.download_button(
    label="Export Conversation",
    data=markdown_buffer,
    file_name=f"schema_generator_log_{datetime.datetime.now(tz=datetime.timezone.utc)}.md",
    mime="text/markdown",
    disabled=buttons_disabled,
):
    pass


if st.sidebar.button("New Chat", disabled=buttons_disabled):
    del st.session_state.thread_id
    st.session_state.messages = []
    st.rerun()

if "infrahub_schema_fid" not in st.session_state:
    infrahub_schema = get_schema(st.session_state.infrahub_branch)
    if not infrahub_schema:
        handle_reachability_error()
    else:
        transformed_schema = {
            k: transform_schema(v.model_dump())
            for k, v in infrahub_schema.items()
            if v.namespace  # not in ("Core", "Profile", "Builtin")
        }

        yaml_schema = yaml.dump(transformed_schema, default_flow_style=False)

        # Convert the schema to a BytesIO object
        file_like_object = io.BytesIO(yaml_schema.encode("utf-8"))
        file_like_object.name = "current_schema.yaml.txt"

        # Upload the file-like object
        message_file = client.files.create(file=file_like_object, purpose="assistants")

        st.session_state.infrahub_schema_fid = message_file.id

        # Create and store the schema overview for the initial prompt
        overviews = [transform_schema_overview(schema.model_dump()) for schema in infrahub_schema.values()]
        st.session_state.schema_overview = merge_overviews(overviews)

demo_prompts = [
    "Generate a schema for kubernetes. It must contain Cluster, Node, Namespace.",
    "Build a DNS record schema, with a dropdown for record types.",
    "Come up with a simple schema for NTP.",
]

if not st.session_state.messages:
    # Add buttons for demo prompts
    st.markdown("### Try me!")

    for demo in demo_prompts:
        if st.button(demo):
            st.session_state.prompt_input = demo

    st.markdown("Or enter a message below to start.")


prompt = st.chat_input("What is up?")

# Set the input field
if "prompt_input" in st.session_state:
    prompt = st.session_state.prompt_input
    del st.session_state.prompt_input

# Display previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle new user input
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Existing code to handle the assistant response
    with st.chat_message("assistant"):
        chat_input = {"content": prompt}

        if "thread_id" in st.session_state:
            chat_input["thread_id"] = st.session_state.thread_id
        else:
            chat_input["content"] = (
                INITIAL_PROMPT_HEADER.format(overview=st.session_state.schema_overview) + chat_input["content"]
            )
        with st.spinner(text="Thinking! Just a moment..."):
            response = agent.invoke(
                input=chat_input,
                attachments=[
                    {
                        "file_id": st.session_state.infrahub_schema_fid,
                        "tools": [{"type": "file_search"}],
                    }
                ],
            )

        if "thread_id" not in st.session_state:
            st.session_state.thread_id = response.return_values["thread_id"]  # type: ignore[union-attr]

        st.write(response.return_values["output"])  # type: ignore[union-attr]

    st.session_state.messages.append(
        {"role": "assistant", "content": response.return_values["output"]}  # type: ignore[union-attr]
    )

    st.rerun()

# Check Schema button
if st.button(
    "Check Schema",
    disabled=buttons_disabled or st.session_state.messages[-1]["role"] == "ai",
    help="Check the schema with your Infrahub instance",
):
    assistant_messages = [m for m in st.session_state.messages if m["role"] == "assistant"]
    combined_code = "\n\n".join(re.findall(r"```(?:\w+)?(.*?)```", assistant_messages[-1]["content"], re.DOTALL))

    schema_check_result = check_schema(branch=st.session_state.infrahub_branch, schemas=[yaml.safe_load(combined_code)])
    if schema_check_result:
        if not schema_check_result.success:
            errors = None
            if schema_check_result.response:
                if "detail" in schema_check_result.response:
                    errors = schema_check_result.response["detail"]
                else:
                    errors = schema_check_result.response["errors"]

            errors_out = translate_errors(schema_errors=errors)
            st.session_state.check_schema_errors = errors_out  # Store errors in session state
            st.session_state.combined_code = combined_code  # Store schema code in session state

            message = "Hmm, looks like we've got some problems.\n\n" + errors_out
        else:
            message = "Schema is valid!\n\n" + translate_success(data=schema_check_result.response)
            st.session_state.check_schema_errors = None  # Clear any previous errors

    # We use 'ai' as the role here to format the message the same as assistant messages,
    # But not include them in the messages we look for schema in.
    st.session_state.messages.append(
        {"role": "ai", "content": message}  # type: ignore[union-attr]
    )
    st.rerun()

if st.session_state.get("check_schema_errors"):
    if st.button("Fix Schema", help="Send the generated schema and errors to our schema builder"):
        st.session_state.prompt_input = ERROR_PROMPT.format(
            errors=st.session_state.check_schema_errors, schema=st.session_state.combined_code
        )
        del st.session_state.check_schema_errors
        st.rerun()  # Force rerun to handle new prompt input
