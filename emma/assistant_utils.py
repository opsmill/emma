from typing import Any, Dict, List

import yaml


# YAML generator with custom string presenter
def generate_yaml(conversation: List[Dict[str, Any]]) -> str:
    """Generate YAML from a conversation list.

    Args:
        conversation: List of conversation dictionaries.

    Returns:
        YAML formatted string.
    """

    def str_presenter(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
        if "\n" in data:
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)

    yaml.add_representer(str, str_presenter)
    return yaml.dump(conversation, default_flow_style=False)
