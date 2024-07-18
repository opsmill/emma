import streamlit as st

from emma.infrahub import InfrahubStatus
from emma.streamlit_utils import ensure_infrahub_address_and_branch, set_page_config
from menu import menu

set_page_config(title="Home", icon=":wave:")

st.write("# Welcome to Emma! :wave:")

st.markdown(
    """
    Emma is an agent designed to help you interact with Infrahub.

    Emma will look for the **INFRAHUB_ADDRESS** environment variable to connect to your Infrahub instance.
    However, you can also set or update the address directly in the UI if needed.

    Use the sidebar to navigate between different functionalities, such as exploring data, importing data,
    generating schemas, and visualizing schemas.
    """
)

if "infrahub_address" not in st.session_state:
    st.session_state.infrahub_address = None

if "infrahub_branch" not in st.session_state:
    st.session_state.infrahub_branch = None
    st.session_state._infrahub_branch = st.session_state.infrahub_branch

ensure_infrahub_address_and_branch()
menu()
