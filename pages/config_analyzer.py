import streamlit as st

import os

import emma.analyzer_components as ac

from emma.infrahub import get_client
from menu import menu_with_redirect

menu_with_redirect()

infrahub_client = get_client(branch=st.session_state.infrahub_branch)

# Streamlit app starts here
st.title("View and Compare Network Configurations")

# Initialize session state for storing filenames and configs
if "filenames" not in st.session_state:
    st.session_state.filenames = []
if "configs" not in st.session_state:
    st.session_state.configs = []
if "regexes" not in st.session_state:
    st.session_state.regexes = {}
if "parsed_configs" not in st.session_state:
    st.session_state.parsed_configs = []
if "templates" not in st.session_state:
    st.session_state.templates = {}
if "extracted_data" not in st.session_state:
    st.session_state.extracted_data = {}
if "pulled_data" not in st.session_state:
    st.session_state.pulled_data = {}
if "gql_query" not in st.session_state:
    st.session_state.gql_query = {}
if "selected_segment" not in st.session_state:
    st.session_state.selected_segment = None
if "selected_schema" not in st.session_state:
    st.session_state.selected_schema = None
if "validation_errors" not in st.session_state:
    st.session_state.validation_errors = []
if "data_to_upload" not in st.session_state:
    st.session_state.data_to_upload = {}
if "selected_hostnames" not in st.session_state:
    st.session_state.selected_hostnames = []
if "schema_node" not in st.session_state:
    st.session_state.schema_node = None
if "formatted_query" not in st.session_state:
    st.session_state.formatted_query = ""
if "loaded_configs" not in st.session_state:
    st.session_state.loaded_configs = {}
    # Walk through the directory and grab the files
    # configs = {}
    # for dirpath, _, filenames in os.walk("test_data"):
    #     for filename in filenames:
    #         if filename.endswith(".conf"):
    #             device_name = filename.replace(".conf", "").replace(".", "-")

    #             with open(os.path.join(dirpath, filename)) as f:
    #                 configs[device_name] = f.read()
    # st.session_state.loaded_configs = configs

    # st.session_state.loaded_configs = configs
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
