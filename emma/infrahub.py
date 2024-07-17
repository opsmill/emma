import os
from enum import Enum
from typing import TYPE_CHECKING, Any, Tuple

import pandas as pd
import streamlit as st
from httpx import HTTPError
from infrahub_sdk import InfrahubClientSync, InfrahubNodeSync
from infrahub_sdk.exceptions import (
    AuthenticationError,
    GraphQLError,
    JsonDecodeError,
    ServerNotReachableError,
    ServerNotResponsiveError,
)
from infrahub_sdk.schema import GenericSchema, NodeSchema

if TYPE_CHECKING:
    from infrahub_sdk.node import Attribute


class InfrahubStatus(str, Enum):
    UNKNOWN = "unknown"
    OK = "ok"
    ERROR = "error"

def get_instance_address() -> str:
    if "infrahub_address" not in st.session_state:
        st.session_state["infrahub_address"] = os.environ.get("INFRAHUB_ADDRESS", "")
    return st.session_state["infrahub_address"]

@st.cache_resource
def get_client(address: str | None = None, branch: str | None = None) -> InfrahubClientSync:
    return InfrahubClientSync(address=address)

def input_infrahub_address():
    with st.sidebar.form(key="input_address_form"):
        new_address = st.text_input(
            label="Enter Infrahub Address",
            value=st.session_state.get("infrahub_address", "")
        )
        submit_address = st.form_submit_button(label="Set Address")
        if submit_address and new_address:
            st.session_state["infrahub_address"] = new_address
            st.rerun()

@st.cache_data
def get_schema(branch: str | None = None):
    client = get_client(branch=branch)
    return client.schema.all(branch=branch)

def get_branches():
    client = get_client()
    return client.branch.all()

def get_version(client: InfrahubClientSync) -> str:
    query = "query { InfrahubInfo { version }}"
    response = client.execute_graphql(query=query, raise_for_error=True)
    return response["InfrahubInfo"]["version"]

def check_reacheability(client: InfrahubClientSync) -> bool:
    try:
        get_version(client=client)
        st.session_state["infrahub_status"] = InfrahubStatus.OK
        return True
    except (
        AuthenticationError,
        GraphQLError,
        HTTPError,
        JsonDecodeError,
        ServerNotReachableError,
        ServerNotResponsiveError
    ) as exc:
        st.session_state["infrahub_error_message"] = str(exc)
        st.session_state["infrahub_status"] = InfrahubStatus.ERROR
        return False

def get_objects_as_df(kind: str, page=1, page_size=20, include_id: bool = True, branch: str | None = None):
    client = get_client()

    objs = client.all(kind=kind, branch=branch)

    df = pd.DataFrame([convert_node_to_dict(obj, include_id=include_id) for obj in objs])
    return df

def convert_node_to_dict(obj: InfrahubNodeSync, include_id: bool = True) -> dict[str, Any]:
    data = {}

    if include_id:
        data["index"] = obj.id or None

    for attr_name in obj._schema.attribute_names:
        attr: Attribute = getattr(obj, attr_name)
        data[attr_name] = attr.value

    return data

def convert_schema_to_dict(
    node: GenericSchema | NodeSchema,
) -> dict[str, Any]:
    """
    Convert a schema item (GenericSchema or NodeSchema) to a dictionary.

    Parameters:
        item (GenericSchema | NodeSchema): The schema item to convert.
        include_id (bool): Whether to include the ID of the item.

    Returns:
        Dict[str, Any]: The converted dictionary.
    """
    data = {
        "name": node.name,
        "namespace": node.namespace,
        "label": node.label,
        "description": node.description,
        "used_by": ", ".join(node.used_by) if hasattr(node, "used_by") else None,
        "inherit_from": ", ".join(node.inherit_from) if hasattr(node, "inherit_from") else None,
        "attributes": [],
        "relationships": [],
    }

    for attr in node.attributes:
        attr_dict = {
            "name": attr.name,
            "label": attr.label,
            "kind": attr.kind,
            "description": attr.description,
            "default_value": str(attr.default_value),
            "optional": attr.optional,
            "unique": attr.unique,
            "branch": attr.branch,
        }
        data["attributes"].append(attr_dict)

    for rel in node.relationships:
        rel_dict = {
            "name": rel.name,
            "peer": rel.peer,
            "description": rel.description,
            "kind": rel.kind,
            "cardinality": rel.cardinality,
            "branch": rel.branch,
        }
        data["relationships"].append(rel_dict)

    return data

def dict_to_df(data: dict[str, Any]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Convert a dictionary of schema data to Pandas DataFrames for main information, attributes, and relationships.

    Parameters:
        data (dict[str, Any]): The schema data as a dictionary.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]: A tuple containing the main information, attributes,
        and relationships dataframes.
    """
    inherit_or_use_label = "Inherit from" if data["inherit_from"] else "Used by"
    inherit_or_use_value = data["inherit_from"] if data["inherit_from"] else data["used_by"]

    main_info = {
        "Name": [data["name"]],
        "Namespace": [data["namespace"]],
        "Label": [data["label"]],
        "Description": [data["description"]],
        inherit_or_use_label: [inherit_or_use_value],
    }

    attributes_df = pd.DataFrame(data["attributes"])
    relationships_df = pd.DataFrame(data["relationships"])

    main_info_df = pd.DataFrame(main_info)

    return main_info_df, attributes_df, relationships_df
