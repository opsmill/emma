import streamlit as st

from emma.streamlit_utils import set_page_config
from menu import menu_with_redirect

set_page_config(title="Test Page")
st.markdown("# Hello, World!")
menu_with_redirect()
