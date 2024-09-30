import asyncio
import difflib

import streamlit as st

from streamlit_ace import st_ace

from emma.analyzer_utils import CONFIG_PATTERNS
from emma.infrahub import run_gql_query
from emma.gql_queries import exclude_keys, dict_to_gql_query

from pulse.tasks.generate_jinja2.task import GenerateJinja2Task


def generate_template_tab():
    # Display the json code in real-time
    st.write("Generate a template!")

    j2llm = GenerateJinja2Task(model_name="gpt-4o")

    tab_keys = list(CONFIG_PATTERNS.keys())
    schema_tabs = st.tabs(tab_keys)

    for i, tab in enumerate(schema_tabs):
        with tab:
            tab_key = tab_keys[i]
            if st.button("Generate Template", key=f"{tab_keys[i]}-generate"):
                expected = [x.get(tab_key, []) for x in st.session_state.parsed_configs]

                # f"# Example {i+1}\n" +
                expected = ["\n".join(x) for x in expected if x]

                expected = "```\n\n```txt\n".join(expected)

                data = st.session_state.pulled_data

                with st.expander("Data"):
                    st.write(data)

                with st.expander("Prompt"):
                    st.markdown(
                        "```\n"
                        + f"{asyncio.run(j2llm.render_prompt(input_data=data, expected_output=expected))}".replace(
                            "```", r"'''"
                        )
                    )

                # NOTE: For troubleshooting
                # with open("temps.json", "w") as f:
                #     json.dump({"expected": expected, "data": data}, f, indent=4)

                with st.spinner("Generating template..."):
                    # NOTE: You can put data ([0], for one device) in a {"data": } key for better results if n=1
                    template = asyncio.run(j2llm.execute(data, expected))
                    st.session_state.templates[tab_keys[i]] = template

            if st.session_state.templates:

                st.session_state.templates[tab_key] = st.text_area(label="Template", value=st.session_state.templates.get(tab_key, ""), height=int(len(st.session_state.templates[tab_key])//1.6))

                st.write(st.session_state.templates)

                st.write("Template is " + "Valid! 🟢" if j2llm.validate_syntax(st.session_state.templates[tab_key]) else "INVALID! 🛑")

                for j, fname in enumerate(st.session_state.selected_hostnames):
                    st.header(fname, divider=True)
                    try:
                        query = asyncio.run(st.session_state.schema_node.generate_query_data(filters={"in_config__name__value": fname}))

                        formatted_query = f"{{\n{exclude_keys(dict_to_gql_query(query))}\n}}"

                        with st.expander("Query"):
                            st.markdown(f"```gql\n\n{formatted_query}\n```")

                        data = run_gql_query(formatted_query)

                        rendered = j2llm.render_template(st.session_state.templates[tab_key], data)

                        test_data = st.session_state.parsed_configs[j].get(tab_key, [])

                        test_data = "\n".join(test_data)

                        test_result = True

                        test_lines = [x.strip() for x in rendered.splitlines()]

                        if test_lines:
                            for line in test_lines:
                                if line not in test_data:
                                    test_result = False
                                    break

                            rendered_result = "\n".join(test_lines) + "\n"
                        else:
                            rendered_result = "Nothing was rendered.\n"

                        st.write(f"\n```\n{rendered_result}```\nPassed: {'🟢' if test_result else '🛑'}")

                        if not test_result:
                            # Sort both lists of lines before comparing
                            sorted_test_lines = sorted([x for x in test_lines if x])
                            sorted_test_data = sorted([x for x in test_data.splitlines() if x])

                            diff = difflib.ndiff(sorted_test_lines, sorted_test_data)

                            # Format the output
                            diff_text = "\n".join(diff)

                            # Display the diff
                            st.code(diff_text, language="diff")

                    except Exception as e:
                        st.write(f"Templating failed:\n{e}")
