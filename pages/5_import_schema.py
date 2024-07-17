import streamlit as st
import yaml

from emma.infrahub import add_branch_selector, add_infrahub_address, load_schema

# Initialization
if "is_smth_uploaded" not in st.session_state:
    st.session_state["is_smth_uploaded"] = False
if "is_schema_applied" not in st.session_state:
    st.session_state["is_schema_applied"] = False


def click_apply_schema():
    st.session_state["is_schema_applied"] = True


def preview_upload_files():
    st.session_state["is_smth_uploaded"] = True


# Page layout
# TODO: Add icon to that page page_icon=":material/upload_file:"
st.markdown("# Schema Importer")
st.set_page_config(page_title="Schema Importer")
add_infrahub_address(st.sidebar)
add_branch_selector(st.sidebar)

uploaded_files = st.file_uploader(
    "Uploader",
    label_visibility="hidden",
    accept_multiple_files=True,
    type=["yaml", "yml"],
    help="If you need help building your schema, feel free to reach out to Opsmill team!",
    on_change=preview_upload_files,
)

preview_container = st.container(border=False)

apply_button = st.button(
    label="🚀 Apply to Infrahub",
    type="primary",
    # help="You first need to upload valid YAML files...", #TODO: Make this dynamic somehow?
    disabled=not st.session_state.is_smth_uploaded,
    on_click=click_apply_schema,
    use_container_width=True,
)

result_container = st.container(border=False)

# TODO: Handle reupload and so on ...
# TODO: Schema validation?
# TODO: Add session storage and so on
# TODO: Handle states so if non valid or empty files button remains disabled
# TODO: Somehow the button is updated before the end of the upload ...
# If someone uploads something
if (
    st.session_state.is_smth_uploaded is True
    and len(uploaded_files) > 0
    and st.session_state.is_schema_applied is False
):
    # Loop over all uploaded files
    for uploaded_file in uploaded_files:
        # Prep a preview expander for each file
        with preview_container.status("Checking YAML ...") as preview_status:
            # Check if the provided file contains a valid YAML
            try:
                python_dict = yaml.safe_load(uploaded_file.read())
                preview_status.success("This file is valid!", icon="✅")
                preview_status.code(
                    yaml.dump(python_dict), language="yaml", line_numbers=True
                )
                preview_status.update(
                    label=uploaded_file.name, state="complete", expanded=True
                )

            # Something wrong happened
            except yaml.YAMLError as exc:
                preview_status.error("This file contains an error!", icon="🚨")
                preview_status.write(exc)  # TODO: Improve that?
                preview_status.update(
                    label=uploaded_file.name, state="error", expanded=True
                )

# If someone clicks the button
if apply_button:
    # Loop over all uploaded files
    for uploaded_file in uploaded_files:
        try:
            with result_container.status("Loading schema ...") as result_status:
                result_status.update(expanded=True)

                st.write("Loading YAML files...")
                python_dict = yaml.safe_load(uploaded_file.read())

                st.write("Calling Infrahub API...")
                response = load_schema(
                    branch=st.session_state.infrahub_branch, schemas=[python_dict]
                )

                if response.errors:
                    result_status.update(
                        label="Something went wrong", state="error", expanded=True
                    )
                    result_status.write(response.errors)
                else:
                    result_status.update(
                        label="🚀 Schema loaded!", state="complete", expanded=True
                    )

                if response.schema_updated:
                    result_status.success("Schema loaded successfully!", icon="✅")
                else:
                    result_status.success(
                        "The schema in Infrahub was is already up to date, no changes were required",
                        icon="✅",
                    )

        except yaml.YAMLError as exc:
            result_status.error(
                f"This file {uploaded_file.name} contains an error!", icon="🚨"
            )
            result_status.write(exc)
