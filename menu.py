import streamlit as st

from emma.streamlit_utils import (
    add_create_branch_button,
    display_branch_selector,
    display_infrahub_address,
    update_infrahub_instance_button,
)


def menu():
    if "infrahub_address" not in st.session_state or st.session_state.infrahub_address is None:
        st.sidebar.page_link("main.py", label="🏠 Homepage")
        return
    # Display current Infrahub Instance
    display_infrahub_address(st.sidebar)
    update_infrahub_instance_button(st.sidebar)
    # Display Branch Selector
    display_branch_selector(st.sidebar)  # Always display the branch selector
    add_create_branch_button(st.sidebar)
    st.sidebar.divider()
    # Pages Goes there
    st.sidebar.page_link("main.py", label="🏠 Homepage")
    st.sidebar.page_link("pages/data_exporter.py", label="🔭 Data Exporter")
    st.sidebar.page_link("pages/data_importer.py", label="📥 Data Importer")
    st.sidebar.page_link("pages/schema_loader.py", label="📦 Schema Loader")
    st.sidebar.page_link("pages/schema_builder.py", label="👷 Schema Builder")
    st.sidebar.page_link("pages/schema_visualizer.py", label="👀 Schema Visualizer")
    st.sidebar.divider()


def menu_with_redirect():
    # Redirect users to the main page
    if "infrahub_address" not in st.session_state or st.session_state.infrahub_address is None:
        st.switch_page("main.py")
    menu()
