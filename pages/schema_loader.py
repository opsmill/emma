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

if "schemas" not in st.session_state:
    st.session_state.schemas = []

if "apply_button" not in st.session_state:
    st.session_state.apply_button_disabled = True

# Check for generated files in session state
generated_files = st.session_state.get("generated_files", [])

if generated_files:
    st.session_state.uploaded_files = generated_files
    st.write("Using generated files from another tab.")
else:
    # Use the generated files or fall back to file uploader
    st.session_state.uploaded_files = st.file_uploader(
        "Uploader",
        label_visibility="hidden",
        accept_multiple_files=True,
        type=["yaml", "yml"],
        help="If you need help building your schema, feel free to reach out to Opsmill team!",
    )

# If something is uploaded or available in session state...
if st.session_state.uploaded_files and len(st.session_state.uploaded_files) > 0:
    st.session_state.is_upload_valid = True
    preview_container = st.container(border=False)

    st.session_state.schemas = []
    for uploaded_file in st.session_state.uploaded_files:
        file_name = uploaded_file["name"] if isinstance(uploaded_file, dict) else uploaded_file.name
        file_content = uploaded_file["content"] if isinstance(uploaded_file, dict) else uploaded_file.read()

        msg = st.toast(body=f"Checking {file_name} ...")
        with preview_container.status(f"Details for {file_name}:") as preview_status:
            try:
                schema_content = yaml.safe_load(file_content)
                preview_status.success("This YAML file is valid", icon="✅")
                preview_status.code(yaml.safe_dump(schema_content), language="yaml", line_numbers=True)
                st.session_state.schemas.append(schema_content)
            except yaml.YAMLError as exc:
                st.session_state.is_upload_valid = False
                preview_container.error("This file contains a YAML error!", icon="🚨")
                preview_status.exception(exception=exc)  # TODO: Improve that?
                msg.toast(body=f"Error encountered for {file_name}", icon="🚨")

    with preview_container.status("Schema check ...") as preview_status:
        # Then check schema over Infrahub instance
        schema_check_result = check_schema(branch=st.session_state.infrahub_branch, schemas=st.session_state.schemas)

        if schema_check_result:
            # If something went wrong
            if not schema_check_result.success:
                st.session_state.is_upload_valid = False
                preview_status.error("Infrahub doesn't like it!", icon="🚨")
                if schema_check_result.response:
                    # TODO: Improve error message
                    preview_status.exception(exception=BaseException(schema_check_result.response))
                msg.toast(body=f"Error encountered for {file_name}", icon="🚨")
            else:
                # Otherwise we load the diff
                preview_status.success("This is the diff against current schema", icon="👇")
                if schema_check_result.response:
                    preview_status.code(yaml.safe_dump(schema_check_result.response), language="yaml")
                msg.toast(body=f"Loading complete for {file_name}", icon="👍")
                st.session_state.apply_button_disabled = False


apply_button = st.button(
    label=f"🚀 Load to :blue[__*{st.session_state.infrahub_branch}*__] branch in Infrahub",
    type="primary",
    use_container_width=True,
    disabled=st.session_state.apply_button_disabled,
)

result_container = st.container(border=False)

# If someone clicks the button and upload is ok
if apply_button and st.session_state.is_upload_valid:
    with result_container.status("Loading schema ...") as result_status:
        result_status.update(expanded=True)

        st.write("Calling Infrahub API...")
        response = load_schema(branch=st.session_state.infrahub_branch, schemas=st.session_state.schemas)
        st.write("Computing results...")

        if response:
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

elif apply_button and not st.session_state.is_upload_valid:
    st.toast("One uploaded file looks fishy...", icon="🚨")
