import asyncio

import streamlit as st
from streamlit.delta_generator import DeltaGenerator
from streamlit.runtime.pages_manager import PagesManager
from streamlit.runtime.scriptrunner import get_script_run_ctx

from emma.infrahub import (
    check_reachability_async,
    create_branch,
    get_branches,
    get_client_async,
    get_instance_address,
    get_instance_branch,
    is_current_schema_empty,
)


def get_current_page():
    ctx = get_script_run_ctx()
    if ctx is None:
        raise RuntimeError("Couldn't get script context")

    mgr = PagesManager.get_current()  # singleton manager
    pages: dict = mgr.pages  # dict[page_hash → PageInfo]
    page_info = pages.get(ctx.page_script_hash)
    if page_info is None:
        raise RuntimeError(f"No page found for hash {ctx.page_script_hash}")
    return page_info.page_name


def set_page_config(title: str | None = None, wide: bool | None = True):
    icon = "static/emma.png"
    if wide:
        st.set_page_config(page_title=title, page_icon=icon, layout="wide")
    else:
        st.set_page_config(page_title=title, page_icon=icon)


def display_expander(name: str, content: str) -> None:
    """
    Display an expander with the given name and content.

    Parameters:
        name (str): The title of the expander.
        content (str): The content to be displayed inside the expander.
    """
    with st.expander(name):
        st.markdown(content)


def set_branch():
    # Callback function to save the branch selection to Session State
    st.session_state.infrahub_branch = st.session_state._infrahub_branch


def display_branch_selector(sidebar: DeltaGenerator):
    # st.session_state._infrahub_branch = None
    branches = get_branches(address=st.session_state.infrahub_address)
    current_branch = get_instance_branch()
    if current_branch:
        st.session_state._infrahub_branch = st.session_state.infrahub_branch
    elif "_infrahub_branch" not in st.session_state and branches:
        st.session_state._infrahub_branch = "main"
        st.session_state.infrahub_branch = "main"
    else:
        st.session_state._infrahub_branch = "Not found"
    sidebar.selectbox(
        label="Branch:",
        options=branches.keys() if branches else [st.session_state._infrahub_branch],
        key="_infrahub_branch",
        on_change=set_branch,
    )


def display_infrahub_address(sidebar: DeltaGenerator):
    sidebar.selectbox(
        label="Infrahub Address:",
        options=[st.session_state.infrahub_address],
        index=0,
        disabled=True,
    )


def input_infrahub_address():
    with st.form(key="input_address_form"):
        new_address = st.text_input(label="Enter Infrahub Address", value=st.session_state.infrahub_address)
        submit_address = st.form_submit_button(label="Submit")
        if submit_address and new_address:
            st.session_state.infrahub_address = new_address
            st.toast(f"Trying to connect to {new_address}")
            st.rerun()


def schema_bootstrap_message():
    if is_current_schema_empty():
        with st.container(border=True):
            st.info(
                """I see that your Infrahub instance is rather empty, a good first step is to create a schema.
                Click on the button below to get to the schema library and start boostraping your schema!
                """,
                icon="ℹ️",
            )
            if st.button(label="Schema Library", icon="📚", use_container_width=True, type="secondary"):
                st.switch_page("pages/schema_library.py")


def ensure_infrahub_address_and_branch():
    # Input Infrahub address via UI if not set
    if not get_instance_address():
        st.info("""
                No INFRAHUB_ADDRESS found in your environment variable.

                Please set the Infrahub Address.
        """)
        input_infrahub_address()
    # Check if infrahub_address is set and get the client
    if "infrahub_address" in st.session_state and st.session_state.infrahub_address:
        address = st.session_state.infrahub_address
        try:
            client = asyncio.run(get_client_async(address=address))
            is_reachable = asyncio.run(check_reachability_async(client=client))

            if not is_reachable:
                handle_reachability_error()
                input_infrahub_address()
                st.stop()

        except ValueError as e:
            st.session_state.infrahub_error_message = str(e)
            handle_reachability_error()
            input_infrahub_address()
            st.stop()
    else:
        st.stop()


def handle_reachability_error(redirect: bool | None = True):
    st.toast(icon="🚨", body=f"Error: {st.session_state.infrahub_error_message}")
    st.cache_data.clear()  # TODO: Maybe something less violent ?
    if not redirect:
        st.stop()
    current_page = get_current_page()
    if current_page != "main":
        st.switch_page("main.py")


@st.dialog("Set or Update Infrahub Instance")
def update_infrahub_instance_dialog():
    new_instance = st.text_input(label="Infrahub Address:", placeholder="http://infrahub-server-fqdn")
    if new_instance or st.button("Submit"):
        st.session_state.infrahub_address = new_instance
        st.rerun()


@st.dialog("Create a branch")
def create_branch_dialog():
    new_branch_name = st.text_input(label="New Branch", placeholder="new-branch-name")
    if new_branch_name or st.button("Submit"):
        create_branch(branch_name=new_branch_name)
        st.session_state.infrahub_branch = new_branch_name
        st.rerun()


def update_infrahub_instance_button(sidebar: DeltaGenerator):
    if sidebar.button("Replace Instance"):
        update_infrahub_instance_dialog()


def add_create_branch_button(sidebar: DeltaGenerator):
    if sidebar.button("Create a new branch"):
        create_branch_dialog()


def display_logo():
    st.logo(
        "static/opsmill-logo.png",
        link="https://github.com/opsmill",
        icon_image="static/opsmill-logo.png",
    )
