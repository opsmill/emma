import asyncio

import streamlit as st

from infrahub_sdk import InfrahubNode

from emma.infrahub import get_client, run_gql_query

from emma.gql_queries import exclude_keys, dict_to_gql_query

infrahub_client = get_client()


def view_data_tab():
    if selected := st.session_state.selected_schema:
        for hostname in st.session_state.selected_hostnames:
            st.header(hostname, divider=True)
            st.session_state.schema_node = InfrahubNode(
                client=infrahub_client,
                schema=st.session_state.schema[selected],
                branch=st.session_state.infrahub_branch,
            )

            full_query = exclude_keys(
                asyncio.run(
                    st.session_state.schema_node.generate_query_data(filters={"in_config__name__value": hostname})
                )
            )

            col1, col2 = st.columns(2)

            formatted_query = f"{{\n{dict_to_gql_query(full_query)}\n}}"

            with col1:
                st.header("Query")
                st.markdown(f"```gql\n\n{formatted_query}\n```")

            st.session_state.pulled_data = run_gql_query(formatted_query)

            with col2:
                st.header("Data")
                st.write(st.session_state.pulled_data)
