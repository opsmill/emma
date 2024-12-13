import base64

import streamlit as st
import yaml
from github import Github
from github.ContentFile import ContentFile


@st.cache_resource
def get_github_object():
    return Github()


@st.cache_data
def get_schema_library():
    github = get_github_object()
    repo = github.get_repo("opsmill/schema-library")
    return repo


@st.cache_data
def get_schema_library_path(path=""):
    schema_library = get_schema_library()
    return schema_library.get_contents(path)


def get_readme(schema_dir: list[ContentFile]):
    readme = [file for file in schema_dir if file.name.lower() == "readme.md"]
    if not readme:
        return None
    return base64.b64decode(readme[0].content).decode("utf-8")


def read_github_yaml(yaml_file) -> dict:
    raw_content = yaml_file.decoded_content.decode("utf-8")
    return yaml.safe_load(raw_content)


def load_schemas_from_github(schema_files: list[ContentFile]):
    schemas_data: list[dict] = []
    for schema in schema_files:
        if schema.type == "file" and schema.name.endswith((".yaml", ".yml")):
            schemas_data.append(read_github_yaml(schema))
        # elif schema.type == "dir":
        #     files = get_schema_library_path(schema.path)
        #     for item in files:
        #         schema_file = SchemaFile(location=item)
        #         schema_file.load_content()
        #         schemas_data.append(schema_file)

    return schemas_data
