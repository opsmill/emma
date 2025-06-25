import streamlit as st

from emma.streamlit_utils import (
    add_create_branch_button,
    display_branch_selector,
    display_infrahub_address,
    display_logo,
    update_infrahub_instance_button,
)
from emma.utils import is_feature_enabled


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
        st.page_link("pages/schema_library.py", label="📚 Schema Library")
        # st.page_link("pages/schema_visualizer.py", label="👀 Schema Visualizer")
        # Example usage of feature flags
        if is_feature_enabled("test_page"):
            st.page_link("pages/test_page.py", label="⚠️ Test Page")

        with st.expander("AI Builders", expanded=True, icon="👷"):
            st.page_link("pages/schema_builder.py", label="🛠️ Schema Builder")
            if is_feature_enabled("alpha_builders"):
                st.page_link("pages/query_builder.py", label="🔍 Query Builder")
                st.page_link("pages/template_builder.py", label="📝 Template Builder")
                st.page_link("pages/docs_agent.py", label="📚 Docs Agent")


def menu_with_redirect():
    # Redirect users to the main page
    if "infrahub_address" not in st.session_state or st.session_state.infrahub_address is None:
        st.switch_page("main.py")

    menu()
