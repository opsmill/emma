import asyncio
import difflib
from datetime import datetime, timezone

import streamlit as st
from pulse.tasks.generate_jinja2.task import GenerateJinja2Task

from emma.gql_queries import dict_to_gql_query, exclude_keys
from emma.infrahub import run_gql_query


def generate_template_tab():
    # Display the json code in real-time
    st.write("Generate a template!")

    j2llm = GenerateJinja2Task(model_name="gpt-4o")

    selected_segment = st.session_state.get("selected_segment")

    if selected_segment:
        if st.button("Generate Template", key=f"{selected_segment}-generate"):
            expected = [x.get(selected_segment, []) for x in st.session_state.parsed_configs]
            expected = ["\n".join(x) for x in expected if x]
            expected = "```\n\n```txt\n".join(expected)

            data = {"data": st.session_state.pulled_data}

            with st.expander("Data"):
                st.write(data)

            with st.expander("Prompt"):
                st.markdown(
                    "```\n"
                    + asyncio.run(j2llm.render_prompt(input_data=data[:10], expected_output=expected[:10])).replace(
                        "```", r"'''"
                    )
                )

            with st.spinner("Generating template..."):
                template = asyncio.run(j2llm.execute(data, expected))
                st.session_state.templates[selected_segment] = template

        if selected_segment in st.session_state.templates:
            template_text = st.session_state.templates.get(selected_segment, "")
            st.session_state.templates[selected_segment] = st.text_area(
                label="Template", value=template_text, height=int(len(template_text) // 1.6)
            )

            valid = j2llm.validate_syntax(st.session_state.templates[selected_segment])
            st.write("Template is " + ("Valid! 🟢" if valid else "INVALID! 🛑"))

            if valid:
                st.download_button(
                    label="Download Template",
                    data=template_text,
                    file_name=f"{selected_segment}_emma_generated_{datetime.now(tz=timezone.utc).strftime('%d%m%Y')}.j2",
                    mime="text/j2",
                )

            for j, fname in enumerate(st.session_state.selected_hostnames):
                st.header(fname, divider=True)
                try:
                    query = asyncio.run(
                        st.session_state.schema_node.generate_query_data(filters={"in_config__name__value": fname})
                    )

                    formatted_query = f"{{\n{exclude_keys(dict_to_gql_query(query))}\n}}"

                    with st.expander("Query"):
                        st.markdown(f"```gql\n\n{formatted_query}\n```")

                    data = {"data": run_gql_query(formatted_query)}
                    rendered = j2llm.render_template(st.session_state.templates[selected_segment], data)

                    test_data = "\n".join(st.session_state.parsed_configs[j].get(selected_segment, []))
                    test_result = all(line.strip() in test_data for line in rendered.splitlines())

                    rendered_result = (
                        "\n".join([x.strip() for x in rendered.splitlines()]) + "\n"
                        if test_result
                        else "Nothing was rendered.\n"
                    )
                    st.write(f"\n```\n{rendered_result}```\nPassed: {'🟢' if test_result else '🛑'}")

                    if not test_result:
                        sorted_test_lines = sorted([x.strip() for x in rendered.splitlines() if x])
                        sorted_test_data = sorted([x.strip() for x in test_data.splitlines() if x])

                        diff = difflib.ndiff(sorted_test_lines, sorted_test_data)
                        st.code("\n".join(diff), language="diff")

                except Exception as e:
                    st.write(f"Templating failed:\n{e}")

    else:
        st.write("No segment selected. Please select a segment to start generating a template.")
