import asyncio
import math

# from streamlit_ace import st_ace
# from graphql import parse, print_ast
import pandas as pd
import streamlit as st
from infrahub_sdk import InfrahubNode
from pulse.tasks.generate_jinja2.task import GenerateJinja2Task

import os

from emma.analyzer_utils import (
    CONFIG_PATTERNS,
    display_segments,
    generate_data_regex,
    parse_cisco_config,
    validate_if_df_is_compatible_with_schema,
    upload_data,
    paginate_list,
    find_matches_with_locations
)
from emma.gql_queries import dict_to_gql_query, exclude_keys  # , generate_query, get_gql_schema
from emma.infrahub import get_json_schema, run_gql_query, get_client
from emma.streamlit_utils import set_page_config
from menu import menu_with_redirect

set_page_config("Config Analyzer")

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
if "loaded_configs" not in st.session_state:
    # Walk through the directory and grab the files
    configs = {}
    for dirpath, _, filenames in os.walk("test_data"):
        for filename in filenames:
            if filename.endswith(".conf"):
                device_name = filename.replace(".conf", "").replace(".", "-")

                with open(os.path.join(dirpath, filename)) as f:
                    configs[device_name] = f.read()
    
    st.session_state.loaded_configs = configs
if "hostnames" not in st.session_state:
    st.session_state.hostnames = infrahub_client.all(kind="InfraDevice")

# Fetch the schema if not already in session state
if "schema" not in st.session_state:
    with st.spinner("Loading Schema"):
        st.session_state.schema = infrahub_client.schema.all()

# Create main tabs for file upload, schema editing, and advanced options
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["Upload Configs", "Select Schema", "Extract Data", "Upload Data", "View Data", "Generate Template"]
)

with tab1:
    devices = st.session_state.hostnames

    configs = st.session_state.loaded_configs

    # Get the list of hostnames
    hostnames = [device.name.value for device in devices]  # Assuming 'name' is a key in the device object
    
    # Number of hosts to display per page
    page_size = 10
    total_pages = math.ceil(len(hostnames) / page_size)
    
    # Create a state variable for the current page
    if 'page' not in st.session_state:
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
            if col.checkbox(hostname, key=f'hostname_{hostname}'):
                 if hostname not in st.session_state.selected_hostnames:
                     st.session_state.selected_hostnames.append(hostname)

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

with tab2:
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


with tab3:
    if selected := st.session_state.selected_schema:
        st.write(f"Extracting data for {selected}")

        data = [
            "\n".join(x[st.session_state.selected_segment])
            for x in st.session_state.parsed_configs
            if x[st.session_state.selected_segment]
        ]

        prompt, reg = generate_data_regex(get_json_schema(selected), data)

        with st.expander("Prompt"):
            st.write(prompt)

        with st.expander("Generated Regex"):
            st.write(reg)

        display_segments(
            st.session_state.selected_hostnames, st.session_state.parsed_configs, reg, raw=False
        )

    else:
        st.write("Select a schema first.")


with tab4:
    with st.expander("Raw Extracted"):
        st.write(st.session_state.extracted_data)
    
    if not st.session_state.data_to_upload:
        print("defaulting")

        st.session_state.data_to_upload = {device: pd.DataFrame(data[st.session_state.selected_segment])
                                        for device, data in st.session_state.extracted_data.items()}

    if selected_schema := st.session_state.selected_schema:
        # Get all enum columns from the schema
        enum_columns = {
            attr.name: [choice["name"] for choice in attr.choices if choice["name"] is not None]
            for attr in st.session_state.schema[selected_schema].attributes
            if attr.choices
        }

        st.write(enum_columns)

        # Create a selectbox to choose which enum column to apply a default to
        selected_enum_column = st.selectbox("Choose enum column to apply default:", options=enum_columns.keys())

        if selected_enum_column:
            # Dropdown to choose a default value for the selected enum column
            selected_default_value = st.selectbox(
                f"Choose default value for {selected_enum_column}:", options=enum_columns[selected_enum_column]
            )

            # Button to apply the default to all devices at the dictionary level
            if st.button(f"Apply default '{selected_default_value}' to {selected_enum_column}"):
                # Apply the selected default value to all devices in the raw data
                for device, data in st.session_state.extracted_data.items():
                    # Ensure the column exists in the dict data and apply the default if None
                    for row in data[st.session_state.selected_segment]:
                        if selected_enum_column not in row or row[selected_enum_column] is None:
                            row[selected_enum_column] = selected_default_value

                # Now that we've modified the raw data, reset data_to_upload with the updated data
                st.session_state.data_to_upload = {device: pd.DataFrame(data[st.session_state.selected_segment])
                                                for device, data in st.session_state.extracted_data.items()}

                st.success(f"Applied default value '{selected_default_value}' to '{selected_enum_column}' across all devices.")

        for device, data in st.session_state.data_to_upload.items():
            # If 'data' is a dict, convert it to a DataFrame first
            if isinstance(data, dict):
                df = pd.DataFrame(data[st.session_state.selected_segment])
            else:
                df = data  # If it's already a DataFrame, keep it

            # Get the columns defined in the schema
            schema_columns = (
                st.session_state.schema[selected_schema].mandatory_input_names +
                st.session_state.schema[selected_schema].attribute_names
            )

            # Ensure that all schema columns are present in the DataFrame
            for col in schema_columns:
                if col not in df.columns:
                    df[col] = pd.NA  # Add missing columns with empty (NaN) values

            # Setup column configurations for attributes that have choices (enums)
            column_config = {}
            for attr in st.session_state.schema[selected_schema].attributes:
                if attr.choices:
                    # Map the 'name' field from the choices to display in the dropdown
                    options = [choice["name"] for choice in attr.choices if choice["name"] is not None]
                    column_config[attr.name] = st.column_config.SelectboxColumn(
                        options=options,
                        label=f"{attr.name.capitalize()} (Select one)"
                    )

            # Validate the data against the schema
            validation_errors = validate_if_df_is_compatible_with_schema(
                df=df, target_schema=st.session_state.schema[selected_schema], schema=selected_schema
            )

            # Display the device name and data editor with enums in the config
            st.header(device)
            
            # Capture the updated DataFrame from data_editor to sync with applied default values
            st.session_state.data_to_upload[device] = st.data_editor(
                df, key=f"{device}-editor", column_config=column_config
            )

            # Display validation errors if any
            if validation_errors:
                for error in validation_errors:
                    if error.severity == "error":
                        st.error(error.message)
                    elif error.severity == "warning":
                        st.warning(error.message)
            else:
                st.success("No validation errors!")


        # Handle data upload on button click
        if st.button("Upload Data"):
            nbr_errors = 0  # Track total errors across all devices
            branch = st.session_state.infrahub_branch  # Get the current branch from session state

            for device, df in st.session_state.data_to_upload.items():
                # Call the existing upload_data function for each device's DataFrame
                device_errors = upload_data(df=df, schema_kind=st.session_state.selected_schema, hostname=device, branch=branch)
                nbr_errors += device_errors  # Accumulate errors

                if device_errors > 0:
                    st.error(f"Upload for {device} completed with {device_errors} errors.")
                else:
                    st.success(f"Data for {device} uploaded successfully.")

            if nbr_errors > 0:
                st.error(f"Upload completed with a total of {nbr_errors} errors.")
            else:
                st.success("All data uploaded successfully!")
    else:
        st.warning("Pick a segment to analyze and a schema first.")

