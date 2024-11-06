import json

import streamlit as st

from emma.analyzer_utils import display_segments, generate_data_regex
from emma.infrahub import get_json_schema


def extra_data_tab():
    # For debugging schema
    # st.write("schemas", [get_json_schema(schema) for schema in st.session_state.selected_schemas])

    st.session_state.setdefault("combined_schema", {"type": "object", "properties": {}})

    if not st.session_state.selected_segment:
        st.markdown("**Sorry, select a segment to process first. Return to select devices and try again.**")

    elif st.session_state.selected_schemas:
        # Handle multiple schemas with `oneOf` JSON schema if more than one schema is selected
        selected_schemas = st.session_state.selected_schemas
        st.write(f"Extracting data for {', '.join(selected_schemas)}")

        # Generate JSON schemas for each selected schema
        schemas = [get_json_schema(schema_name) for schema_name in selected_schemas]

        # st.write("schema:", st.session_state.combined_schema)

        if len(schemas) > 1:
            st.session_state.combined_schema = {"type": "object", "properties": {}}

            # Merge all schema properties into one
            for json_schema in schemas:
                st.session_state.combined_schema["properties"].update(json_schema.get("properties", {}))

        else:
            st.session_state.combined_schema = schemas[0]

        # If not in session state, generate and store initial regex and prompt
        if "regex_data" not in st.session_state or "regex_prompt" not in st.session_state:
            # Gather data for the selected segment from each schema
            data = [
                "\n".join(config[st.session_state.selected_segment])
                for config in st.session_state.parsed_configs[:10]
                if config.get(st.session_state.selected_segment)
            ]

            # Generate regex data and prompt using the combined schema
            prompt, reg = generate_data_regex(json.dumps(st.session_state.combined_schema), data)
            st.session_state.regex_data = reg
            st.session_state.regex_prompt = prompt

        # Show prompt
        with st.expander("Combined Schema"):
            st.write(st.session_state.combined_schema)

        with st.expander("Prompt"):
            st.write(st.session_state.regex_prompt)

        # Display each item in the dictionary as editable fields with a delete option
        with st.expander("Generated Regex"):
            keys_to_delete = []
            for key, value in st.session_state.regex_data.items():
                col1, col2 = st.columns([4, 1])
                with col1:
                    # Generate a text input for each key-value pair
                    updated_value = st.text_input(f"Edit value for {key}", value, key=key)
                    # Update the session state with the new value
                    st.session_state.regex_data[key] = updated_value
                with col2:
                    # Add a trashcan icon button
                    if st.button("🗑️", key=f"delete_{key}"):
                        keys_to_delete.append(key)

            # Remove items after loop to avoid modifying dictionary during iteration
            for key in keys_to_delete:
                del st.session_state.regex_data[key]

        # Rerun button to regenerate regex and prompt
        if st.button("Rerun Regex Generation"):
            data = [
                "\n".join(x[st.session_state.selected_segment])
                for x in st.session_state.parsed_configs[:10]
                if x[st.session_state.selected_segment]
            ]
            prompt, reg = generate_data_regex(get_json_schema(st.session_state.combined_schema), data)
            st.session_state.regex_data = reg
            st.session_state.regex_prompt = prompt
            st.rerun()  # Rerun app to update UI with new regex data

        # Display segments using the updated regex
        display_segments(
            st.session_state.selected_hostnames, st.session_state.parsed_configs, st.session_state.regex_data, raw=False
        )

    else:
        st.write("Select a schema first.")
