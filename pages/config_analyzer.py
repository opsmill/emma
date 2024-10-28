
import streamlit as st

import emma.analyzer_components as ac
from emma.analyzer_utils import GROUP_QUERY
from emma.infrahub import get_client, run_gql_query
from menu import menu_with_redirect

menu_with_redirect()

infrahub_client = get_client(branch=st.session_state.infrahub_branch)

# Streamlit app starts here
st.title("View and Compare Network Configurations")

# Initialize session state for storing filenames and configs
st.session_state.setdefault("filenames", [])
st.session_state.setdefault("configs", [])
st.session_state.setdefault("regexes", {})
st.session_state.setdefault("parsed_configs", [])
st.session_state.setdefault("templates", {})
st.session_state.setdefault("extracted_data", {})
st.session_state.setdefault("pulled_data", {})
st.session_state.setdefault("gql_query", {})
st.session_state.setdefault("selected_segment", None)
st.session_state.setdefault("selected_schema", None)
st.session_state.setdefault("validation_errors", [])
st.session_state.setdefault("data_to_upload", {})
st.session_state.setdefault("selected_hostnames", [])
st.session_state.setdefault("schema_node", None)
st.session_state.setdefault("formatted_query", "")

if "device_groups" not in st.session_state:
    device_groups = []

    groups = run_gql_query(GROUP_QUERY)

    for group in groups["CoreStandardGroup"]["edges"]:
        members = [x["node"] for x in group["node"]["members"]["edges"]]
        if all(x["__typename"] == "InfraDevice" for x in members):
            device_groups.append(
                {"name": group["node"]["display_label"], "hosts": [x["display_label"] for x in members]}
            )

    st.session_state.device_groups = device_groups

if "loaded_configs" not in st.session_state:
    st.session_state.loaded_configs = {}

if "hostnames" not in st.session_state:
    st.session_state.hostnames = infrahub_client.all(kind="InfraDevice")

# Fetch the schema if not already in session state
if "schema" not in st.session_state:
    with st.spinner("Loading Schema"):
        st.session_state.schema = infrahub_client.schema.all()

# Create main tabs for file upload, schema editing, and advanced options
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    ["Select Devices", "Select Schema", "Extract Data", "Upload Data", "View Data", "Generate Template", "Update Repo"]
)

with tab1:
    ac.select_devices_tab()

with tab2:
    ac.select_schema_tab()

with tab3:
    ac.extra_data_tab()

with tab4:
    ac.upload_data_tab()

with tab5:
    ac.view_data_tab()

with tab6:
    ac.generate_template_tab()

with tab7:
    ac.update_repo_tab()
