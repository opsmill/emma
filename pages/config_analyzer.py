import asyncio
import colorsys
import html
import json

import regex as re
import streamlit as st
import traceback as tb

from streamlit_ace import st_ace

from emma.streamlit_utils import set_page_config
from menu import menu_with_redirect
from pulse.tasks.generate_jinja2.task import GenerateJinja2Task
from pulse.tasks.parse_config.task import GenerateDataRegexTask

from infrahub_sdk.jinja2 import identify_faulty_jinja_code

llm = GenerateDataRegexTask(model_name="gpt-4o-mini")

default_schemas = {}

set_page_config("Config Analyzer")

menu_with_redirect()

# Initialize session state to keep json edits across reruns
if "json_code" not in st.session_state:
    for fname in ["snmp", "ntp"]:
        with open(f"./default_schemas/{fname}.json") as f:
            default_schemas[fname] = f.read()

    default_schemas["uncaptured"] = {}

    st.session_state.json_code = default_schemas

# Streamlit app starts here
st.title("View and Compare Network Configurations")

# Initialize session state for storing filenames and configs
if "filenames" not in st.session_state:
    st.session_state.filenames = []
if "configs" not in st.session_state:
    st.session_state.configs = []
if "regexes" not in st.session_state:
    st.session_state.regexes = {}
if "parsed_configs" not in st.session_state:
    st.session_state.parsed_configs = []
if "templates" not in st.session_state:
    st.session_state.templates = {}
if "extracted_data" not in st.session_state:
    st.session_state.extracted_data = {}


# Define regex patterns to capture raw segments
CONFIG_PATTERNS = {
    # "vlan": r"^vlan\s+\d+[\s\S]+?(?=^vlan\s+\d+|^!|^$)",
    # "ospf": r"^router\sospf\s\d+[\s\S]+?(?=^router\s\S+|^!|^$)",
    # "eigrp": r"^router\seigrp\s\d+[\s\S]+?(?=^router\s\S+|^!|^$)",
    # "bgp": r"^router\sbgp\s\d+[\s\S]+?(?=^router\sbgp\s\d+|^!|^$)",
    # "standard_acl": r"^access-list\s\d+[\s\S]+?(?=^access-list\s\d+|^!|^$)",
    # "extended_acl": r"^access-list\s\d+\sextended[\s\S]+?(?=^access-list\s\d+|^!|^$)",
    # "prefix_list": r"^ip\sprefix-list\s\S+[\s\S]+?(?=^ip\sprefix-list\s\S+|^!|^$)",
    # "route_map": r"^route-map\s\S+[\s\S]+?(?=^route-map\s\S+|^!|^$)",
    "ntp": r"^ntp\sserver\s\S+[\s\S]+?(?=^ntp\sserver\s\S+|^!|^$)",
    "snmp": r"^snmp-server\s.*$",
    # "logging": r"^logging\s\S+[\s\S]+?(?=^logging\s\S+|^!|^$)",
    # "line_vty": r"^line\svty\s\d+\s\d+[\s\S]+?(?=^line\s\S+|^!|^$)",
    # "line_console": r"^line\scon\s\d+[\s\S]+?(?=^line\s\S+|^!|^$)",
    # "line_aux": r"^line\saux\s\d+[\s\S]+?(?=^line\saux\s\d+|^!|^$)",
    # "class_map": r"^class-map\s\S+[\s\S]+?(?=^class-map\s\S+|^!|^$)",
    # "policy_map": r"^policy-map\s\S+[\s\S]+?(?=^policy-map\s\S+|^!|^$)",
    # "service_policy": r"^service-policy\s\S+[\s\S]+?(?=^service-policy\s\S+|^!|^$)",
    # "aaa": r"^aaa\s\S+[\s\S]+?(?=^aaa\s\S+|^!|^$)",
    # "vrf": r"^ip\svrf\s\S+[\s\S]+?(?=^ip\svrf\s\S+|^!|^$)",
    # "banner": r"^banner\s\S+[\s\S]+?(?=^banner\s\S+|^!|^$)",
    # "dns_settings": r"^(ip domain-lookup|ip domain-name\s+\S+|ip name-server\s+[\d\.\s]+(?:use-vrf\s+\S+)?)",
    # "interface": r"^interface\s+\S+[\s\S]+?(?=^interface\s+\S+|^!|^$)",
}


