import streamlit as st
from emma.analyzer_utils import paginate_list, CONFIG_PATTERNS, parse_cisco_config, display_segments

from emma.infrahub import get_client
import math

client = get_client(branch=st.session_state.infrahub_branch)

def select_devices_tab():
    devices = st.session_state.hostnames

    configs = st.session_state.loaded_configs

    # Get the list of hostnames
    hostnames = [device.name.value for device in devices]  # Assuming 'name' is a key in the device object

    # Number of hosts to display per page
    page_size = 10
    total_pages = math.ceil(len(hostnames) / page_size)

    # Create a state variable for the current page
    if "page" not in st.session_state:
        st.session_state.page = 0

    # Display pagination controls
    col1, col2, col3 = st.columns([1, 2, 1])
    if col1.button("Previous Page", disabled=st.session_state.page == 0):
        st.session_state.page -= 1
    if col3.button("Next Page", disabled=st.session_state.page == total_pages - 1):
        st.session_state.page += 1

    # Paginate the list of hostnames
    current_page_hostnames = paginate_list(hostnames, page_size, st.session_state.page)

    with st.expander("Select hostnames to process", expanded=True):
        cols = st.columns(2)  # Adjust columns as needed
        for i, hostname in enumerate(current_page_hostnames):
            col = cols[i % 2]  # Alternate between columns
            if col.checkbox(hostname, key=f"hostname_{hostname}"):
                if hostname not in st.session_state.selected_hostnames:
                    queried_device = client.get("InfraDevice", name__value = hostname, include=["config_object_store_id"])

                    if hasattr(queried_device, "object_store_id"):
                        config = client.object_store.get(queried_device.config_object_store_id.value)

                        st.session_state.selected_hostnames.append(hostname)

                        st.session_state.loaded_configs[hostname] = config
                    else:
                        st.toast(f"Hmm, no config found in the object store for {hostname}")

    if selected_hostnames := st.session_state.selected_hostnames:
        # Process configs for selected hostnames
        raw_texts = [configs[hostname] for hostname in selected_hostnames]
        parsed_configs = [{k: v for k, v in parse_cisco_config(raw_text).items() if v} for raw_text in raw_texts]

        st.session_state.parsed_configs = parsed_configs  # Store the parsed configs

        st.header("Select config segments to process", divider=True)

        # Segment selection
        segment_cols = st.columns(len(CONFIG_PATTERNS), gap="small")

        for i, item in enumerate(segment_cols):
            with item:
                label = [*CONFIG_PATTERNS.keys()][i]
                if st.button(label):
                    st.session_state.selected_segment = label
                    st.write(f"Selected segment: {label}")

        # If a segment is selected, filter the parsed config to only include the selected segment
        if selected := st.session_state.selected_segment:
            parsed_configs = [{selected: x.get(selected, [])} for x in st.session_state.parsed_configs]
            st.session_state.parsed_configs = parsed_configs

        # Display the segments and parsed config for the selected hostnames
        display_segments(selected_hostnames, parsed_configs, raw=True, highlight=False)

    # Option to clear the selected hostnames
    if st.sidebar.button("Clear selected hostnames"):
        st.session_state.selected_segment = None
        st.session_state.parsed_configs = []
        st.rerun()
