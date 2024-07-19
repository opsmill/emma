from typing import Tuple

import streamlit as st
from streamlit.delta_generator import DG
from streamlit_theme import st_theme

from emma.infrahub import check_reachability, create_branch, get_branches, get_client, get_instance_address


def set_page_config(title: str, icon: str | None = None, wide: bool | None = True):
    if wide:
        st.set_page_config(page_title=title, page_icon=icon, layout="wide")
    else:
        st.set_page_config(page_title=title, page_icon=icon)


def get_theme_settings() -> Tuple[str, str]:
    """
    Get theme settings for background and font color.

    Returns:
        Tuple[str, str]: Background color and font color.
    """
    theme = st_theme()
    if theme:
        return theme["backgroundColor"], theme["textColor"]
    return "#FFFFFF", "#000000"  # Default to light mode colors if not set


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


def display_branch_selector(sidebar: DG):
    branches = get_branches(address=st.session_state.infrahub_address)
    if st.session_state._infrahub_branch is None:
        st.session_state._infrahub_branch = "main"
    sidebar.selectbox(
        label="Branch:",
        options=branches.keys(),
        key="_infrahub_branch",
        on_change=set_branch,
    )


def display_infrahub_address(sidebar: DG):
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
            st.rerun()


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
        # display_infrahub_address(st.sidebar)  # Always display the Infrahub address input
        try:
            client = get_client(address=address)
            is_reachable = check_reachability(client=client)

            # If reachable, show success message and version info
            if not is_reachable:
                st.error(f"Server address {address} is unreachable or not a valid Infrahub Instance.")
                display_expander(name="Detail", content=st.session_state.infrahub_error_message)
                input_infrahub_address()
                st.stop()

        except ValueError as e:
            st.error(f"Inputed address {address} is not valid.")
            display_expander(name="Detail", content=str(e))
            input_infrahub_address()
            st.stop()
    else:
        st.stop()


@st.experimental_dialog("Set or Update Infrahub Instance")
def update_infrahub_instance_dialog():
    new_instance = st.text_input("Infrahub Address...")
    if st.button("Submit"):
        st.session_state["infrahub_address"] = new_instance
        st.rerun()


@st.experimental_dialog("Create a branch")
def create_branch_dialog():
    new_branch_name = st.text_input("Branch name...")
    if st.button("Submit"):
        # Here create branch in infrahub
        create_branch(new_branch_name)
        st.session_state["infrahub_branch"] = new_branch_name
        st.rerun()


# def add_branch_selector(sidebar: DG):
#     branches = get_branches()
#     if "infrahub_branch" not in st.session_state:
#         st.session_state["infrahub_branch"] = "main"
#     sidebar.selectbox(label="branch", options=branches.keys(), key="infrahub_branch")


# def add_infrahub_address(sidebar: DG):
#     if "infrahub_address" not in st.session_state:
#         st.session_state["infrahub_address"] = os.environ.get("INFRAHUB_ADDRESS")
#     sidebar.markdown(f"Infrahub address: :blue-background[{st.session_state["infrahub_address"]}]")


def update_infrahub_instance_button(sidebar: DG):
    if sidebar.button("Replace Instance"):
        update_infrahub_instance_dialog()


def add_create_branch_button(sidebar: DG):
    if sidebar.button("Create a new branch"):
        create_branch_dialog()