# Function to parse Cisco configs and return segments
def parse_cisco_config(config_text):
    raw_segments = {}
    captured_lines = []

    for label, pattern in CONFIG_PATTERNS.items():
        matches = re.findall(pattern, config_text, re.MULTILINE)
        raw_segments[label] = matches
        for match in matches:
            captured_lines.extend(match.splitlines())

    # Capture uncaptured lines (for debugging or completeness)
    config_lines = config_text.splitlines()
    uncaptured_lines = [line for line in config_lines if line.strip() and line not in captured_lines]
    raw_segments["uncaptured"] = uncaptured_lines

    return raw_segments


def find_matches_with_locations(regex_dict, text_list):
    all_results = []

    for text in text_list:
        results = {}

        for variable_name, pattern in regex_dict.items():
            matches = []

            try:
                for match in re.finditer(pattern, text, re.MULTILINE | re.DOTALL):
                    if match and len(match.groups()) >= 1:
                        match_group = 1
                    else:
                        match_group = 0

                    match_data = {
                        "match": match.group(match_group),
                        "start": match.start(match_group),
                        "end": match.end(match_group),
                    }
                    matches.append(match_data)
            except re.error as e:
                print(f"Regex error for {variable_name}: {e}")
                continue

            if matches:
                results[variable_name] = matches

        all_results.append(results)

    return all_results


def generate_data_regex(schema, config_segments):
    with st.spinner("Generating data regex..."):
        regexes = asyncio.run(llm.execute(config_segments, schema))
        return {x.name: x.regex for x in regexes if x.regex}


# Function to generate distinct colors using a color wheel
def generate_colors(num_colors):
    colors = []
    for i in range(num_colors):
        hue = i / num_colors  # Distribute colors evenly around the color wheel
        rgb = colorsys.hsv_to_rgb(hue, 0.7, 1.0)  # Convert HSV to RGB
        rgb_hex = "#{:02x}{:02x}{:02x}".format(int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))
        colors.append(rgb_hex)
    return colors


def json_to_html(data, key_to_color):
    html_parts = []
    html_parts.append("{<br>")
    for idx, (key, values) in enumerate(data.items()):
        color = key_to_color.get(key, "#FFFFFF")  # Default to white if key not found
        # Escape the key
        escaped_key = html.escape(str(key))
        # Wrap the key in a span with the color
        highlighted_key = (
            f'<span style="background-color: {color}; color: black; font-weight: bold;">"{escaped_key}"</span>'
        )
        # Now process the values, which is a list
        # Serialize the list into a JSON-like format with proper indentation
        value_html = "[<br>"
        for i, value in enumerate(values):
            escaped_value = html.escape(str(value))
            value_line = f'        "{escaped_value}"'
            if i < len(values) - 1:
                value_line += ",<br>"
            else:
                value_line += "<br>"
            value_html += value_line
        value_html += "    ]"
        # Build the line
        line = f"    {highlighted_key}: {value_html}"
        if idx < len(data) - 1:
            line += ",<br>"
        else:
            line += "<br>"
        html_parts.append(line)
    html_parts.append("}")
    return "".join(html_parts)


