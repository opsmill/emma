import asyncio

import streamlit as st
from infrahub_sdk import InfrahubNode

from emma.gql_queries import dict_to_gql_query, exclude_keys
from emma.infrahub import run_gql_query, get_client

infrahub_client = get_client(branch=st.session_state.infrahub_branch)


def select_schema_tab():
    excluded_namespaces = (
        "Core",
        "Account",
        "Nested",
        "Edged",
        "Builtin",
        "Lineage",
        "Organization",
        "Profile",
        "Branch",
        "Diff",
        "Infrahub",
    )

    # Get all possible options for search
    options = [x for x in st.session_state.schema.keys() if not x.startswith(excluded_namespaces)]

    # Set up pagination
    if "page" not in st.session_state:
        st.session_state.page = 0

    if "selected" not in st.session_state:
        st.session_state.selected = None

    # Number of results per page
    results_per_page = 6

    def reset_page():
        st.session_state.page = 0

    # Search input with auto-update
    search_query = st.text_input("What schema should we use?", on_change=reset_page)

    # Filter function
    if search_query:
        filtered_data = [item for item in options if search_query.lower() in item.lower()]
    else:
        filtered_data = options

    if not filtered_data:
        st.write("Nothing found...")

    else:
        # Pagination logic
        total_pages = (len(filtered_data) - 1) // results_per_page + 1

        start_idx = st.session_state.page * results_per_page
        end_idx = start_idx + results_per_page
        paginated_data = filtered_data[start_idx:end_idx]

        # Show the filtered results as buttons

        cols = st.columns(min(results_per_page, len(filtered_data)), gap="medium", vertical_alignment="center")

        for i, item in enumerate(paginated_data):
            with cols[i]:
                if st.button(item):
                    st.session_state.selected_schema = item
                    st.write(f"Selected schema: {item}")

        # Pagination controls with colored buttons in columns
        col1, _, col3 = st.columns([1, 5, 1], gap="large")

        with col1:
            if st.session_state.page > 0:
                if st.button("Back"):
                    st.session_state.page -= 1

        with col3:
            if st.session_state.page < total_pages - 1:
                if st.button("More"):
                    st.session_state.page += 1

    if selected := st.session_state.selected_schema:
        st.divider()

        st.session_state.schema_node = InfrahubNode(
            client=infrahub_client, schema=st.session_state.schema[selected], branch=st.session_state.infrahub_branch
        )

        full_query = exclude_keys(asyncio.run(st.session_state.schema_node.generate_query_data()))

        col1, col2 = st.columns(2)

        formatted_query = f"{{\n{dict_to_gql_query(full_query)}\n}}"

        with col1:
            st.header("Query")
            st.markdown(f"```gql\n\n{formatted_query}\n```")

        st.session_state.pulled_data = run_gql_query(formatted_query)

        with col2:
            st.header("Existing Data")
            st.write(st.session_state.pulled_data)
            # st.markdown(display_query_and_data(formatted_query, data), unsafe_allow_html=True)
