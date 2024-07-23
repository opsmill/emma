import streamlit as st

from emma.streamlit_utils import ensure_infrahub_address_and_branch, set_page_config
from menu import menu

set_page_config(title="Homepage")

# Set columns to receive content
left, right = st.columns([1, 1.6], gap="medium", vertical_alignment="center")

# Left is for Emma avatar
left.image("static/emma-assist-character.png", caption="Hello, I'm Emma")

# Right is for the text
right.write("# Welcome! :wave:")
right.markdown(
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

ensure_infrahub_address_and_branch()
menu()
