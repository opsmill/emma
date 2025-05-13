import json
import os
from typing import Any, Dict, Optional

import pandas as pd
import requests
import streamlit as st
from langchain_community.agents.openai_assistant import OpenAIAssistantV2Runnable
from langchain_core.messages import HumanMessage
from openai import OpenAI

from emma.streamlit_utils import set_page_config
from menu import menu_with_redirect

# ————————————————
# Setup & state defaults
# ————————————————

api_key = "EmmaDefaultAuthMakingInfrahubEasierToUse!!!11"
client = OpenAI(base_url="https://emma.opsmill.cloud/v1", api_key=api_key)
agent = OpenAIAssistantV2Runnable(
    assistant_id=os.environ.get("INFRAHUB_EXPLORER_ASSISTANT_ID", "asst_1XurhPZgTg2iBk3FcuqWQH0l"),
    as_agent=True,
    client=client,
    check_every_ms=1000,
)

for key, default in {
    "infrahub_branch": "main",
    "mcp_server_url": "http://localhost:8001",
    "thread_id": None,
    # now each msg is a dict with keys: role, type, content/data
    "messages": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def call_mcp(tool: str, params: Dict[str, Any]) -> Any:
    resp = requests.post(
        url=st.session_state.mcp_server_url,
        json={"tool": tool, "params": params},
        timeout=30,
    )
    resp.raise_for_status()
    res = resp.json().get("result", {})
    if not res.get("success", False):
        st.error(f"MCP error: {res.get('error', 'Unknown')}")
        return None
    return res


@st.cache_data
def fetch_schema(branch: str) -> Dict[str, Any]:
    r = call_mcp("infrahub_get_schema", {"infrahub_url": st.session_state.infrahub_address, "branch": branch})
    schemas = r.get("schemas", []) if r else []
    return {s["kind"]: s for s in schemas}


schema_data = fetch_schema(branch=st.session_state.infrahub_branch)

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
    "Retrieve the schema for the Tag",
    "List all the tags",
    "Give me the name of all the Devices",
]

if not st.session_state.messages:
    # Add buttons for demo prompts
    st.markdown("Example of prompt you can use:")

    for demo in demo_prompts:
        if st.button(demo):
            st.session_state.prompt_input = demo

    st.markdown("Or enter a message below to start.")


prompt = st.chat_input("Enter your message")

# Set the input field
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
            # assume you stored records under "data"
            df = pd.DataFrame.from_records(message["content"])
            st.dataframe(df)

        elif msg_type == "csv":
            st.download_button("📥 Download CSV", message["content"], "data.csv", "text/csv")

        elif msg_type == "json" and message["role"] == "assistant":
            with st.expander("🔧 Agent JSON (debug)", expanded=False):
                st.code(message["content"], language="json")

        else:
            # fallback to plain text
            st.markdown(message["content"])