def dual_pane_with_highlight(texts, regex_matches):
    # texts: list of raw texts
    # regex_matches: dict with indices as keys, each value is a dict of matches for that text
    html_outputs = []  # List to store HTML outputs for each text

    for idx, raw_text in enumerate(texts):
        matches_for_text = regex_matches[idx]

        # Get unique keys from matches_for_text and generate distinct colors for them
        keys = list(matches_for_text.keys())
        colors = generate_colors(len(keys))  # Generate a unique color for each key
        key_to_color = {key: color for key, color in zip(keys, colors)}

        # Clean the extracted data
        extracted_data = {key: [entry["match"] for entry in value] for key, value in matches_for_text.items()}

        # Flatten the matches_for_text dictionary into a list of matches with locations
        all_matches = []
        for key, match_list in matches_for_text.items():
            for match_data in match_list:
                all_matches.append(
                    {"match": match_data["match"], "start": match_data["start"], "end": match_data["end"], "key": key}
                )

        # Sort matches by start position
        all_matches.sort(key=lambda x: x["start"])

        # Build the highlighted text
        highlighted_text_parts = []
        last_end = 0
        for match in all_matches:
            highlight_color = key_to_color.get(match["key"], "#FFFFFF")  # Default to white if key not found

            # Append text before the match (escaped)
            pre_match_text = raw_text[last_end : match["start"]]
            highlighted_text_parts.append(html.escape(pre_match_text))

            # Escape the matched text
            escaped_match = html.escape(match["match"])

            # Create the highlighted text with a span tag
            highlighted_span = f'<span style="background-color: {highlight_color}; color: black; font-weight: bold;">{escaped_match}</span>'
            highlighted_text_parts.append(highlighted_span)

            last_end = match["end"]

        # Append any remaining text after the last match (escaped)
        post_match_text = raw_text[last_end:]
        highlighted_text_parts.append(html.escape(post_match_text))

        # Combine all parts
        highlighted_text = "".join(highlighted_text_parts)

        # Convert extracted data to HTML string with highlighted keys
        extracted_data_html = json_to_html(extracted_data, key_to_color)

        # Generate the dual-pane view with scroll syncing for this text
        sync_scroll_html = f"""<div style="display: flex; margin-bottom: 20px; height: auto;">
    <div id="pane1_{idx}" style="width: 50%; border-right: 1px solid #ddd; padding-right: 10px; display: flex; flex-direction: column;">
        <pre style="flex: 1; margin: 0; overflow-y: auto;">{highlighted_text}</pre>
    </div>
    <div id="pane2_{idx}" style="width: 50%; padding-left: 10px; white-space: pre-wrap; display: flex; flex-direction: column;">
        <div style="flex: 1; margin: 0; overflow-y: auto;">{extracted_data_html}</div>
    </div>
</div>

<script>
window.addEventListener('load', function() {{
    const pre1_{idx} = document.querySelector("#pane1_{idx} pre");
    const pre2_{idx} = document.querySelector("#pane2_{idx} div");

    // Synchronize scrolling
    pre1_{idx}.onscroll = function() {{
        pre2_{idx}.scrollTop = this.scrollTop;
    }};

    pre2_{idx}.onscroll = function() {{
        pre1_{idx}.scrollTop = this.scrollTop;
    }};
}});
</script>"""

        html_outputs.append(sync_scroll_html)

    # Combine all HTML outputs
    return "\n".join(html_outputs)


# Create main tabs for file upload, schema editing, and advanced options
tab1, tab2, tab3, tab4 = st.tabs(["View Configs", "Edit JSON Schema", "Advanced", "Generate Template"])

with tab1:
    # File upload for text data
    uploaded_files = st.file_uploader("Upload config files", accept_multiple_files=True)

    if uploaded_files:
        # Read filenames and content
        filenames = [file.name for file in uploaded_files]
        texts = [file.read().decode("utf-8") for file in uploaded_files]  # Read and store the config contents

        # Store filenames and configs in session state
        if filenames != st.session_state.filenames:
            for regex_key in CONFIG_PATTERNS.keys():
                st.session_state.regexes[regex_key] = generate_data_regex(
                    st.session_state.json_code[regex_key],
                    sum([x.get(regex_key, []) for x in st.session_state.parsed_configs], []),
                )

        st.session_state.filenames = filenames  # Store filenames in session state
        st.session_state.configs = texts  # Store the config contents in session state

        st.session_state.parsed_configs = [
            {k: v for k, v in parse_cisco_config(raw_text).items() if v} for raw_text in texts
        ]

        # For troubleshooting parsed config state
        # with open("fuck.json", "w") as f:
        #     json.dump(st.session_state.parsed_configs, f, indent=4)

        # Create tabs for each config file
        tabs = st.tabs(filenames)

        # Inside your loop over configs and segments
        for i, tab in enumerate(tabs):
            with tab:
                raw_text = st.session_state.configs[i]
                parsed_segments = st.session_state.parsed_configs[i]

                # Create a second row of tabs for the config segments
                segment_keys = list(parsed_segments.keys())
                segment_tabs = st.tabs(segment_keys)

                for j, segment_tab in enumerate(segment_tabs):
                    with segment_tab:
                        segment_name = segment_keys[j]
                        segment_lines = parsed_segments[segment_name]

                        if segment_name != "uncaptured":
                            # Convert segment_lines to a single string if necessary
                            if isinstance(segment_lines, list):
                                segment_text = "\n".join(segment_lines)
                            else:
                                segment_text = segment_lines

                            # Extract data using the updated function
                            extracted_data = find_matches_with_locations(
                                st.session_state.regexes[segment_name], segment_lines
                            )

                            # Clean the extracted data
                            extracted_data_clean = [
                                {key: [entry["match"] for entry in value] for key, value in data_entry.items()}
                                for data_entry in extracted_data
                            ]

                            # Store the cleaned data in the session state
                            filename = st.session_state.filenames[i]
                            st.session_state.extracted_data.setdefault(filename, {})[segment_name] = (
                                extracted_data_clean
                            )

                            html_output = dual_pane_with_highlight(segment_lines, extracted_data)

                            # Display the HTML in Streamlit
                            st.write(html_output, unsafe_allow_html=True)

                        else:
                            # For other segments, just display the raw segment content
                            st.subheader(f"Segment: {segment_name}")
                            st.text_area(
                                f"Content of {segment_name}",
                                value="\n".join(segment_lines),
                                height=300,
                                key=f"{segment_name}-{tab}",
                            )

    # Option to clear uploaded files
    if st.sidebar.button("Clear uploaded files"):
        st.session_state.filenames = []
        st.session_state.configs = []
        st.rerun()

