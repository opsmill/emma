import streamlit as st

from emma.infrahub import (  # noqa: E402
    check_reachability,
    get_client,
    get_instance_address,
    get_version,
    input_infrahub_address,
)
from emma.streamlit_helper import display_branch_selector, display_expander, display_infrahub_address

st.set_page_config(
    page_title="Home",
    page_icon="👋",
)

st.write("# Welcome to Emma! 👋")

st.markdown(
    """
    Emma is an agent designed to help you interact with Infrahub.
    """
)

# Initialize reachable status
is_reacheable = False

# Input Infrahub address via UI if not set
if not get_instance_address():
    st.info("""
            No INFRAHUB_ADDRESS found in your environment variable.

            Please set the Infrahub Address.
            """)
    input_infrahub_address()

# Check if infrahub_address is set and get the client
if "infrahub_address" in st.session_state and st.session_state["infrahub_address"]:
    try:
        branch = st.session_state.get("infrahub_branch", "main")
        address = st.session_state.get("infrahub_address")
        client = get_client(address=address, branch=branch)
        is_reacheable = check_reachability(client=client)

        # If reachable, fetch schema data based on the branch
        if is_reacheable:
            st.success(f"Server {address} is reacheable.")
            st.info(f"**Version**: {get_version(client=client)}")
            display_infrahub_address(st.sidebar)
            display_branch_selector(st.sidebar)
        else:
            st.error(f"Server {address} is unreacheable.")
            display_expander(name="Detail", content=st.session_state["infrahub_error_message"])

    except ValueError as e:
        st.error(str(e))
