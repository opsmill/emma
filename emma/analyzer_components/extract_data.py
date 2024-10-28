import streamlit as st

from emma.analyzer_utils import display_segments, generate_data_regex
from emma.infrahub import get_json_schema


def extra_data_tab():
    if not st.session_state.selected_segment:
        st.markdown("**Sorry, select a segment to process first. Return to select devices and try again.**")
    elif selected := st.session_state.selected_schema:
        st.write(f"Extracting data for {selected}")

        data = [
            "\n".join(x[st.session_state.selected_segment])
            for x in st.session_state.parsed_configs[:10]
            if x[st.session_state.selected_segment]
        ]

        prompt, reg = generate_data_regex(get_json_schema(selected), data)

        with st.expander("Prompt"):
            st.write(prompt)

        with st.expander("Generated Regex"):
            st.write(reg)

        display_segments(st.session_state.selected_hostnames, st.session_state.parsed_configs, reg, raw=False)

    else:
        st.write("Select a schema first.")
