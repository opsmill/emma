import streamlit as st

from emma.infrahub import add_branch_selector

st.set_page_config(
    page_title="Home",
    page_icon="👋",
)

st.write("# Welcome to Emma! 👋")

add_branch_selector(st.sidebar)

st.markdown(
    """
    Emma is an agent designed to help you interact with Infrahub.
    """
)
