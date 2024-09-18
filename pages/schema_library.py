import os
from enum import Enum
from os import listdir
from pathlib import Path

import streamlit as st
from infrahub_sdk import MainSchemaTypes

from emma.infrahub import (
    get_schema,
    get_schema_library_path,
    load_schema,
    load_schemas_from_disk,
)
from emma.streamlit_utils import set_page_config
from menu import menu_with_redirect

set_page_config(title="Schema Library")
st.markdown("# Schema Library")
menu_with_redirect()


class SchemaState(str, Enum):
    NOT_LOADED = "NOT_LOADED"
    LOADING = "LOADING"
    LOADED = "LOADED"


if "extensions_states" not in st.session_state:
    st.session_state.extensions_states = {}


def init_schema_extension_state(schema_extension: str) -> None:
    # Check if the extension is already in the session state
    if schema_extension not in st.session_state.extensions_states:
        # TODO: Here we need to evaluate if it's already existing in Infrahub ... somehow
        # So if it's the case we could put the proper LOADED state
        schema: dict[str, MainSchemaTypes] = get_schema()

        # FIXME: This is beyond hacking, but I need to define whether base extension is in place or not
        if schema_extension == "base":
            if "DcimDevice" in schema:
                st.session_state.extensions_states["base"] = SchemaState.LOADED
        else:
            st.session_state.extensions_states[schema_extension] = SchemaState.NOT_LOADED


# Function that checks if a readme exists in a given folder and return the content if so
def check_and_open_readme(path: Path) -> str:
    readme_path: Path = Path(f"{path}/README.md")

    # Check if the file exists
    if readme_path.exists() and readme_path.is_file() and readme_path.suffix == ".md":
        # Open the file in read mode
        with open(readme_path, "r") as readme_file:
            # Read the content of the file
            content: str = readme_file.read()
        return content
    else:
        return f"No `README.md` in '{path}'..."


def schema_loading_container(path: Path, schema_extension: str) -> None:
    with st.status(f"Loading schema extension `{schema_extension}` ...", expanded=True) as schema_loading_container:
        # Get schema content
        st.write("Opening schema file...")
        schema_content: list[dict] = load_schemas_from_disk(schemas=[path])
        st.write("Schema file loaded!")

        # Place request
        st.write("Calling Infrahub API...")
        response = load_schema(
            branch=st.session_state.infrahub_branch, schemas=[item.content for item in schema_content]
        )
        st.write("Computing results...")

        # Process the response
        if response:
            if response.errors:
                schema_loading_container.update(label="❌ Load failed ...", state="error", expanded=True)
                schema_loading_container.error("Infrahub doesn't like it!", icon="🚨")
                schema_loading_container.exception(response.errors)
            else:
                schema_loading_container.update(label="✅ Schema loaded!", state="complete", expanded=True)
                st.session_state.extensions_states[schema_extension] = SchemaState.LOADED

                if response.schema_updated:
                    st.write("Schema loaded successfully!")
                    st.write("Generating balloons...")
                    st.balloons()  # 🎉
                else:
                    schema_loading_container.info(
                        "The schema in Infrahub was already up to date, no changes were required!",
                        icon="ℹ️",
                    )


def on_click_schema_load(schema_extension: str):
    st.session_state.extensions_states[schema_extension] = SchemaState.LOADING


def render_schema_extension_content(schema_extension_path: Path, schema_extension_name: str) -> None:
    # Render description for the extension
    st.write(check_and_open_readme(schema_extension_path))

    # Prepare vars for the button
    is_button_disabled: bool = False
    button_label: str = "🚀 Load to Infrahub"
    if st.session_state.extensions_states.get(schema_extension_name) is SchemaState.LOADING:
        is_button_disabled = True
        button_label = "🚀 Load to Infrahub"
    elif st.session_state.extensions_states.get(schema_extension_name) is SchemaState.LOADED:
        is_button_disabled = True
        button_label = "✅ Already in Infrahub"

    # Render the button
    st.button(
        label=button_label,
        type="secondary",
        use_container_width=True,
        key=schema_extension_name,
        disabled=is_button_disabled,
        on_click=on_click_schema_load,
        args=[schema_extension_name],
    )

    # Render loading container if needed
    if st.session_state.extensions_states.get(schema_extension_name) is SchemaState.LOADING:
        schema_loading_container(path=schema_extension_path, schema_extension=schema_extension_name)


# If we don't have the path then we display warning message
if not get_schema_library_path():
    st.warning(
        """
                No `SCHEMA_LIBRARY_PATH` found in your environment variable.

                Please set the variable and reload.
        """,
        icon="⚠️",
    )
else:
    st.write(
        """You can find below a few schema we crafted at Opsmill. This will give you the
        main building blocks to kickoff your automation journey. You can decide to use one, none or all of them!"""
    )

    # First create a box for base that is mandatory
    with st.container(border=True):
        # Init vars
        schema_extension_name: str = "base"
        schema_extension_path: Path = Path(f"{st.session_state.schema_library_path}/{schema_extension_name}")
        init_schema_extension_state(schema_extension_name)

        # Render container content
        render_schema_extension_content(schema_extension_path, schema_extension_name)

    if st.session_state.extensions_states.get("base") is SchemaState.LOADED:
        # Separate base from the extensions
        st.divider()

        # Then box containing all extensions
        with st.container():
            # Init vars
            EXTENSIONS_FOLDER: str = "extensions"
            extensions_folder_path: Path = Path(f"{st.session_state.schema_library_path}/{EXTENSIONS_FOLDER}")

            # Loop over the extension directory
            for schema_extension_name in listdir(extensions_folder_path):  # TODO: Maybe review that...
                with st.container(border=True):
                    # Init vars
                    init_schema_extension_state(schema_extension_name)
                    schema_extension_path: Path = Path(f"{extensions_folder_path}/{schema_extension_name}")

                    # Each extension is packaged as a folder ...
                    if os.path.isdir(schema_extension_path):
                        # Render container content
                        render_schema_extension_content(schema_extension_path, schema_extension_name)
