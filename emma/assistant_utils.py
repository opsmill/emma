from typing import Dict, List

import yaml


# YAML generator with custom string presenter
def generate_yaml(conversation: List[Dict]):
    def str_presenter(dumper, data):
        if "\n" in data:
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)

    yaml.add_representer(str, str_presenter)
    return yaml.dump(conversation, default_flow_style=False)
