import asyncio

import streamlit as st
from infrahub_sdk import InfrahubNode

from emma.gql_queries import dict_to_gql_query, exclude_keys
from emma.infrahub import get_client, run_gql_query

infrahub_client = get_client(branch=st.session_state.infrahub_branch)


def select_schema_tab():  # noqa: PLR0915, PLR0912
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

    if "selected_schemas" not in st.session_state:
        st.session_state.selected_schemas = []

    # Number of results per page
    results_per_page = 6

    def reset_page():
        st.session_state.page = 0

    # Search input with auto-update
    search_query = st.text_input("What schema(s) should we use?", on_change=reset_page)

    # Filter function
    filtered_data = [item for item in options if search_query.lower() in item.lower()] if search_query else options

    if not filtered_data:
        st.write("Nothing found...")
    else:
        # Pagination logic
        total_pages = (len(filtered_data) - 1) // results_per_page + 1
        start_idx = st.session_state.page * results_per_page
        end_idx = start_idx + results_per_page
        paginated_data = filtered_data[start_idx:end_idx]

        # Show the filtered results as checkboxes with a green check if selected
        cols = st.columns(min(results_per_page, len(filtered_data)))

        for i, item in enumerate(paginated_data):
            with cols[i]:
                selected = st.checkbox(f"{item} ✅" if item in st.session_state.selected_schemas else item)
                if selected and item not in st.session_state.selected_schemas:
                    st.session_state.selected_schemas.append(item)
                # elif not selected and item in st.session_state.selected_schemas:
                #     st.session_state.selected_schemas.remove(item)

        # Pagination controls
        col1, _, col3 = st.columns([1, 5, 1], gap="large")

        with col1:
            if st.session_state.page > 0 and st.button("Back"):
                st.session_state.page -= 1

        with col3:
            if st.session_state.page < total_pages - 1 and st.button("More"):
                st.session_state.page += 1

    # If schemas are selected, proceed with query generation
    if st.session_state.selected_schemas:
        st.divider()
        all_queries = []
        for selected in st.session_state.selected_schemas:
            st.session_state.schema_node = InfrahubNode(
                client=infrahub_client,
                schema=st.session_state.schema[selected],
                branch=st.session_state.infrahub_branch,
            )

            if not hasattr(st.session_state.schema_node, "in_config"):
                st.error(
                    f"Schema '{selected}' must have an 'in_config' relationship with InfraDevice to capture the relationship with selected devices."
                )
            else:
                full_query = exclude_keys(asyncio.run(st.session_state.schema_node.generate_query_data()))
                formatted_query = f"{{\n{dict_to_gql_query(full_query)}\n}}"
                all_queries.append(formatted_query)

        # Display all queries and attempt to fetch data for each schema
        st.header("Queries")
        for query, schema_name in zip(all_queries, st.session_state.selected_schemas):
            st.subheader(f"Schema: {schema_name}")
            st.markdown(f"```gql\n\n{query}\n```")

            # Run query and display data
            try:
                pulled_data = run_gql_query(query)
                st.write(pulled_data)
            except Exception as e:
                st.write(f"Error querying data for {schema_name}: {e}")
