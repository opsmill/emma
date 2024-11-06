import math
import os
from itertools import islice

import streamlit as st

from emma.analyzer_utils import (
    CISCO_CONFIG_PATTERNS,
    JUNOS_CONFIG_PATHS,
    display_segments,
    extract_junos_segments,
    junos_dict_to_config,
    paginate_list,
    parse_cisco_config,
    parse_junos_config,
)
from emma.infrahub import get_client

client = get_client(branch=st.session_state.infrahub_branch)


# Helper to group items in chunks of 3
def chunked_iterable(iterable, size):
    it = iter(iterable)
    while chunk := list(islice(it, size)):
        yield chunk


# Helper to load configs safely
def load_config(hostname):
    """Load config for a hostname if not already loaded, with error check."""
    if hostname not in st.session_state.loaded_configs:
        try:
            queried_device = client.get("InfraDevice", name__value=hostname, include=["config_object_store_id"])
            config_id = getattr(queried_device, "config_object_store_id", None)
            if config_id:
                config = client.object_store.get(config_id.value)
                st.session_state.loaded_configs[hostname] = config
            else:
                st.toast(f"No config found for {hostname}")
        except Exception as e:
            st.error(f"Error loading config for {hostname}: {e}")


def select_devices_tab():  # noqa: PLR0915, PLR0912, C901
    # Platform and group selections (disabled if configs are uploaded)
    st.session_state.selected_platform = st.selectbox("Choose platform", ["iOS", "JunOS"])

    # Config upload functionality
    uploaded_files = st.file_uploader("Upload configuration files", accept_multiple_files=True)

    # If files are uploaded, disable the selectbox for device selection
    if uploaded_files:
        st.session_state.use_uploaded_configs = True
        st.session_state.selected_hostnames = []  # Clear selected hostnames if any
    else:
        st.session_state.use_uploaded_configs = False

    groups = {x["name"]: x["hosts"] for x in st.session_state.device_groups}
    st.session_state.selected_group = st.selectbox(
        "Choose a group (optional)", {None: None, **groups}, disabled=st.session_state.use_uploaded_configs
    )

    # If files are uploaded, process them directly; otherwise, proceed with device selection
    if uploaded_files:
        st.session_state.selected_hostnames = [
            os.path.splitext(file.name)[0] for file in uploaded_files
        ]  # Use filenames as hostnames
        raw_texts = [file.read().decode("utf-8") for file in uploaded_files]

        if st.session_state.selected_platform == "iOS":
            parsed_configs = [parse_cisco_config(raw_text) for raw_text in raw_texts]

        elif st.session_state.selected_platform == "JunOS":
            # Step 1: Parse raw texts into config dictionaries
            parsed_config_dicts = [parse_junos_config(raw_text) for raw_text in raw_texts]

            parsed_configs = []

            for conf in parsed_config_dicts:
                segmented_conf = {}
                for key in conf.keys():
                    if isinstance(conf[key], dict):
                        clean_conf_dict = [{"key": k, "value": v} for k, v in conf[key].items()]

                    else:
                        clean_conf_dict = [{"key": key, "value": conf[key]}]

                    lines = [f"{x['key']} {{ \n{junos_dict_to_config(x['value'], 2)}\n}}" for x in clean_conf_dict]

                    segmented_conf[key] = lines
                parsed_configs.append(segmented_conf)

            st.session_state.parsed_configs = parsed_configs

    else:
        # Get the list of hostnames
        devices = st.session_state.hostnames
        hostnames = [device.name.value for device in devices]
        page_size = 10
        total_pages = math.ceil(len(hostnames) / page_size)

        # Set initial states if not present
        st.session_state.setdefault("page", 0)
        st.session_state.setdefault("selected_hostnames", [])
        st.session_state.setdefault("loaded_configs", {})
        st.session_state.setdefault("selected_segment", None)

        # Group-based hostnames loading
        if selected := st.session_state.selected_group:
            st.session_state.selected_hostnames = groups[selected]
            for hostname in st.session_state.selected_hostnames:
                load_config(hostname)

        # Pagination logic
        current_page_hostnames = paginate_list(hostnames, page_size, st.session_state.page)
        col1, col2, col3 = st.columns([1, 2, 1])
        if col1.button("Previous Page", disabled=(st.session_state.page <= 0)):
            st.session_state.page = max(st.session_state.page - 1, 0)
        if col3.button("Next Page", disabled=(st.session_state.page >= total_pages - 1)):
            st.session_state.page = min(st.session_state.page + 1, total_pages - 1)

        # Hostname selection with config load/unload
        with st.expander("Select hostnames to process", expanded=True):
            cols = st.columns(2)
            for i, hostname in enumerate(current_page_hostnames):
                col = cols[i % 2]
                checked = hostname in st.session_state.selected_hostnames
                if col.checkbox(hostname, key=f"hostname_{hostname}", value=checked):
                    if hostname not in st.session_state.selected_hostnames:
                        st.session_state.selected_hostnames.append(hostname)
                    load_config(hostname)
                elif hostname in st.session_state.selected_hostnames:
                    st.session_state.selected_hostnames.remove(hostname)
                    st.session_state.loaded_configs.pop(hostname, None)

        # Parsing selected hostnames
        if selected_hostnames := st.session_state.selected_hostnames:
            raw_texts = [
                st.session_state.loaded_configs.get(hostname, "Failed to load config")
                for hostname in selected_hostnames
            ]

            if st.session_state.selected_platform == "iOS":
                parsed_configs = [parse_cisco_config(raw_text) for raw_text in raw_texts]

            elif st.session_state.selected_platform == "JunOS":
                print("yep")
                parsed_config_dicts = [parse_junos_config(raw_text) for raw_text in raw_texts]
                parsed_configs = [
                    {k: junos_dict_to_config(v) for k, v in extract_junos_segments(raw).items()}
                    for raw in parsed_config_dicts
                ]

            st.session_state.parsed_configs = parsed_configs

    # Segment selection and display
    st.header("Select config segments to process", divider=True)
    if st.session_state.selected_platform == "ios":
        segment_keys = CISCO_CONFIG_PATTERNS
    else:
        segment_keys = JUNOS_CONFIG_PATHS

    for chunk in chunked_iterable(segment_keys.keys(), 5):
        cols = st.columns(5, gap="small")
        for i, label in enumerate(chunk):
            with cols[i]:
                if st.button(label):
                    st.session_state.selected_segment = label
                    st.write(f"Selected segment: {label}")

    if selected := st.session_state.selected_segment:
        parsed_configs = [{selected: x.get(selected, [])} for x in st.session_state.parsed_configs]
        st.session_state.parsed_configs = parsed_configs

    if st.session_state.parsed_configs:
        display_segments(
            st.session_state.selected_hostnames, st.session_state.parsed_configs, raw=True, highlight=False
        )

    if st.sidebar.button("Clear selected hostnames"):
        st.session_state.selected_segment = None
        st.session_state.parsed_configs = []
        st.rerun()
