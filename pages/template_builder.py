import datetime
import json
import os
import re

import streamlit as st
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.jinja2 import identify_faulty_jinja_code
from jinja2 import Template, TemplateSyntaxError
from langchain_community.agents.openai_assistant import OpenAIAssistantV2Runnable
from openai import OpenAI

from emma.assistant_utils import generate_yaml
from emma.infrahub import run_gql_query
from emma.streamlit_utils import set_page_config
from menu import menu_with_redirect

api_key = "EmmaDefaultAuthMakingInfrahubEasierToUse!!!11"

client = OpenAI(base_url="https://emma.opsmill.cloud/v1", api_key=api_key)

agent = OpenAIAssistantV2Runnable(
    assistant_id=os.environ.get("TEMPLATE_ASSISTANT_ID", "asst_RVFDTr6emtjcEqwQfNVNYmcm"),
    as_agent=True,
    client=client,
    check_every_ms=1000,
)

INITIAL_PROMPT = """\n\nYour user has provided the following gql query and return data.

We need you to build a j2 template to match this spec!

Query:
```gql
{query}
```

Returned data:
```json
{data}
```

Remember to look at the top of this message, that is our templating goal.

*NOTE* - The return data doesn't have a root "data" key.

In our data the edge/node keys are all important - Don't forget them!

You are REQUIRED to ONLY template out the data that is present in the above query/return data.

If it isn't present in the query above YOU MAY NOT USE IT.

These templates will be applied on a per-device basis, don't try to combine it all into one file.

Always assume that the user wants to create a small template to create a portion of a configuration.

Use Jinja's whitespace control feature to avoid rendering blank lines.

Make sure to include a comment as the top line with a good filename for this template!"""

ERROR_PROMPT = """We've generated the following template, but when trying to render
it with our gql query data from Infrahub we ran into some problems.

Regenerate the template so that it will work.

Query:
```gql
{query}
```

Template:
```j2
{template}
```

Errors:
```
{errors}
```

Don't forget the filename in a comment on the top line."""

# Set Streamlit page configuration
set_page_config(title="Template Builder")

# Initialize session state
if "template_messages" not in st.session_state:
    st.session_state.template_messages = []

if "config_fileids" not in st.session_state:
    st.session_state.config_fileids = []

if "gql_query" not in st.session_state:
    st.session_state.gql_query = ""

if "gql_data" not in st.session_state:
    st.session_state.gql_data = None

if "query_errors" not in st.session_state:
    st.session_state.query_errors = None

buttons_disabled = not st.session_state.template_messages or st.session_state.gql_data is None

# UI Elements
st.markdown("# Template Builder")
menu_with_redirect()

# Sidebar for exporting conversation and starting a new chat
yaml_buffer = generate_yaml(st.session_state.template_messages)
st.sidebar.download_button(
    label="Export Conversation",
    data=yaml_buffer,
    file_name=f"template_builder_log_{datetime.datetime.now(tz=datetime.timezone.utc)}.yml",
    mime="text/markdown",
    disabled=buttons_disabled,
)

if st.sidebar.button("New Chat", disabled=buttons_disabled):
    if "thread_id" in st.session_state:
        del st.session_state.thread_id

    if "prompt_input" in st.session_state:
        del st.session_state.prompt_input

    st.session_state.template_messages = []
    st.session_state.gql_data = None
    st.session_state.gql_query = ""

    st.rerun()

if not st.session_state.config_fileids:
    st.markdown(
        "## Upload Configs (Optional)\n\nWe don't require configs to build templates,"
        "but it can be helpful to make sure we get the syntax right!"
    )
    st.session_state.configs = st.file_uploader("Upload here", accept_multiple_files=True)

# GQL Query Input
st.markdown("""## Step 1: Enter your GQL Query

Emma will use your query to generate the template you're looking for.

Here we don't handle variables directly - You'll have to input those directly if you need a filter!""")

st.session_state.gql_query = st.text_area("GQL Query", st.session_state.gql_query, height=150)

if st.button("Run GQL Query") and st.session_state.gql_query:
    with st.spinner("Running your GQL query..."):
        try:
            st.session_state.gql_data = run_gql_query(
                branch=st.session_state.infrahub_branch, query=st.session_state.gql_query
            )
            st.session_state.query_errors = None
        except GraphQLError as e:
            st.session_state.query_errors = e.errors
            st.session_state.gql_data = None