with tab5:
    if selected := st.session_state.selected_schema:
        for hostname in st.session_state.selected_hostnames:
            st.header(hostname, divider=True)
            st.session_state.schema_node = InfrahubNode(
                client=infrahub_client, schema=st.session_state.schema[selected], branch=st.session_state.infrahub_branch
            )

            full_query = exclude_keys(asyncio.run(st.session_state.schema_node.generate_query_data(filters={"in_config__name__value": hostname})))

            col1, col2 = st.columns(2)

            formatted_query = f"{{\n{dict_to_gql_query(full_query)}\n}}"

            with col1:
                st.header("Query")
                st.markdown(f"```gql\n\n{formatted_query}\n```")

            st.session_state.pulled_data = run_gql_query(formatted_query)

            with col2:
                st.header("Data")
                st.write(st.session_state.pulled_data)



with tab6:
    # Display the json code in real-time
    st.write("Generate a template!")

    j2llm = GenerateJinja2Task(model_name="gpt-4o")

    tab_keys = list(CONFIG_PATTERNS.keys())
    schema_tabs = st.tabs(tab_keys)

    for i, tab in enumerate(schema_tabs):
        with tab:
            tab_key = tab_keys[i]
            if st.button("Generate Template", key=f"{tab_keys[i]}-generate"):
                expected = [x.get(tab_key, []) for x in st.session_state.parsed_configs]

                # f"# Example {i+1}\n" +
                expected = ["\n".join(x) for x in expected if x]

                expected = "```\n\n```txt\n".join(expected)

                data = st.session_state.pulled_data

                with st.expander("Data"):
                    st.write(data)

                with st.expander("Prompt"):
                    st.markdown(
                        "```\n"
                        + f"{asyncio.run(j2llm.render_prompt(input_data=data, expected_output=expected))}".replace(
                            "```", r"'''"
                        )
                    )

                # NOTE: For troubleshooting
                # with open("temps.json", "w") as f:
                #     json.dump({"expected": expected, "data": data}, f, indent=4)

                with st.spinner("Generating template..."):
                    # NOTE: You can put data ([0], for one device) in a {"data": } key for better results if n=1
                    template = asyncio.run(j2llm.execute(data, expected))
                    st.session_state.templates[tab_keys[i]] = template

                st.markdown(f"```j2\n{st.session_state.templates.get(tab_key)}\n```")

                st.write("Template is " + "Valid! 🟢" if j2llm.validate_syntax(template) else "INVALID! 🛑")

                for j, fname in enumerate(st.session_state.selected_hostnames):
                    st.header(fname, divider=True)
                    try:
                        query = asyncio.run(st.session_state.schema_node.generate_query_data(filters={"in_config__name__value": fname}))

                        formatted_query = f"{{\n{exclude_keys(dict_to_gql_query(query))}\n}}"

                        with st.expander("Query"):
                            st.markdown(f"```gql\n\n{formatted_query}\n```")

                        data = run_gql_query(formatted_query)

                        rendered = j2llm.render_template(template, data)

                        test_data = st.session_state.parsed_configs[j].get(tab_key, [])

                        test_data = "\n".join(test_data)

                        test_result = True

                        test_lines = rendered.splitlines()

                        extra_lines = []

                        if test_lines:
                            for line in test_lines:
                                if line not in test_data:
                                    test_result = False
                                    extra_lines.append(line)
                            
                            rendered_result = "\n".join(test_lines) + "\n"
                        else:
                            rendered_result = "Nothing was rendered.\n"

                        st.write(f"\n```\n{rendered_result}```\nPassed: {'🟢' if test_result else '🛑'}")

                        if extra_lines:
                            lines = ":red[" + "]\n\n:red[".join(extra_lines) + "]"
                            st.markdown(f"**Extra lines not found in config:**\n\n{lines}")

                    except Exception as e:
                        st.write(f"Templating failed:\n{e}")
