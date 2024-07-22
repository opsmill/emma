import datetime
import io
import os
import re

import streamlit as st
import yaml
from langchain_community.agents.openai_assistant import OpenAIAssistantV2Runnable
from openai import OpenAI

from emma.infrahub import get_schema, check_schema
from emma.streamlit_utils import set_page_config
from menu import menu_with_redirect


client = OpenAI(base_url="https://emma-gateway.cloudflare-096.workers.dev/v1", api_key="Emma doesn't require one!")

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


set_page_config(title="Schema Builder")
st.markdown("# Schema Builder")
menu_with_redirect()

agent = OpenAIAssistantV2Runnable(assistant_id="asst_tQPcGt2OV7fuVgi4JmwsgeHJ", as_agent=True, client=client, check_every_ms=500)

if "messages" not in st.session_state:
    st.session_state.messages = []

if "infrahub_schema_fid" not in st.session_state:
    infra_schema = get_schema(st.session_state["infrahub_branch"])

    transformed_schema = {
        k: transform_schema(v.model_dump())
        for k, v in infra_schema.items()
        if v.namespace  # not in ("Core", "Profile", "Builtin")
    }

    yaml_schema = yaml.dump(transformed_schema, default_flow_style=False)

    # Convert the schema to a BytesIO object
    file_like_object = io.BytesIO(yaml_schema.encode("utf-8"))
    file_like_object.name = "current_schema.yaml.txt"

    # Upload the file-like object
    message_file = client.files.create(file=file_like_object, purpose="assistants")

    st.session_state["infrahub_schema_fid"] = message_file.id

    # Create and store the schema overview for the initial prompt
    overviews = [transform_schema_overview(schema.model_dump()) for schema in infra_schema.values()]
    st.session_state["schema_overview"] = merge_overviews(overviews)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("What is up?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        chat_input = {"content": prompt}

        if "thread_id" in st.session_state:
            chat_input["thread_id"] = st.session_state.thread_id
        else:
            chat_input["content"] = (
                INITIAL_PROMPT_HEADER.format(overview=st.session_state["schema_overview"]) + chat_input["content"]
            )

        response = agent.invoke(
            input=chat_input,
            attachments=[
                {
                    "file_id": st.session_state["infrahub_schema_fid"],
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

# Create columns for buttons
col1, col2, *_ = st.columns([1, 1, 1, 1, 1, 1, 1, 1])

with col1:
    if st.button("Export Chat"):
        markdown_buffer = generate_markdown(st.session_state.messages)

        st.download_button(
            label="Download Markdown",
            data=markdown_buffer,
            file_name=f"schema_generator_log_{datetime.datetime.now(tz=datetime.timezone.utc)}.md",
            mime="text/markdown",
        )

with col2:
    # Check Schema button
    if st.button("Check Schema"):
        combined_code = "\n\n".join(
            re.findall(r"```(.*?)```", "\n\n".join(x["content"] for x in st.session_state.messages), re.DOTALL)
        )

        schema_result, schema_detail = check_schema(st.session_state["infrahub_branch"], combined_code)

        if schema_result:
            st.write("Schema Check Result:", schema_detail)
        else:
            st.exception("Uhoh! We've got a problem.\n", schema_detail)
