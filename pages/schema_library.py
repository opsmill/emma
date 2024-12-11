from enum import Enum
from typing import Any

import streamlit as st

from emma.github import (
    get_readme,
    get_schema_library_path,
    load_schemas_from_github,
)
from emma.infrahub import (
    get_schema,
    load_schema,
)
from emma.streamlit_utils import set_page_config
from menu import menu_with_redirect

set_page_config(title="Schema Library")
st.markdown("# Schema Library")
menu_with_redirect()

# Load the schema paths to be used for loading schemas
SCHEMAS = {
    "base",
    "experimental",
    "extensions",
}


class SchemaState(str, Enum):
    NOT_LOADED = "NOT_LOADED"
    LOADING = "LOADING"
    LOADED = "LOADED"


if "extensions_states" not in st.session_state:
    st.session_state.extensions_states = {}


def init_schema_extension_state(schema_extension: str) -> None:
    # Check if the extension is already in the session state
    if schema_extension not in st.session_state.extensions_states:
        # FIXME: This is beyond hacking, but I need to define whether base extension is in place or not
        if schema_extension == "base":
            schema: dict[str, Any] | None = get_schema()
            if schema is not None and "DcimDevice" in schema.items():
                st.session_state.extensions_states["base"] = SchemaState.LOADED
        else:
            # TODO: Here we need to evaluate if it's already existing in Infrahub ... somehow
            # So if it's the case we could put the proper LOADED state
            st.session_state.extensions_states[schema_extension] = SchemaState.NOT_LOADED


# Function that checks if a readme exists in a given folder and return the content if so
def check_and_open_readme(path: str) -> str:
    content = get_readme(path)

    return content if content else ""


def schema_loading_container(schema_extension: str) -> None:
    with st.status(f"Loading schema extension `{schema_extension}` ...", expanded=True) as loading_container:
        # Get schema content
        st.write("Opening schema file...")
        schema_content: list[dict[Any, Any]] = load_schemas_from_github(name=schema_extension)
        st.write("Schema file loaded!")

        # Place request
        st.write("Calling Infrahub API...")
        response = load_schema(
            branch=st.session_state.infrahub_branch,
            schemas=schema_content,
        )

        st.write("Computing results...")

        # Process the response
        if response:
            if response.errors:
                loading_container.update(label="❌ Load failed ...", state="error", expanded=True)
                loading_container.error("Infrahub doesn't like it!", icon="🚨")
                loading_container.exception(response.errors)
            else:
                loading_container.update(label="✅ Schema loaded!", state="complete", expanded=True)
                st.session_state.extensions_states[schema_extension] = SchemaState.LOADED

                if response.schema_updated:
                    st.write("Schema loaded successfully!")
                    st.write("Generating balloons...")
                    st.balloons()  # 🎉
                else:
                    loading_container.info(
                        "The schema in Infrahub was already up to date, no changes were required!",
                        icon="ℹ️",
                    )


def on_click_schema_load(schema_extension: str):
    st.session_state.extensions_states[schema_extension] = SchemaState.LOADING


def render_schema_extension_content(schema_name: str) -> None:
    # Render description for the extension
    st.write(check_and_open_readme(schema_name))

    # Prepare vars for the button
    is_button_disabled: bool = False
    button_label: str = "🚀 Load to Infrahub"
    if st.session_state.extensions_states.get(schema_name) == SchemaState.LOADING:
        is_button_disabled = True
        button_label = "🚀 Load to Infrahub"
    elif st.session_state.extensions_states.get(schema_name) == SchemaState.LOADED:
        is_button_disabled = True
        button_label = "✅ Already in Infrahub"

    # Render the button
    st.button(
        label=button_label,
        type="secondary",
        use_container_width=True,
        key=schema_name,
        disabled=is_button_disabled,
        on_click=on_click_schema_load,
        args=(schema_name,),
    )

    # Render loading container if needed
    if st.session_state.extensions_states.get(schema_name) == SchemaState.LOADING:
        schema_loading_container(schema_name)


st.write(
    """You can find below a few schema we crafted at Opsmill. This will give you the
    main building blocks to kickoff your automation journey. You can decide to use one, none or all of them!"""
)

# First create a box for base that is mandatory
with st.container(border=True):
    # Render container content
    schema_base_name = "base"
    render_schema_extension_content(schema_base_name)

    if st.session_state.extensions_states.get("base") == SchemaState.LOADED:
        # Separate base from the extensions
        st.divider()

        # Then box containing all extensions
        with st.container():
            # Loop over the extension directory
            for schema_extension_name in get_schema_library_path("extensions"):
                with st.container(border=True):
                    init_schema_extension_state(schema_extension_name.name)

                    render_schema_extension_content(schema_extension_name.path)
