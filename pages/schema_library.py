import asyncio
import os
import re
from datetime import datetime
from enum import Enum
from itertools import chain
from pathlib import Path
from typing import Any

import pytz
import streamlit as st
from infrahub_sdk.yaml import SchemaFile

from emma.git_utils import SCHEMA_LIBRARY_REFRESH_INTERVAL, get_repo
from emma.infrahub import (
    get_schema_async,
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

if "schema_kinds" not in st.session_state:
    st.session_state.schema_kinds = {}

# Setup repo related session state
if "repo" not in st.session_state:
    st.session_state.repo = {
        "local_path": None,
        "last_pull": None,
        "exists": False,
    }

# Determine if the repo currently exists
if not st.session_state.repo["local_path"]:
    _local_path = Path(os.getenv("SCHEMA_LIBRARY_PATH", Path(__file__).parent.parent / "schema-library"))
    if _local_path.exists():
        st.session_state.repo["exists"] = True
        if not st.session_state.repo["last_pull"]:
            st.session_state.repo["last_pull"] = datetime.now(pytz.UTC)
    # Set local path regardless of existence
    st.session_state.repo["local_path"] = _local_path


async def init_schema_extension_state(schema_extension: str) -> None:
    # Check if the extension is already in the session state
    if schema_extension not in st.session_state.extensions_states:
        st.session_state.extensions_states[schema_extension] = SchemaState.NOT_LOADED

    schema_kinds = st.session_state.schema_kinds.get(schema_extension)
    # TODO: This accounts for qinq that only has a schema extension and no schema kinds. We need to account for node extensions here as well.
    if not schema_kinds:
        return
    existing_schemas = await get_schema_async(refresh=True)
    if schema_kinds.issubset(existing_schemas):
        st.session_state.extensions_states[schema_extension] = SchemaState.LOADED


# Function that checks if a readme exists in a given folder and return the content if so
def check_and_open_readme(path: Path) -> str:
    readme_path: Path = Path(f"{path}/README.md")
    content: str = f"No `README.md` in '{path}'..."

    # Check if the file exists
    if readme_path.exists() and readme_path.is_file() and readme_path.suffix == ".md":
        # Open the file in read mode
        with open(readme_path, encoding="utf8") as readme_file:
            # Read the content of the file
            content = readme_file.read()

    # Return result
    return content


def schema_loading_container(
    schema_files: list[SchemaFile],
    schema_extension: str,
) -> None:
    with st.status(f"Loading schema extension `{schema_extension}` ...", expanded=True) as loading_container:
        # Place request
        st.write("Calling Infrahub API...")
        response = load_schema(
            branch=st.session_state.infrahub_branch,
            schemas=[item.content for item in schema_files],
        )

        st.write("Computing results...")

        # Process the response
        if response:
            if response.errors:
                loading_container.update(label="❌ Load failed ...", state="error", expanded=True)
                loading_container.error("Infrahub doesn't like it!", icon="🚨")
                if "Unable to find" in response.errors["errors"][0]["message"]:
                    loading_container.error(
                        "You might be missing schema dependencies. Please load the schemas' dependencies first!",
                        icon="🔍",
                    )
                loading_container.error(response.errors["errors"][0]["message"])
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


def render_schema_extension_content(schema_path: Path, schema_name: str, schema_files: list[SchemaFile]) -> None:
    # Render description for the extension
    readme = check_and_open_readme(schema_path)
    # Regex pattern to capture everything before and after ## Overview
    pattern = re.compile(r"([\s\S]*?)(^## Overview[\s\S]*)", re.MULTILINE)
    # Find matches
    match = pattern.match(readme)
    if match:
        before_overview = match.group(1)
        st.markdown(before_overview)
        overview_and_below = match.group(2)
        with st.expander("More details..."):
            st.markdown(overview_and_below)
    else:
        # This is encountered if there is no "## Overview" in the README (qinq README as an example)
        st.markdown(readme)

    # Prepare vars for the button
    is_button_disabled: bool = False
    button_label: str = "🚀 Load to Infrahub"
    if st.session_state.extensions_states[schema_name] == SchemaState.LOADING:
        is_button_disabled = True
        button_label = "🚀 Loading schema into Infrahub"
    elif st.session_state.extensions_states[schema_name] == SchemaState.LOADED:
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
    if st.session_state.extensions_states[schema_name] == SchemaState.LOADING:
        schema_loading_container(schema_files=schema_files, schema_extension=schema_name)


def register_schema_kinds(schema_extension: str, schemas: list[Any]) -> None:
    """Add schema kinds to session state to determine if they are already loaded.

    Args:
        schema_extension (str): The schema extension name.
        schemas (list[Any]): The list of schemas to register.
    """
    for schema in schemas:
        if schema_extension not in st.session_state.schema_kinds:
            st.session_state.schema_kinds[schema_extension] = set()

        schema_types = chain(schema.content.get("nodes", []), schema.content.get("generics", []))
        for node in schema_types:
            schema_kind = f"{node['namespace']}{node['name']}"
            if schema_kind not in st.session_state.schema_kinds[schema_extension]:
                st.session_state.schema_kinds[schema_extension].add(schema_kind)


# Perform repo related actions of either cloning or pulling
if not st.session_state.repo["exists"]:
    st.write(f"Cloning `Schema Library` into `{st.session_state.repo['local_path']}` ...")
    repo = get_repo()
elif (
    st.session_state.repo["last_pull"]
    and datetime.now(pytz.UTC) - st.session_state.repo["last_pull"] > SCHEMA_LIBRARY_REFRESH_INTERVAL
):
    st.write("Pulling latest changes from `Schema Library` ...")
    # Attempt to pull latest changes (there may not be any, but refreshing per interval)
    repo = get_repo()
    repo.remotes.origin.pull()
    st.session_state.repo["last_pull"] = datetime.now(pytz.UTC)

st.write(
    """You can find below a few schema we crafted at Opsmill. This will give you the
    main building blocks to kickoff your automation journey. You can decide to use one, none or all of them!"""
)

# First create a box for base that is mandatory
with st.container(border=True):
    # Init vars
    schema_base_name: str = "base"
    schema_base_path: Path = Path(f"{st.session_state.repo['local_path']}/{schema_base_name}")
    base_schemas = load_schemas_from_disk(schemas=[schema_base_path])
    # Registering base schema kinds
    register_schema_kinds(schema_extension=schema_base_path.name, schemas=base_schemas)
    asyncio.run(init_schema_extension_state(schema_base_name))

    # Render container content
    render_schema_extension_content(schema_base_path, schema_base_name, base_schemas)

with st.container(border=True):
    st.write("# Extensions")
    if st.session_state.extensions_states["base"] == SchemaState.LOADED:
        # Separate base from the extensions
        st.divider()

        # Then box containing all extensions
        with st.container():
            # Init vars
            EXTENSIONS_FOLDER: str = "extensions"
            extensions_folder_path: Path = Path(f"{st.session_state.repo['local_path']}/{EXTENSIONS_FOLDER}")

            # Loop over the extension directory
            for schema_extension_path in extensions_folder_path.iterdir():  # TODO: Maybe review that...
                with st.container(border=True):
                    # Init vars
                    # schema_extension_path: Path = Path(f"{extensions_folder_path}/{schema_extension_name}")
                    extension_schemas = load_schemas_from_disk(schemas=[schema_extension_path])
                    register_schema_kinds(schema_extension=schema_extension_path.name, schemas=extension_schemas)
                    asyncio.run(init_schema_extension_state(schema_extension_path.name))

                    # Each extension is packaged as a folder ...
                    if os.path.isdir(schema_extension_path):
                        # Render container content
                        render_schema_extension_content(
                            schema_extension_path, schema_extension_path.name, extension_schemas
                        )