# Handle new user input
if prompt:
    # 1) record user
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2) ask the agent
    sys = (
        "You’re a high-performance Infrahub AI assistant. "
        "Interpret the user’s request and output *only* one JSON object with these keys:\n"
        "- action: one of “fetch_nodes”, “count”, or “fetch_schema”\n"
        "- kind: the object type (required for all actions, including fetch_schema)\n"
        "- filters: a dict of filters to apply (use {} for fetch_schema)\n"
        "- partial_match: boolean (true or false; use false for fetch_schema)\n"
        "- output: “dataframe” or “csv” (use null for fetch_schema)\n"
        "- columns: optional list of column names (use null or omit for fetch_schema)\n"
        "If the user asks to filter on any attribute (e.g. “any attribute”, “attributes”), "
        "use key “any” (not “attributes”).\n"
        "No extra text, only the JSON."
    )
    with st.chat_message("assistant"):
        chat_input = {"content": f"System: {sys}\nUser: {prompt}\nKinds: {list(schema_data.keys())}"}

        if st.session_state.thread_id:
            chat_input["thread_id"] = st.session_state.thread_id
        with st.spinner(text="Thinking..."):
            resp = agent.invoke(input=chat_input)

    if not st.session_state.thread_id:
        st.session_state.thread_id = resp.return_values.get("thread_id")

    raw = resp.return_values.get("output", "").strip()
    # strip fences
    if raw.startswith("```"):
        raw = raw.strip("`").replace("json", "", 1).strip()

    # 3) store the JSON under a collapsed expander
    st.session_state.messages.append({"role": "assistant", "type": "json", "content": raw})

    # 4) parse it
    try:
        opts = json.loads(raw)
    except json.JSONDecodeError:
        st.session_state.messages.append(
            {"role": "assistant", "type": "text", "content": "❗ Failed to parse agent JSON"}
        )
        opts = {}

    # 5) perform the action
    action = opts.get("action")
    kind = opts.get("kind", None)
    filters = opts.get("filters", [])
    pm = opts.get("partial_match", False)
    out = opts.get("output", "dataframe")
    cols = opts.get("columns")

    # stylesheet: coerce single string -> list
    if isinstance(cols, str):
        cols = [cols]

    df: Optional[pd.DataFrame] = None

    if action in ("fetch_nodes", "count"):
        params = []
        if not kind and filters:
            if filters.get("kind"):
                kind = filters.get("kind")
                del filters["kind"]
        if not kind:
            st.session_state.messages.append({"role": "assistant", "type": "text", "content": "❌ No kind specified"})
            df = None
        else:
            params = {
                "infrahub_url": st.session_state.infrahub_address,
                "kind": kind,
                "branch": st.session_state.infrahub_branch,
                "partial_match": pm,
            }
        if filters:
            params["filters"] = filters
        nodes = call_mcp("infrahub_get_nodes", params).get("nodes", []) or []
        df = pd.json_normalize(nodes)
        df.columns = [c.split(".", 1)[1] if c.startswith(("attributes.", "relationships.")) else c for c in df.columns]
        if action == "count":
            st.session_state.messages.append(
                {"role": "assistant", "type": "text", "content": f"**Count:** {len(df)} ✅"}
            )
            df = None
        else:
            st.session_state.last_df = df
            st.session_state.last_kind = kind

    elif action == "fetch_schema":
        if kind or filters:
            if not kind and filters:
                kind = filters.get("kind")
            schema = schema_data.get(kind)
            if not schema:
                st.session_state.messages.append(
                    {"role": "assistant", "type": "text", "content": f"No schema found for kind '{kind}'"}
                )
            else:
                # render attributes & relationships under expanders
                st.session_state.messages.append({"role": "assistant", "type": "text", "content": f"## Schema: {kind}"})
                attrs = schema.get("attributes", [])
                if attrs:
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "type": "dataframe",
                            "content": pd.json_normalize(attrs).to_dict(orient="records"),
                        }
                    )
                rels = schema.get("relationships", [])
                if rels:
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "type": "dataframe",
                            "content": pd.json_normalize(rels).to_dict(orient="records"),
                        }
                    )
        else:
            # high-level summary of all schemas
            summary = [
                {
                    "kind": k,
                    "attributes": len(v.get("attributes", [])),
                    "relationships": len(v.get("relationships", [])),
                }
                for k, v in schema_data.items()
            ]
            df = pd.DataFrame(summary)

    # 6) if there's a leftover DataFrame to show
    if df is not None:
        # column filter
        if cols:
            available = df.columns.tolist()
            lookup = {c.lower(): c for c in available}
            pick = []
            for r in cols:
                if r in available:
                    pick.append(r)
                elif r.lower() in lookup:
                    pick.append(lookup[r.lower()])
                else:
                    for p in ("attributes.", "relationships."):
                        c2 = p + r
                        if c2 in available:
                            pick.append(c2)
                            break
            if pick:
                df = df[pick]
            else:
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "type": "text",
                        "content": (
                            f"None of the requested columns were found.\nRequested: {cols}\nAvailable: {available}"
                        ),
                    }
                )
                df = None

        # store and/or serialize
        if df is not None:
            if out == "csv":
                csv = df.to_csv(index=False)
                st.session_state.messages.append({"role": "assistant", "type": "csv", "content": csv})
            else:
                st.session_state.messages.append(
                    {"role": "assistant", "type": "dataframe", "content": df.to_dict(orient="records")}
                )

    # 7) refresh so the top-loop will render everything
    st.rerun()