if st.session_state.query_errors:
    st.error(f"Errors occurred: {json.dumps(st.session_state.query_errors, indent=4)}")

if st.session_state.gql_data:
    st.markdown("""## Step 2: GQL Data

Verify your data looks good, then tell me what we're templating!""")
    st.json(st.session_state.gql_data)

# Disable chat input if GQL data is not yet available
if st.session_state.gql_data:
    prompt = st.chat_input("What are we templating today?")
    if "prompt_input" in st.session_state:
        prompt = st.session_state.prompt_input
        del st.session_state.prompt_input

    for message in st.session_state.template_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt:
        st.session_state.template_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            if not st.session_state.template_messages:
                chat_input = {
                    "content": prompt
                    + INITIAL_PROMPT.format(query=st.session_state.gql_query, data=st.session_state.gql_data)
                }
            else:
                chat_input = {"content": prompt}

            if "template_thread_id" in st.session_state:
                chat_input["thread_id"] = st.session_state.template_thread_id

            with st.spinner("Thinking! Just a moment..."):
                response = agent.invoke(
                    input=chat_input,
                    attachments=[
                        {
                            "file_id": fileid,
                            "tools": [{"type": "file_search"}],
                        }
                        for fileid in st.session_state.config_fileids
                    ],
                )

            if "template_thread_id" not in st.session_state:
                st.session_state.template_thread_id = response.return_values["thread_id"]  # type: ignore[union-attr]

            output = response.return_values["output"].replace("data.", "")  # type: ignore[union-attr]

            st.write(output)

        st.session_state.template_messages.append({"role": "assistant", "content": output})
        st.session_state.combined_code = "\n\n".join(
            code for _, code in re.findall(r"```(j2|jinja2)\s*(.*?)```", output, re.DOTALL)
        ).lstrip("\n")

        print(st.session_state.combined_code)
        st.rerun()

# The rest of the code remains unchanged
col1, col2, col3 = st.columns([2, 2, 2])

# Check template button
with col1:
    if st.button(
        "Check template",
        disabled=buttons_disabled or st.session_state.template_messages[-1]["role"] == "ai",
        help="Check the template with your Infrahub instance",
    ):
        try:
            # Fetch the Jinja2 template from the generated code
            template = Template(
                st.session_state.combined_code,
                trim_blocks=True,
                lstrip_blocks=True,
            )

            # Render the template with the data from the GQL query
            rendered_output = template.render(st.session_state.gql_data)

            message = f"""Template rendering successful!

Here's the rendered output:

```txt
{rendered_output}
```

Want to download the template? Or refine it?"""

        except TemplateSyntaxError as e:
            # Handle Jinja2 template syntax errors
            st.session_state.template_errors = identify_faulty_jinja_code(e)

            message = (
                "Hmm, looks like we encountered a problem while rendering the template:\n\n"
                + st.session_state.template_errors
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            st.session_state.template_errors = str(e)

            message = "Hmm, looks like we encountered a problem while rendering the template:\n\n" + str(e)

        st.session_state.template_messages.append({"role": "ai", "content": message})
        st.rerun()


if st.session_state.get("combined_code"):
    code = st.session_state.combined_code.splitlines()
    filename = (
        code[0].replace("#", "").lstrip()
        if code[0].lstrip().startswith("#")
        else f"template_generated_{str(datetime.datetime.now(tz=datetime.timezone.utc))[:16]}.j2"
    )
    code = "\n".join(code[1:] if filename != code[0] else code)

    with col2:
        st.download_button(
            label="Download template",
            data=code,
            file_name=filename,
            mime="text/j2",
        )

# Fix template button
with col1:
    if st.session_state.get("template_errors"):
        if st.button("Fix template", help="Send the generated template and errors to our template builder"):
            st.session_state.prompt_input = ERROR_PROMPT.format(
                errors=st.session_state.template_errors,
                query=st.session_state.gql_query,
                template=st.session_state.combined_code,
            )
            st.session_state.template_errors = False
            st.rerun()
