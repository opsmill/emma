import streamlit as st

from emma.streamlit_utils import (
    add_create_branch_button,
    display_branch_selector,
    display_infrahub_address,
    display_logo,
    update_infrahub_instance_button,
)


def menu():
    if "infrahub_address" not in st.session_state or st.session_state.infrahub_address is None:
        st.sidebar.page_link("main.py", label="🏠 Homepage")
        return

    # Display Opsmill logo
    display_logo()

    with st.sidebar:
        # Display current Infrahub Instance
        display_infrahub_address(st.sidebar)
        update_infrahub_instance_button(st.sidebar)
        # Display Branch Selector
        display_branch_selector(st.sidebar)  # Always display the branch selector
        add_create_branch_button(st.sidebar)
        st.divider()

        st.page_link("main.py", label="🏠 Homepage")
        st.page_link("pages/data_exporter.py", label="🔭 Data Exporter")
        st.page_link("pages/data_importer.py", label="📥 Data Importer")
        st.page_link("pages/schema_loader.py", label="📦 Schema Loader")
        st.page_link("pages/schema_visualizer.py", label="👀 Schema Visualizer")

        with st.expander("Builders", expanded=True, icon="👷"):
            st.page_link("pages/schema_builder.py", label="🛠️ Schema Builder")
            st.page_link("pages/query_builder.py", label="🔍 Query Builder")


def menu_with_redirect():
    # Redirect users to the main page
    if "infrahub_address" not in st.session_state or st.session_state.infrahub_address is None:
        st.switch_page("main.py")

    menu()
