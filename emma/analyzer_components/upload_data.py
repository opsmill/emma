import pandas as pd
import streamlit as st

from emma.analyzer_utils import upload_data, validate_if_df_is_compatible_with_schema


def upload_data_tab(): # noqa: PLR0912, C901
    with st.expander("Raw Extracted"):
        st.write(st.session_state.extracted_data)

    if not st.session_state.data_to_upload:
        st.session_state.data_to_upload = {
            device: pd.DataFrame(data[st.session_state.selected_segment]).dropna(how="all")
            for device, data in st.session_state.extracted_data.items()
        }

    if selected_schema := st.session_state.selected_schema:
        # Get all enum columns from the schema
        enum_columns = {
            attr.name: [choice["name"] for choice in attr.choices if choice["name"] is not None]
            for attr in st.session_state.schema[selected_schema].attributes
            if attr.choices
        }

        # st.write(enum_columns)

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
                st.session_state.data_to_upload = {
                    device: pd.DataFrame(data[st.session_state.selected_segment])
                    for device, data in st.session_state.extracted_data.items()
                }

                st.success(
                    f"Applied default value '{selected_default_value}' to '{selected_enum_column}' across all devices."
                )

        for device, data in st.session_state.data_to_upload.items():
            # If 'data' is a dict, convert it to a DataFrame first
            if isinstance(data, dict):
                df = pd.DataFrame(data[st.session_state.selected_segment])
            else:
                df = data  # If it's already a DataFrame, keep it

            # Get the columns defined in the schema
            schema_columns = (
                st.session_state.schema[selected_schema].mandatory_input_names
                + st.session_state.schema[selected_schema].attribute_names
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
                        options=options, label=f"{attr.name.capitalize()} (Select one)"
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
                device_errors = upload_data(
                    df=df, schema_kind=st.session_state.selected_schema, hostname=device, branch=branch
                )
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
