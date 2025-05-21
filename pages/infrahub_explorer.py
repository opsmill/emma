import json
import os
from typing import Any, Optional

from emma.infrahub import get_instance_address
import pandas as pd
import requests
import streamlit as st
from langchain_community.agents.openai_assistant import OpenAIAssistantV2Runnable
from openai import OpenAI

from emma.streamlit_utils import set_page_config
from menu import menu_with_redirect

# ————————————————
# Setup & state defaults
# ————————————————
for key, default in {
    "infrahub_branch": "main",
    "mcp_server_url": "http://localhost:8001",
    "thread_id": None,
    "messages": [],
    # cache our tool-list and schema
    "mcp_tools": None,
    "schema_data": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# OpenAI + Assistant client
api_key = "EmmaDefaultAuthMakingInfrahubEasierToUse!!!11"
client = OpenAI(base_url="https://emma.opsmill.cloud/v1", api_key=api_key)
agent = OpenAIAssistantV2Runnable(
    assistant_id=os.environ.get(
        "INFRAHUB_EXPLORER_ASSISTANT_ID",
        "asst_1XurhPZgTg2iBk3FcuqWQH0l",
    ),
    as_agent=True,
    client=client,
    check_every_ms=1000,
)


def call_mcp(tool: str, params: dict[str, Any] | None = None) -> dict | None:
    """
    JSON-RPC style call into the MCP server.

    Args:
        tool: Name of the tool to call
        params: Dictionary of parameters to pass to the tool

    Returns:
        dict: Result of the tool call or None if there was an error

    """
    extended_params = params
    if st.session_state.infrahub_address:
        extended_params["infrahub_url"] = get_instance_address()

    if tool == "tools/discover":
        payload = {"tool": "tools/discover", "params": {}}
    else:
        payload = {
            "tool": "tools/call",
            "params": {
                "name": tool,
                "arguments": extended_params
            },
        }

    resp = requests.post(
        url=st.session_state.mcp_server_url,
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    # expected shape: {"result": ...}
    result = data.get("result")
    if result is None:
        st.error(f"Malformed MCP reply: {data}")
        return None

    # for real tool calls, check success flag
    if tool != "tools/discover" and not result.get("success", False):
        st.error(f"MCP error: {result.get('error', 'Unknown')}")
        return None

    return result


@st.cache_data
def discover_tools() -> list[dict[str, Any]]:
    """Fetch the list of available MCP tools (name / description / parameters).

    Returns:
        list[dict[str, Any]]: List of tools, each with name, description, and parameters

    """
    tools = call_mcp("tools/discover", {})
    return tools or []


@st.cache_data
def fetch_schema(branch: str) -> dict[str, Any]:
    """Fetch the schema for the given branch from Infrahub.

    Returns:
        dict[str, Any]: Dictionary of all schema organized by kind

    """
    r = call_mcp(
        "infrahub_get_schemas",
        {
            "branch": branch,
            # omit 'kind' → None to get all schemas
        },
    )
    schemas = r.get("schemas", []) if r else []
    return {s["kind"]: s for s in schemas}


# On first run, populate our session_state
if st.session_state.mcp_tools is None:
    st.session_state.mcp_tools = discover_tools()
if st.session_state.schema_data is None:
    st.session_state.schema_data = fetch_schema(st.session_state.infrahub_branch)

# ————————————————
# UI Layout
# ————————————————
set_page_config(title="Infrahub Explorer")
st.markdown("# Infrahub Explorer")
menu_with_redirect()

with st.expander("MCP Server Configuration", expanded=False):
    url = st.text_input("MCP Server URL", st.session_state.mcp_server_url)
    if url != st.session_state.mcp_server_url:
        st.session_state.mcp_server_url = url
        st.success("MCP URL updated")

# ————————————————
# Chat input & handling
# ————————————————
demo_prompts = [
    "Retrieve the schema for Tag",
    "List all the tags",
    "Give me the name of all the Devices",
    "Give me the interfaces of the Device named 'atl1-edge1'",
]

if not st.session_state.messages:
    st.markdown("Example of prompt you can use:")
    for demo in demo_prompts:
        if st.button(demo):
            st.session_state.prompt_input = demo
    st.markdown("Or enter a message below to start.")

prompt = st.chat_input("Enter your message")

# If using a demo button
if "prompt_input" in st.session_state:
    prompt = st.session_state.prompt_input
    del st.session_state.prompt_input

# Display previous messages
for message in st.session_state.messages:
    if message["role"] == "user":
        st.markdown(message["content"])
    else:
        msg_type = message.get("type", "text")
        if msg_type == "dataframe":
            df = pd.DataFrame.from_records(message["content"])
            st.dataframe(df)
        elif msg_type == "csv":
            st.download_button("📥 Download CSV", message["content"], "data.csv", "text/csv")
        elif msg_type == "json" and message["role"] == "assistant":
            with st.expander("🔧 Agent JSON (debug)", expanded=False):
                st.code(message["content"], language="json")
        else:
            st.markdown(message["content"])

# Handle new user input
if prompt:
    # 1) record user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2) ask the assistant
    tool_list_md = "\n".join(f"- **{t['name']}**: {t['description']}" for t in st.session_state.mcp_tools)
    kinds_md = ", ".join(list(st.session_state.schema_data.keys()))

    system_prompt = f"""
        You’re a high-performance Infrahub AI assistant.  You have these MCP tools:
        {tool_list_md}

        Valid schema kinds are: {kinds_md}

        RULES:
        1) If the user asks about a kind in the list, call exactly one of your tools.

        2) If they ask about a kind _not_ in the list, call `infrahub_get_schemas` with no args.

        3) Always output *only* one JSON object:
            {{
            "action": "<tool name>",
            "arguments": {{ ... }}
            }}

        EXAMPLES:
        User: Retrieve the schema for Device
            {{
                "action": "infrahub_get_schemas",
                "arguments": {{ "kind": "{{ valid kind from above }}", "branch": "{st.session_state.infrahub_branch}" }}
            }}

        User: List all the tags
            {{
                "action": "infrahub_get_nodes",
                "arguments": {{ "kind": "{{ valid kind from above }}", "branch": "{st.session_state.infrahub_branch}" }}
            }}

        User: Retrieve the interfaces of the device 'atl1-core1'
            {{
                "action": "infrahub_get_related_nodes",
                "arguments": {{
                    "kind": "{{ valid kind from above }}",
                    "filters": {{ "hfid__value": "atl1-core1" }},
                    "relation": "interfaces",
                    "branch": "{st.session_state.infrahub_branch}"
                }}
            }}

        User: Retrieve the interfaces of the device '183e2e4e-a505-c9c9-3b9c-1065606772de'
            {{
                "action": "infrahub_get_related_nodes",
                "arguments": {{
                    "kind": "{{ valid kind from above }}",
                    "filters": {{ "ids": ["183e2e4e-a505-c9c9-3b9c-1065606772de"] }},
                    "relation": "interfaces",
                    "branch": "{st.session_state.infrahub_branch}"
                }}
            }}

        No extra text.only the JSON.
    """

    # invoke the assistant
    with st.chat_message("assistant"):
        chat_input = {
            "content": f"System: {system_prompt}\nUser: {prompt}"
        }
        if st.session_state.thread_id:
            chat_input["thread_id"] = st.session_state.thread_id
        resp = agent.invoke(input=chat_input)

    # persist thread id
    if not st.session_state.thread_id:
        st.session_state.thread_id = resp.return_values.get("thread_id")

    raw = resp.return_values.get("output", "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").replace("json", "", 1).strip()

    # store JSON for debug
    st.session_state.messages.append({"role": "assistant", "type": "json", "content": raw})

    # parse
    try:
        call = json.loads(raw)
        action = call["action"]
        args = call.get("arguments", {})
    except Exception:
        st.session_state.messages.append({
            "role": "assistant", "type": "text",
            "content": "❗ Failed to parse assistant JSON"
        })
        action = args = None

    df: Optional[pd.DataFrame] = None

    # handle each tool
    if action == "infrahub_get_nodes":
        res = call_mcp(action, args)
        if res:
            nodes = res.get("nodes", [])
            df = pd.json_normalize(nodes)
    elif action == "infrahub_get_schemas":
        res = call_mcp(action, args)
        # case A: you got the full list back
        if res and "schemas" in res:
            schemas = res["schemas"]
            df = pd.DataFrame([
                {"kind": s["kind"], "attrs": len(s["attributes"]), "rels": len(s["relationships"])}
                for s in schemas
            ])
        # case B: you got a single schema back
        if res and "attributes" in res and "relationships" in res:
            # header
            st.session_state.messages.append({
                "role": "assistant",
                "type": "text",
                "content": f"## Schema: {res.get('kind','?')}"
            })
            # attributes table
            if res["attributes"]:
                st.session_state.messages.append({
                    "role": "assistant",
                    "type": "dataframe",
                    "content": pd.json_normalize(res["attributes"]).to_dict("records")
                })
            # relationships table
            if res["relationships"]:
                st.session_state.messages.append({
                    "role": "assistant",
                    "type": "dataframe",
                    "content": pd.json_normalize(res["relationships"]).to_dict("records")
                })
            df = None
        else:
            # unexpected shape
            st.session_state.messages.append({
                "role": "assistant",
                "type": "text",
                "content": f"❗ Unexpected response shape from infrahub_get_schemas: {res}"
            })
            df = None
    elif action == "infrahub_get_related_nodes":
        # if not args.get("node_id"):
        #     kind = args["kind"]
        #     name = args["arguments"].pop("name__value", None)
        #     # fetch the node to get its id
        #     node_res = call_mcp("infrahub_get_nodes", {
        #         "kind": kind, "branch": st.session_state.infrahub_branch,
        #         "filters": {"any__value": name}
        #     })
        #     node_id = node_res["nodes"][0]["index"]
        #     args["node_id"] = node_id

        res = call_mcp(action, args)
        if res:
            nodes = res.get("nodes", [])
            df = pd.json_normalize(nodes)

    elif action == "infrahub_query_graphql":
        res = call_mcp(action, args)
        if res:
            data = res.get("data", {})
            st.session_state.messages.append({"role": "assistant", "type": "json", "content": json.dumps(data, indent=2)})
    else:
        st.session_state.messages.append(
            {"role": "assistant", "type": "text", "content": f"❌ Unknown action: {action}"}
        )

    # render DataFrame if present
    if df is not None:
        st.session_state.messages.append({"role": "assistant", "type": "dataframe", "content": df.to_dict("records")})

    st.rerun()
