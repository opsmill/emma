import asyncio
import colorsys
import html
from enum import Enum
from typing import Any, Dict

import openai
import pandas as pd
import regex as re
import streamlit as st
from infrahub_sdk import NodeSchema
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.utils import compare_lists
from pulse.tasks.parse_config.task import GenerateDataRegexTask
from pydantic import BaseModel

from emma.infrahub import get_client

api_key = "EmmaDefaultAuthMakingInfrahubEasierToUse!!!11"

openai.base_url = "https://emma.opsmill.cloud/v1"
openai.api_key = api_key

llm = GenerateDataRegexTask(model_name="gpt-4o-mini")


# Define regex patterns to capture raw segments
CISCO_CONFIG_PATTERNS = {
    "vlan": r"^vlan\s+\d+[\s\S]+?(?=^vlan\s+\d+|^!|^$)",
    "ospf": r"^router\sospf\s\d+[\s\S]+?(?=^router\s\S+|^!|^$)",
    "eigrp": r"^router\seigrp\s\d+[\s\S]+?(?=^router\s\S+|^!|^$)",
    "bgp": r"^router\sbgp\s\d+[\s\S]+?(?=^router\sbgp\s\d+|^!|^$)",
    "standard_acl": r"^access-list\s\d+[\s\S]+?(?=^access-list\s\d+|^!|^$)",
    "extended_acl": r"^access-list\s\d+\sextended[\s\S]+?(?=^access-list\s\d+|^!|^$)",
    "prefix_list": r"^ip\sprefix-list\s\S+[\s\S]+?(?=^ip\sprefix-list\s\S+|^!|^$)",
    "route_map": r"^route-map\s\S+[\s\S]+?(?=^route-map\s\S+|^!|^$)",
    "ntp": r"^ntp\sserver\s\S+[\s\S]+?(?=^ntp\sserver\s\S+|^!|^$)",
    "snmp": r"^snmp-server\s.*$",
    "logging": r"^logging\s\S+[\s\S]+?(?=^logging\s\S+|^!|^$)",
    "line_vty": r"^line\svty\s\d+\s\d+[\s\S]+?(?=^line\s\S+|^!|^$)",
    "line_console": r"^line\scon\s\d+[\s\S]+?(?=^line\s\S+|^!|^$)",
    "line_aux": r"^line\saux\s\d+[\s\S]+?(?=^line\saux\s\d+|^!|^$)",
    "class_map": r"^class-map\s\S+[\s\S]+?(?=^class-map\s\S+|^!|^$)",
    "policy_map": r"^policy-map\s\S+[\s\S]+?(?=^policy-map\s\S+|^!|^$)",
    "service_policy": r"^service-policy\s\S+[\s\S]+?(?=^service-policy\s\S+|^!|^$)",
    "aaa": r"^aaa\s\S+[\s\S]+?(?=^aaa\s\S+|^!|^$)",
    "vrf": r"^ip\svrf\s\S+[\s\S]+?(?=^ip\svrf\s\S+|^!|^$)",
    "banner": r"^banner\s\S+[\s\S]+?(?=^banner\s\S+|^!|^$)",
    "dns_settings": r"^(ip domain-lookup|ip domain-name\s+\S+|ip name-server\s+[\d\.\s]+(?:use-vrf\s+\S+)?)",
    "interface": r"^interface\s+\S+[\s\S]+?(?=^interface\s+\S+|^!|^$)",
}

JUNOS_CONFIG_PATHS = {
    "system": ["system"],
    "ntp": ["system", "ntp"],
    "dns": ["system", "name-server"],
    "services": ["system", "services"],
    "interfaces": ["interfaces"],
    "protocols": ["protocols"],
    "bgp": ["protocols", "bgp"],
    "ospf": ["protocols", "ospf"],
    "isis": ["protocols", "isis"],
    "routing_options": ["routing-options"],
    "policy_options": ["policy-options"],
    "firewall": ["firewall"],
    "security": ["security"],
    "zones": ["security", "zones"],
    "snmp": ["snmp"],
    "routing_instances": ["routing-instances"],
    "chassis": ["chassis"],
}


class MessageSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Message(BaseModel):
    severity: MessageSeverity = MessageSeverity.INFO
    message: str


GROUP_QUERY = """{
	CoreStandardGroup {
		edges {
			node {
				display_label
				group_type { value }
				members {
					edges {
						node {
							display_label
							__typename
						}
					}
				}
			}
		}
	}
}"""


# Function to parse Cisco configs and return segments
def parse_cisco_config(config_text):
    raw_segments = {}
    captured_lines = []

    for label, pattern in CISCO_CONFIG_PATTERNS.items():
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
        prompt = llm.format_prompt(config_segments, schema)
        regexes = asyncio.run(llm.execute(config_segments, schema))
        return prompt, {x.name: x.regex for x in regexes if x.regex}


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
            highlighted_span = (
                f'<span style="background-color: {highlight_color};'
                f'color: black; font-weight: bold;">{escaped_match}</span>'
            )
            highlighted_text_parts.append(highlighted_span)

            last_end = match["end"]

        # Append any remaining text after the last match (escaped)
        post_match_text = raw_text[last_end:]
        highlighted_text_parts.append(html.escape(post_match_text))

        # Combine all parts
        highlighted_text = "".join(highlighted_text_parts)

        # Convert extracted data to HTML string with highlighted keys
        extracted_data_html = json_to_html(extracted_data, key_to_color) if extracted_data else ""

        # Generate the dual-pane view with scroll syncing for this text
        sync_scroll_html = f"""<div style="display: flex; margin-bottom: 20px; height: auto;">
    <div id="pane1_{idx}" style="width: 50%; border-right: 1px solid #ddd; padding-right: 10px; display: flex; flex-direction: column;">
        <pre style="flex: 1; margin: 0; overflow-y: auto; white-space: pre-wrap; background-color: #f4f4f4; padding: 10px; border-radius: 4px;">{highlighted_text}</pre>
    </div>
    <div id="pane2_{idx}" style="width: 50%; padding-left: 10px; white-space: pre-wrap;
    display: flex; flex-direction: column;">
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


def display_segments(filenames, parsed_configs, regexes=None, raw=False, highlight=True):
    """
    Function to display configuration segments in a tabbed interface in Streamlit.

    Args:
        filenames (list): List of config filenames.
        configs (list): List of raw config file contents.
        parsed_configs (list): List of parsed config segments for each file.
        regexes (dict, optional): Dictionary of regex patterns for extracting data from config segments.
                                  Defaults to None.
        raw (bool): If True, disables regex extraction and shows raw config segments. Defaults to False.
        highlight (bool): If True, enables highlighting of regex matches. Defaults to True.
    """
    # Create tabs for each config file
    tabs = st.tabs(filenames)

    # Loop over configs and segments
    for i, tab in enumerate(tabs):
        with tab:
            parsed_segments = parsed_configs[i]

            # Create a second row of tabs for the config segments
            segment_keys = list(parsed_segments.keys())
            segment_tabs = st.tabs(segment_keys)

            for j, segment_tab in enumerate(segment_tabs):
                with segment_tab:
                    segment_name = segment_keys[j]
                    segment_lines = parsed_segments[segment_name]

                    if not segment_lines:
                        st.write("No data found.")
                        continue

                    st.subheader(f"Segment: {segment_name}")

                    if isinstance(segment_lines, str):
                        lines = segment_lines
                    else:
                        lines = "\n".join(segment_lines) or "No data found."

                    # If raw mode is enabled, show raw content
                    if raw:
                        st.markdown(
                            "Content of {segment_name}\n```\n{lines}\n```".format(
                                segment_name=segment_name, lines=lines
                            ),
                        )
                    elif highlight and regexes:
                        # Use regex and highlighting if both are enabled and regexes provided
                        extracted_data = find_matches_with_locations(regexes, segment_lines)

                        extracted_data_clean = [
                            {key: [entry["match"] for entry in value][0] for key, value in data_entry.items() if value}
                            for data_entry in extracted_data
                            if data_entry
                        ]

                        filename = filenames[i]
                        st.session_state.extracted_data.setdefault(filename, {})[segment_name] = extracted_data_clean

                        # Highlight with dual pane
                        html_output = dual_pane_with_highlight(segment_lines, extracted_data)

                        # Display the HTML in Streamlit
                        st.write(html_output, unsafe_allow_html=True)
                    else:
                        # No highlighting, just show plain text with regex processing

                        st.markdown(
                            "Content of {segment_name}\n```\n{lines}\n```".format(
                                segment_name=segment_name, lines=lines
                            ),
                        )


def validate_if_df_is_compatible_with_schema(df: pd.DataFrame, target_schema: NodeSchema, schema: str) -> list[Message]:
    errors = []

    # Get DataFrame columns
    df_columns = list(df.columns.values)

    # Check for missing mandatory columns (non-enum related)
    _, _, missing_mandatory = compare_lists(list1=df_columns, list2=target_schema.mandatory_input_names)
    for item in missing_mandatory:
        errors.append(
            Message(severity=MessageSeverity.ERROR, message=f"Mandatory column for {schema!r} missing: {item!r}")
        )

    # Check for additional columns not in schema
    _, additional, _ = compare_lists(
        list1=df_columns, list2=target_schema.relationship_names + target_schema.attribute_names
    )
    for item in additional:
        errors.append(Message(severity=MessageSeverity.WARNING, message=f"Unable to map {item!r} for {schema!r}"))

    # Check if any enum fields contain invalid values, including None
    for column in df_columns:
        # Check if it's an enum field and validate
        for attr in target_schema.attributes:
            if attr.name == column and attr.choices:
                valid_options = [choice["name"] for choice in attr.choices if choice["name"] is not None]

                # Check if values in the column are valid enum options (including catching None)
                invalid_values = df[~df[column].isin(valid_options)][column]
                if not invalid_values.empty:
                    errors.append(
                        Message(
                            severity=MessageSeverity.ERROR,
                            message=f"Invalid value for '{column}' in {schema!r}. Must be one of {valid_options}",
                        )
                    )

    # Check for invalid cardinality on relationships
    for column in df_columns:
        if column in target_schema.relationship_names:
            for relationship_schema in target_schema.relationships:
                if relationship_schema.name == column and relationship_schema.cardinality == "many":
                    errors.append(
                        Message(
                            severity=MessageSeverity.ERROR,
                            message=f"Only relationships with a cardinality of one are supported: {column!r}",
                        )
                    )

    return errors


def dict_remove_nan_values(dictionary: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in dictionary.items() if not pd.isnull(v)}


def upload_data(df: pd.DataFrame, schema_kind: str, hostname: str, branch: str) -> int:
    client = get_client(branch=branch)
    nbr_errors = 0

    for index, row in df.iterrows():
        data = dict_remove_nan_values(dict(row))
        node = client.create(kind=schema_kind, **data)
        try:
            node.save(allow_upsert=True)
            including_device = client.get(kind="InfraDevice", name__value=hostname)
            node.add_relationships(relation_to_update="in_config", related_nodes=[including_device.id])

        except GraphQLError:
            nbr_errors += 1

    return nbr_errors


def paginate_list(items, page_size, page_number):
    """Simple pagination for a list."""
    start_index = page_number * page_size
    end_index = start_index + page_size
    return items[start_index:end_index]


def parse_junos_config(config_text):
    def add_to_dict(path, value, config_dict):
        current = config_dict
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[path[-1]] = value

    config_dict = {}
    path = []

    # Remove comments and unnecessary whitespaces
    config_text = re.sub(r"/\*.*?\*/", "", config_text, flags=re.DOTALL)
    config_text = re.sub(r"//.*", "", config_text)
    config_text = config_text.strip()

    for line in config_text.splitlines():
        clean_line = line.strip()

        if clean_line == "" or clean_line.startswith("#"):
            continue  # Ignore empty lines and comments

        # Detect block openings
        if clean_line.endswith("{"):
            key = clean_line.rstrip("{").strip()
            path.append(key)

        # Detect block closures
        elif clean_line == "}":
            path.pop()

        # Handle key-value pairs
        elif clean_line.endswith(";"):
            key_value = clean_line.rstrip(";").split(maxsplit=1)
            if len(key_value) == 1:
                key_value.append(None)  # Handle cases like "disable;"
            add_to_dict(path + [key_value[0]], key_value[1], config_dict)

    if config_dict:
        return config_dict
    else:
        return {"Error": ["Failed to parse config."]}


def junos_dict_to_config(config_dict, indent=0):
    indent_space = 4  # Junos typically uses 4 spaces per indent level

    def format_line(key, value, indent_level):
        return " " * indent_level + f"{key} {value};\n"

    def format_block(key, content, indent_level):
        return " " * indent_level + f"{key} {{\n{content}{' ' * indent_level}}}\n"

    config_text = ""

    if isinstance(config_dict, list):
        config_dict = {d["key"]: d["value"] for d in config_dict}

    if isinstance(config_dict, dict):
        for key, value in config_dict.items():
            if isinstance(value, dict):
                # For nested dicts, format each as a block
                nested_content = junos_dict_to_config(value, indent + indent_space)
                config_text += format_block(key, nested_content, indent)
            elif isinstance(value, list):
                # For lists, format each item individually
                for item in value:
                    config_text += (
                        format_line(key, item, indent) if isinstance(item, str) else junos_dict_to_config(item, indent)
                    )
            else:
                # Simple key-value pairs
                config_text += format_line(key, value, indent)
    elif isinstance(config_dict, str):
        # Direct string if input is a string instead of a dict
        config_text += config_dict + "\n"

    return config_text


def extract_junos_segments(config_dict, path_map=JUNOS_CONFIG_PATHS):
    raw_segments = {}
    captured_paths = set()  # Track paths we've captured to avoid duplicates

    # Helper function to retrieve nested keys and maintain structure
    def get_nested_value(d, keys):
        current = d
        nested_result = {}
        temp = nested_result

        for i, key in enumerate(keys):
            if isinstance(current, dict) and key in current:
                if i == len(keys) - 1:
                    temp[key] = current[key]  # Final key gets the actual value
                else:
                    temp[key] = {}
                    temp = temp[key]  # Go deeper into the nested structure
                current = current[key]
            else:
                return None
        return nested_result

    # Traverse path_map to extract corresponding segments from config_dict
    for label, path_list in path_map.items():
        segment = get_nested_value(config_dict, path_list)
        if segment:
            # If it's a list or dict, we convert each item to config text strings
            if isinstance(segment, list):
                raw_segments[label] = [junos_dict_to_config(item) for item in segment]
            elif isinstance(segment, dict):
                # Break down each entry into separate strings
                raw_segments[label] = [junos_dict_to_config({k: v}) for k, v in segment.items()]
            captured_paths.add(tuple(path_list))

    # Collect uncaptured paths for completeness/debugging
    uncaptured_segments = []

    def traverse_and_capture(d, path=()):
        if isinstance(d, dict):
            for key, value in d.items():
                new_path = path + (key,)
                if new_path not in captured_paths:
                    traverse_and_capture(value, new_path)
        elif path not in captured_paths:
            uncaptured_segments.append(d)

    traverse_and_capture(config_dict)
    raw_segments["uncaptured"] = uncaptured_segments

    return raw_segments
