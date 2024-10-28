import asyncio
import io
import os
import subprocess
import tempfile
import zipfile
from contextlib import chdir, redirect_stderr, redirect_stdout

import infrahub_sdk.ctl.cli_commands as cli
import streamlit as st
import yaml

from emma.gql_queries import dict_to_gql_query, exclude_keys


# Function to parse the uploaded YAML file
def parse_yaml(uploaded_file):
    return yaml.safe_load(uploaded_file)


# Function to convert dict to YAML formatted string
def dict_to_yaml(yaml_data):
    return yaml.dump(yaml_data, default_flow_style=False)


# Function to add artifacts and transforms
def add_artifact_and_transform(yaml_dict, template_name, query_name, target_group):
    # Adding the Jinja2 transform
    jinja_transform = {
        "name": f"{template_name}_config",
        "description": f"Template to generate {template_name} configuration",
        "query": query_name,
        "template_path": f"{template_name}.j2",
    }

    if "jinja2_transforms" not in yaml_dict:
        yaml_dict["jinja2_transforms"] = []

    yaml_dict["jinja2_transforms"].append(jinja_transform)

    # Adding the artifact definition
    artifact_definition = {
        "name": f"{template_name.capitalize()} Config for {target_group.capitalize()}",
        "artifact_name": f"{template_name}-config",
        "parameters": {"device": "name__value"},
        "content_type": "text/plain",
        "targets": f"{target_group}",
        "transformation": f"{template_name}_config",
    }

    if "artifact_definitions" not in yaml_dict:
        yaml_dict["artifact_definitions"] = []

    yaml_dict["artifact_definitions"].append(artifact_definition)

    # Adding the query definition
    query_definition = {"name": query_name, "file_path": f"{query_name}.gql"}

    if "queries" not in yaml_dict:
        yaml_dict["queries"] = []

    yaml_dict["queries"].append(query_definition)

    return yaml_dict


# Function to save files to a temp folder and run the validation CLI
def run_validation_cli(yaml_data, other_files, transform_name, selected_host):
    # Create a temp folder
    with tempfile.TemporaryDirectory() as tmpdirname:
        # Save .infrahub.yml
        yaml_path = os.path.join(tmpdirname, ".infrahub.yml")
        with open(yaml_path, "w") as yaml_file:
            yaml_file.write(dict_to_yaml(yaml_data))

        # Save other files (query and template)
        for filename, filedata in other_files.items():
            file_path = os.path.join(tmpdirname, filename)
            with open(file_path, "wb") as file:
                file.write(filedata)

        cli_command = f"cd {tmpdirname} && git init"

        # Initialize repo
        subprocess.run(cli_command, shell=True, capture_output=True, text=True, check=False)

        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):  # Redirect console outs to log strings
            with chdir(tmpdirname):
                cli.render(transform_name=f"{transform_name}_config", variables=[f"device={selected_host}"])

        return stdout.getvalue(), stderr.getvalue()


def update_repo_tab():
    # Initialize session state for YAML data
    if "yaml_data" not in st.session_state:
        st.session_state.yaml_data = {}

    # Title or label for the tab content
    st.title("Update Repo")

    # Upload YAML file or generate new one
    uploaded_file = st.file_uploader(
        "Upload your .infrahub.yml (or leave blank to generate a new one)", type=["yaml", "yml"]
    )

    st.write("Select a device to validate with.")
    selected_device = st.selectbox("Host to render", st.session_state.selected_hostnames)

    if uploaded_file is not None:
        # Parse the uploaded YAML file and store it in session state
        st.session_state.yaml_data = parse_yaml(uploaded_file)
    else:
        st.write("Current .infrahub.yml")
        st.session_state.yaml_data = {}

    # Display the current YAML data
    st.subheader("Current YAML Data:")
    st.code(dict_to_yaml(st.session_state.yaml_data), language="yaml")

    selected_segment = st.session_state.selected_segment

    # Get user input for template name, query name, and target group
    template_name = st.text_input("Enter Template Name", value=selected_segment)
    query_name = st.text_input("Enter Query Name", value=selected_segment)
    target_group = st.text_input("Enter Target Group", value="InfraDevice")

    if st.button("Add Artifact and Transform"):
        # Add artifacts and transforms to YAML and update session state
        st.session_state.yaml_data = add_artifact_and_transform(
            st.session_state.yaml_data, template_name, query_name, target_group
        )

        # Display updated YAML
        st.subheader("Updated YAML Data:")
        st.code(dict_to_yaml(st.session_state.yaml_data), language="yaml")

        full_query = dict_to_gql_query(
            exclude_keys(
                asyncio.run(
                    st.session_state.schema_node.generate_query_data(filters={"in_config__name__value": "$device"})
                )
            )
        )

        # Other files to include in the ZIP
        full_query = f"query {selected_segment} ($device: String!) {{\n{full_query}\n}}".replace('"$device"', "$device")

        other_files = {
            selected_segment + ".gql": full_query.encode("utf-8"),
            selected_segment + ".j2": st.session_state.templates[selected_segment].encode("utf-8"),
        }

        # Run the CLI validation tool and get the result
        stdout, stderr = run_validation_cli(st.session_state.yaml_data, other_files, template_name, selected_device)
        if stdout:
            st.subheader(f"infrahubctl rendered {template_name} successfully!")
            st.write(stdout)
        else:
            st.subheader("infrahubctl failed to render updates.")
            st.write(stderr)

        # Create a ZIP file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            # Add updated YAML to the ZIP
            zip_file.writestr(".infrahub.yml", dict_to_yaml(st.session_state.yaml_data).encode("utf-8"))

            # Add other files to the ZIP
            for filename, filedata in other_files.items():
                zip_file.writestr(filename, filedata)

        # Prepare ZIP for download
        zip_buffer.seek(0)

        # Download button for the ZIP file
        st.download_button(
            label="Download Repo Updates",
            data=zip_buffer,
            file_name="infrahub_repo_updates.zip",
            mime="application/zip",
        )
