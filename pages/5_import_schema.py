import streamlit as st
import yaml

from emma.infrahub import (
    add_branch_selector,
    add_infrahub_address,
    check_schema,
    load_schema,
)

# Initialization
if "is_upload_valid" not in st.session_state:
    st.session_state["is_upload_valid"] = False


# Page layout
# TODO: Add icon to that page page_icon=":material/upload_file:"
st.markdown("# Schema Loader")
# st.set_page_config(page_title="Schema Importer")
add_infrahub_address(st.sidebar)
add_branch_selector(st.sidebar)

uploaded_files = st.file_uploader(
    "Uploader",
    label_visibility="hidden",
    accept_multiple_files=True,
    type=["yaml", "yml"],
    help="If you need help building your schema, feel free to reach out to Opsmill team!",
)

preview_container = st.container(border=False)

apply_button = st.button(
    label="🚀 Load to Infrahub",
    type="primary",
    use_container_width=True,
)

result_container = st.container(border=False)

# TODO: Handle reupload and so on ...
# TODO: Add session storage and so on
# TODO: Handle states so if non valid or empty files button remains disabled
# TODO: Somehow the button is updated before the end of the upload ...
# If something is uploaded ...
if not apply_button and len(uploaded_files) > 0:
    # Set upload as valid
    st.session_state["is_upload_valid"] = True

    # Loop over all uploaded files
    for uploaded_file in uploaded_files:
        # Prep a preview expander for each file
        with preview_container.status("Checking YAML ...") as preview_status:
            # Check if the provided file contains a valid YAML
            try:
                # First load the yaml and make sure it's valid
                schema_content = yaml.safe_load(uploaded_file.read())
                preview_status.success("This YAML file is valid", icon="✅")
                preview_status.code(
                    yaml.safe_dump(schema_content), language="yaml", line_numbers=True
                )

                # Then check schema over Infrahub instance
                success, response = check_schema(
                    branch=st.session_state.infrahub_branch, schemas=[schema_content]
                )

                # If something went wrong
                if not success:
                    st.session_state["is_upload_valid"] = False
                    preview_status.error("Infrahub doesn't like it!", icon="🚨")
                    preview_status.exception(response)  # TODO: Improve error message
                    preview_status.update(
                        label=uploaded_file.name, state="error", expanded=True
                    )
                else:
                    # Otherwise we load the diff
                    preview_status.success(
                        "This is the diff against current schema", icon="👇"
                    )
                    preview_status.code(yaml.safe_dump(response), language="yaml")
                    preview_status.update(
                        label=uploaded_file.name, state="complete", expanded=True
                    )

            # Something wrong happened with YAML
            except yaml.YAMLError as exc:
                st.session_state["is_upload_valid"] = False
                preview_status.error("This file contains a YAML error!", icon="🚨")
                preview_status.exception(exc)  # TODO: Improve that?
                preview_status.update(
                    label=uploaded_file.name, state="error", expanded=True
                )

# If someone clicks the button and upload is ok
if apply_button and st.session_state.is_upload_valid:
    # Loop over all uploaded files
    for uploaded_file in uploaded_files:
        try:
            with result_container.status("Loading schema ...") as result_status:
                result_status.update(expanded=True)

                st.write("Loading YAML files...")
                schema_content = yaml.safe_load(uploaded_file.read())

                st.write("Calling Infrahub API...")
                response = load_schema(
                    branch=st.session_state.infrahub_branch, schemas=[schema_content]
                )

                if response.errors:
                    result_status.update(
                        label="Something went wrong", state="error", expanded=True
                    )
                    result_status.exception(response.errors)
                else:
                    st.balloons()  # 🎉
                    result_status.update(
                        label="🚀 Schema loaded!", state="complete", expanded=True
                    )

                if response.schema_updated:
                    result_status.success("Schema loaded successfully!", icon="✅")
                else:
                    result_status.success(
                        "The schema in Infrahub was already up to date, no changes were required",
                        icon="✅",
                    )

        except yaml.YAMLError as exc:
            result_status.error(
                f"This file {uploaded_file.name} contains an error!", icon="🚨"
            )
            result_status.write(exc)
# If someome clicks even tho upload is faulty
elif apply_button and not st.session_state.is_upload_valid:
    st.toast("One uploaded file looks fishy...", icon="🚨")