with tab2:
    tab_keys = list(CONFIG_PATTERNS.keys())
    schema_tabs = st.tabs(tab_keys)

    # Display the json code in real-time
    st.write("Enter your schema, or edit the provided one.")

    for i, tab in enumerate(schema_tabs):
        with tab:
            # Editable json text area with syntax highlighting
            json_code = st_ace(
                language="json",
                height=400,
                font_size=14,
                show_gutter=True,
                show_print_margin=False,
                wrap=True,
                value=st.session_state.json_code[tab_keys[i]],
            )

            # Save the edits back to session state
            if json_code != st.session_state.json_code[tab_keys[i]]:
                st.session_state.json_code[tab_keys[i]] = json_code
                st.session_state.data_regex[tab_keys[i]] = generate_data_regex(
                    json_code, sum([x.get(tab_keys[i], []) for x in st.session_state.parsed_configs], [])
                )

with tab3:
    st.session_state.regexes

with tab4:
    # Display the json code in real-time
    st.write("Generate a template!")

    j2llm = GenerateJinja2Task(model_name="gpt-4o")

    tab_keys = list(CONFIG_PATTERNS.keys())
    schema_tabs = st.tabs(tab_keys)
    with st.expander("Confs"):
        st.session_state.parsed_configs

    for i, tab in enumerate(schema_tabs):
        with tab:
            tab_key = tab_keys[i]
            if st.button("Generate Template", key=f"{tab_keys[i]}-generate"):
                expected = [x.get(tab_key, []) for x in st.session_state.parsed_configs]

                # f"# Example {i+1}\n" +
                expected = ["\n".join(x) for x in expected]

                # expected = "\n\n".join(expected)

                data = [x.get(tab_key, []) for x in st.session_state.extracted_data.values()]

                # with st.expander("Prompt"):
                #     st.markdown(
                #         "```\n"
                #         + f"{j2llm.prompt.format_prompt(input_data=data, expected_output=expected).text}".replace(
                #             "```", r"\`\`\`"
                #         )
                #     )

                # NOTE: For troubleshooting
                # with open("temps.json", "w") as f:
                #     json.dump({"expected": expected, "data": data}, f, indent=4)

                with st.spinner("Generating template..."):
                    # NOTE: You can put data ([0], for one device) in a {"data": } key for better results if n=1
                    template = asyncio.run(j2llm.execute(data, expected))
                    st.session_state.templates[tab_keys[i]] = template

                st.markdown(f"```j2\n{st.session_state.templates.get(tab_key)}\n```")

                st.write("Template is " + "Valid! 🟢" if j2llm.validate_syntax(template) else "INVALID! 🛑")

                for i, (fname, sub_data) in enumerate(st.session_state.extracted_data.items()):
                    if tab_key not in sub_data:
                        continue

                    clean_data = {"data": sub_data[tab_key]}

                    # Assuming data is a dict of lists like {'key1': [1, 2], 'key2': [3, 4]}
                    try:
                        # st.write(f"```j2\n{template}```")
                        # st.write(clean_data)

                        rendered = j2llm.render_template(template, clean_data)
                        
                        # st.write(rendered)

                        test_data = st.session_state.parsed_configs[i].get(tab_key, [])

                        test_data = "\n".join(test_data)

                        
                        test_result = all(
                            x in test_data for x in rendered.splitlines()
                        )

                        st.write(f"{fname}:\n```\n{rendered}```\nPassed: {'🟢' if test_result else '🛑'}")
                    except Exception as e:
                        st.write(f"Templating failed:\n{e}")
