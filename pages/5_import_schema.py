import json
import os
from enum import Enum

import requests
import streamlit as st
import yaml
from pydantic import BaseModel

from emma.infrahub import add_branch_selector, get_client, get_schema, load_schema

st.set_page_config(page_title="Schema Importer")

add_branch_selector(st.sidebar)

st.markdown("# Schema Importer")

client = get_client(branch=st.session_state["infrahub_branch"])
schema = get_schema(branch=st.session_state["infrahub_branch"])

# option = st.selectbox("Select schema to import:", options=schema.keys())
# selected_schema = schema[option]

uploaded_file = st.file_uploader("Choose a schema file")


class MessageSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Message(BaseModel):
    severity: MessageSeverity = MessageSeverity.INFO
    message: str


def validate_yaml(file):
    error = ""
    try:
        yaml.safe_load(file)
    except yaml.YAMLError as error:
        return error


def strip_yaml_headers(yaml_input):
    lines = yaml_input.split("\n")
    stripped_lines = [
        line for line in lines
        if not line.startswith("#") and line != "---"
    ]
    return "\n".join(stripped_lines)


def upload_schema(file):
    url = st.session_state["infrahub_address"] + "/api/schema/load"
    api_key = os.environ.get("INFRAHUB_API_TOKEN")
    headers = {
        "Content-Type": "application/json",
        "X-INFRAHUB-KEY": f"{api_key}"
    }

    response = requests.post(url, headers=headers, data=json.dumps(file))

    response = 

    if response.status_code == 201:
        return None
    else:
        return response.text
        # print("Failed to upload schema")
        # print("Status code:", response.status_code)
        # print("Response:", response.text)


if uploaded_file is not None:
    container = st.container(border=True)
    file_contents = uploaded_file.read().decode("utf-8")
    cleaned_yaml = strip_yaml_headers(file_contents)
    errors = ""
    try:
        python_dict=yaml.safe_load(cleaned_yaml)
    except yaml.YAMLError as errors:
        container.error(errors.message)
        # return error
    # errors = validate_yaml(cleaned_yaml)

    # st.subheader("YAML File Contents:")
    # st.code(cleaned_yaml, language="yaml")

    # if errors:
    #     container.error(errors.message)

    json_data = json.dumps(python_dict, indent=2)

    st.subheader("JSON File Contents:")
    st.code(json_data, language="json")


    if json_data:
        if st.button("Import Schema"):
            with st.status("Loading schema...", expanded=True) as status:

                upload_error = upload_schema(json_data)

                if upload_error is None:
                    st.write("Schema loaded successfully!")
                    # status.update("Schema loading completed", state="complete", expanded=True)

                else:
                    container.error(upload_error)
                    st.write("Schema load error!")
                    # status.update("Schema load error!", state="error", expanded=True)

