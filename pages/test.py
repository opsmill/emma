import streamlit as st
import yaml
import zipfile
import io
import tempfile
import subprocess
import os

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
        "template_path": f"{template_name}.j2"
    }
    
    if "jinja2_transforms" not in yaml_dict:
        yaml_dict["jinja2_transforms"] = []
    
    yaml_dict["jinja2_transforms"].append(jinja_transform)
    
    # Adding the artifact definition
    artifact_definition = {
        "name": f"{template_name.capitalize()} Config for {target_group.capitalize()}",
        "artifact_name": f"{template_name}-config",
        "parameters": {
            "device": "name__value"
        },
        "content_type": "text/plain",
        "targets": f"{target_group}",
        "transformation": f"{template_name}_config"
    }
    
    if "artifact_definitions" not in yaml_dict:
        yaml_dict["artifact_definitions"] = []
    
    yaml_dict["artifact_definitions"].append(artifact_definition)

    # Adding the query definition
    query_definition = {
        "name": query_name,
        "file_path": f"{query_name}.gql"
    }
    
    if "queries" not in yaml_dict:
        yaml_dict["queries"] = []
    
    yaml_dict["queries"].append(query_definition)

    return yaml_dict

# Function to save files to a temp folder and run the validation CLI
def run_validation_cli(yaml_data, other_files, transform_name):
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
        
        # Run the CLI tool (replace 'your_cli_command' with your actual command)
        cli_command = f'cd {tmpdirname} && git init && infrahubctl render {transform_name}_config'
        result = subprocess.run(cli_command, shell=True, capture_output=True, text=True)

        # Return the output
        return result.stdout, result.stderr

# Initialize session state for YAML data
if 'yaml_data' not in st.session_state:
    st.session_state.yaml_data = {}

# Streamlit app
st.title("Update repo")

# Upload YAML file or generate new one
uploaded_file = st.file_uploader("Upload your .infrahub.yml (or leave blank to generate a new one)", type=["yaml", "yml"])

if uploaded_file is not None:
    # Parse the uploaded YAML file and store it in session state
    st.session_state.yaml_data = parse_yaml(uploaded_file)
else:
    st.write("Current .infrahub.yml")
    st.session_state.yaml_data = {}

# Display the current YAML data
st.subheader("Current YAML Data:")
st.code(dict_to_yaml(st.session_state.yaml_data), language="yaml")

# Get user input for template name, query name, and target group
template_name = st.text_input("Enter Template Name", value="template1")
query_name = st.text_input("Enter Query Name", value="query1")
target_group = st.text_input("Enter Target Group", value="group1")

if st.button("Add Artifact and Transform"):
    # Add artifacts and transforms to YAML and update session state
    st.session_state.yaml_data = add_artifact_and_transform(st.session_state.yaml_data, template_name, query_name, target_group)

    # Display updated YAML
    st.subheader("Updated YAML Data:")
    st.code(dict_to_yaml(st.session_state.yaml_data), language="yaml")

    # Other files to include in the ZIP
    other_files = {
        'ntp.gql': b"""{
NetworkNTPServerRole {
  edges {
    node {
      hfid
      display_label
      name {
        value
      }
      description {
        value
      }
      in_config {
        edges {
          node {
            display_label
          }
        }
      }
      servers {
        edges {
          node {
            display_label
          }
        }
      }
    }
  }
}
}""",
        'ntp.j2': b"""{% for edge in data.NetworkNTPServerRole.edges %}
  {% set node = edge.node %}
  {% set vrf = 'management' if node.in_config.edges|length > 4 else 'default' %}
  ntp server {{ node.display_label }} use-vrf {{ vrf }}
{% endfor %}"""
    }

    # Run the CLI validation tool and get the result
    stdout, stderr = run_validation_cli(st.session_state.yaml_data, other_files, template_name)

    # Display CLI result
    if stdout:
        st.subheader(f"infrahubctl render {template_name}")
        st.text(stdout)
    if stderr:
        st.subheader("infrahubctl Errors:")
        st.text(stderr)

    # Create a ZIP file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        # Add updated YAML to the ZIP
        zip_file.writestr(".infrahub.yml", dict_to_yaml(st.session_state.yaml_data).encode('utf-8'))
        
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
        mime="application/zip"
    )
