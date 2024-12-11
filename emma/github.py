import base64

import streamlit as st
import yaml
from github import Github, UnknownObjectException


@st.cache_resource
def get_github_object():
    return Github()


@st.cache_data
def get_schema_library():
    github = get_github_object()
    repo = github.get_repo("opsmill/schema-library")
    return repo


# TODO: Look into potentially passing in the latest commit hash so it will refresh if the repo is at a different hash
@st.cache_data
def get_schema_library_path(path=""):
    schema_library = get_schema_library()
    return schema_library.get_contents(path)


@st.cache_data
def get_readme(path: str):
    schema_library = get_schema_library()
    try:
        readme = schema_library.get_contents(f"{path}/README.md")
    except UnknownObjectException:
        return None

    return base64.b64decode(readme.content).decode("utf-8")


def read_github_yaml(yaml_file) -> dict:
    raw_content = yaml_file.decoded_content.decode("utf-8")
    return yaml.safe_load(raw_content)


@st.cache_data
def load_schemas_from_github(name: str):
    schemas = get_schema_library_path(name)
    schemas_data: list[dict] = []
    for schema in schemas:
        if schema.type == "file" and schema.name.endswith((".yaml", ".yml")):
            schemas_data.append(read_github_yaml(schema))
        # elif schema.type == "dir":
        #     files = get_schema_library_path(schema.path)
        #     for item in files:
        #         schema_file = SchemaFile(location=item)
        #         schema_file.load_content()
        #         schemas_data.append(schema_file)

    return schemas_data
