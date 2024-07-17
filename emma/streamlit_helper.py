from typing import Tuple

import streamlit as st
from streamlit.delta_generator import DG
from streamlit_theme import st_theme

from emma.infrahub import check_reacheability, get_branches, get_client


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


def display_branch_selector(sidebar: DG):
    branches = get_branches()
    if "infrahub_branch" not in st.session_state:
        st.session_state["infrahub_branch"] = "main"
    sidebar.selectbox(label="branch", options=branches.keys(), key="infrahub_branch")

def display_infrahub_address(sidebar: DG):
    sidebar.selectbox(
        label="Current Infrahub Address",
        options=[st.session_state.get("infrahub_address", "")],
        index=0,
        disabled=True
    )

def test_reacheability_and_display_sidebar():
    if "infrahub_address" in st.session_state and st.session_state["infrahub_address"]:
        try:
            branch = st.session_state.get("infrahub_branch", "main")
            address = st.session_state.get("infrahub_address")
            client = get_client(address=address, branch=branch)
            is_reacheable = check_reacheability(client=client)

            # If reachable, fetch schema data based on the branch
            if is_reacheable:
                display_infrahub_address(st.sidebar)
                display_branch_selector(st.sidebar)
            else:
                st.error(f"Server {address} is unreacheable.")
                display_expander(name="Detail", content=st.session_state["infrahub_error_message"])
        except ValueError as e:
            st.error(str(e))
