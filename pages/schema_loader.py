import streamlit as st
import yaml

from emma.infrahub import (
    check_schema,
    load_schema,
)
from emma.streamlit_utils import set_page_config
from menu import menu_with_redirect

set_page_config(title="Schema Loader")
st.markdown("# Schema Loader")
menu_with_redirect()

# Initialization
if "is_upload_valid" not in st.session_state:
    st.session_state.is_upload_valid = False


uploaded_files = st.file_uploader(
    "Uploader",
    label_visibility="hidden",
    accept_multiple_files=True,
    type=["yaml", "yml"],
    help="If you need help building your schema, feel free to reach out to Opsmill team!",
)

preview_container = st.container(border=False)

apply_button = st.button(
    label=f"🚀 Load to :blue[__*{st.session_state.infrahub_branch}*__] branch in Infrahub",
    type="primary",
    use_container_width=True,
)

result_container = st.container(border=False)

# TODO: Add session storage and so on
# TODO: Handle states so if non valid or empty files button remains disabled
# If something is uploaded ...
if not apply_button and uploaded_files and len(uploaded_files) > 0:
    # Set upload as valid
    st.session_state.is_upload_valid = True

    # Loop over all uploaded files
    for uploaded_file in uploaded_files:
        # Prep a preview expander for each file
        with preview_container.status("Checking schema ...") as preview_status:
            # Check if the provided file contains a valid YAML
            try:
                # First load the yaml and make sure it's valid
                schema_content = yaml.safe_load(uploaded_file.read())
                preview_status.success("This YAML file is valid", icon="✅")
                preview_status.code(yaml.safe_dump(schema_content), language="yaml", line_numbers=True)

                # Then check schema over Infrahub instance
                success, response = check_schema(branch=st.session_state.infrahub_branch, schemas=[schema_content])

                # If something went wrong
                if not success:
                    st.session_state.is_upload_valid = False
                    preview_status.error("Infrahub doesn't like it!", icon="🚨")
                    preview_status.exception(response)  # TODO: Improve error message
                    preview_status.update(label=uploaded_file.name, state="error", expanded=True)
                else:
                    # Otherwise we load the diff
                    preview_status.success("This is the diff against current schema", icon="👇")
                    preview_status.code(yaml.safe_dump(response), language="yaml")
                    preview_status.update(label=uploaded_file.name, state="complete", expanded=True)

            # Something wrong happened with YAML
            except yaml.YAMLError as exc:
                st.session_state.is_upload_valid = False
                preview_status.error("This file contains a YAML error!", icon="🚨")
                preview_status.exception(exc)  # TODO: Improve that?
                preview_status.update(label=uploaded_file.name, state="error", expanded=True)

# If someone clicks the button and upload is ok
if apply_button and st.session_state.is_upload_valid:
    # Loop over all uploaded files
    with result_container.status("Loading schema ...") as result_status:
        # List with all schema dict
        schemas_data = []
        result_status.update(expanded=True)

        # Loop over all files to build schema list
        if uploaded_files:
            for uploaded_file in uploaded_files:
                try:
                    st.write(f"Loading `{uploaded_file.name}` ...")
                    schemas_data.append(yaml.safe_load(uploaded_file.read()))

                except yaml.YAMLError as exc:
                    result_status.error(f"This file {uploaded_file.name} contains an error!", icon="🚨")
                    result_status.write(exc)

        # Call Infrahub API
        st.write("Calling Infrahub API...")
        response = load_schema(branch=st.session_state.infrahub_branch, schemas=schemas_data)
        st.write("Computing results...")

        # Compute response
        if response.errors:
            result_status.update(label="Load failed ...", state="error", expanded=True)
            result_status.error("Infrahub doesn't like it!", icon="🚨")
            result_status.exception(response.errors)
        else:
            result_status.update(label="🚀 Schema loaded!", state="complete", expanded=True)

            if response.schema_updated:
                # TODO: Add an actual diff section ...
                result_container.success("Schema loaded successfully!", icon="✅")
                st.balloons()  # 🎉
            else:
                result_container.info(
                    "The schema in Infrahub was already up to date, no changes were required!",
                    icon="ℹ️",
                )

# If someome clicks even tho upload is faulty
elif apply_button and not st.session_state.is_upload_valid:
    st.toast("One uploaded file looks fishy...", icon="🚨")
