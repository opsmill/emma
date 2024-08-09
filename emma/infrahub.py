import os
from enum import Enum
from typing import TYPE_CHECKING, Any, List, Tuple

import pandas as pd
import streamlit as st
from httpx import HTTPError
from infrahub_sdk import Config, InfrahubClientSync, InfrahubNodeSync, MainSchemaTypes, RelationshipKind
from infrahub_sdk.branch import BranchData
from infrahub_sdk.exceptions import (
    AuthenticationError,
    GraphQLError,
    JsonDecodeError,
    ServerNotReachableError,
    ServerNotResponsiveError,
)
from infrahub_sdk.schema import GenericSchema, NodeSchema, SchemaLoadResponse
from pydantic import BaseModel
from st_pages import get_pages, get_script_run_ctx

if TYPE_CHECKING:
    from infrahub_sdk.node import Attribute, RelatedNodeSync


class InfrahubStatus(str, Enum):
    UNKNOWN = "unknown"
    OK = "ok"
    ERROR = "error"


class SchemaCheckResponse(BaseModel):
    success: bool
    response: dict | None = None


def get_instance_address() -> str | None:
    if "infrahub_address" not in st.session_state or not st.session_state.infrahub_address:
        st.session_state.infrahub_address = os.environ.get("INFRAHUB_ADDRESS")
    return st.session_state.infrahub_address


def get_instance_branch() -> str:
    if "infrahub_branch" not in st.session_state:
        st.session_state.infrahub_branch = None
    return st.session_state.infrahub_branch


@st.cache_resource
def get_client(address: str | None = None, branch: str = "main") -> InfrahubClientSync:  # pylint: disable=unused-argument
    return InfrahubClientSync(address=address, config=Config(default_branch=branch))


@st.cache_data
def get_schema(branch: str | None = None) -> dict[str, MainSchemaTypes] | None:
    client = get_client(branch=branch)
    if check_reachability(client=client):
        return client.schema.all(branch=branch)
    return None

def get_node_schema(kind: str, branch: str | None = None) -> MainSchemaTypes | None:
    client = get_client(branch=branch)
    if check_reachability(client=client):
        return client.schema.get(kind=kind)
    return None


def get_candidate_related_nodes(schema_node: MainSchemaTypes, branch: str | None = None) -> dict[str, List[InfrahubNodeSync]]:
    client = get_client(branch=branch)
    candidates = {}
    if check_reachability(client=client):
        relationships = [
            relationship.peer
            for relationship in schema_node.relationships
            if relationship.kind == RelationshipKind.GENERIC
        ]

        for relation in relationships:
            nodes = client.all(kind=relation)
            candidates[relation] = nodes

    return candidates

def load_schema(branch: str, schemas: list[dict] | None = None) -> SchemaLoadResponse | None:
    client = get_client(branch=branch)
    if check_reachability(client=client):
        return client.schema.load(schemas, branch)
    return None


def check_schema(branch: str, schemas: list[dict] | None = None) -> SchemaCheckResponse | None:
    client = get_client(branch=branch)
    if check_reachability(client=client):
        success, response = client.schema.check(schemas=schemas, branch=branch)
        schema_check = SchemaCheckResponse(success=success, response=response)
        return schema_check

    return None

def get_branches(address: str | None = None) -> dict[str, BranchData] | None:
    client = get_client(address=address)
    if check_reachability(client=client):
        return client.branch.all()
    return None


def create_branch(branch_name: str) -> BranchData | None:
    client = get_client()
    if check_reachability(client=client):
        return client.branch.create(branch_name=branch_name)
    return None


def get_version(client: InfrahubClientSync) -> str:
    query = "query { InfrahubInfo { version }}"
    response = client.execute_graphql(query=query, raise_for_error=True)
    return response["InfrahubInfo"]["version"]


def check_reachability(client: InfrahubClientSync) -> bool:
    try:
        get_version(client=client)
        st.session_state.infrahub_status = InfrahubStatus.OK
        return True
    except (
        AuthenticationError,
        GraphQLError,
        HTTPError,
        JsonDecodeError,
        ServerNotReachableError,
        ServerNotResponsiveError,
    ) as exc:
        st.session_state.infrahub_error_message = str(exc)
        st.session_state.infrahub_status = InfrahubStatus.ERROR
        return False


def get_objects_as_df(kind: str, include_id: bool = True, branch: str | None = None) -> pd.DataFrame | None:
    client = get_client(branch=branch)
    if not check_reachability(client=client):
        return None

    node_schema = client.schema.get(kind=kind)
    export_relationships = get_relationships_to_export(node_schema=node_schema)

    objs = client.all(kind=kind, branch=branch)

    df = pd.DataFrame(
        [convert_node_to_dict(obj, include_id=include_id, export_relationships=export_relationships) for obj in objs]
    )
    return df


def get_relationships_to_export(node_schema: NodeSchema) -> List[str]:
    export_relationships = []
    for relationship in node_schema.relationships:
        if relationship.cardinality == "one":
            export_relationships.append(relationship.name)
    return export_relationships


def convert_node_to_dict(
    obj: InfrahubNodeSync, export_relationships: List[str], include_id: bool = True
) -> dict[str, Any]:
    data = {}

    if include_id:
        data["index"] = obj.id or None

    for attr_name in obj._schema.attribute_names:
        attr: Attribute = getattr(obj, attr_name)
        data[attr_name] = attr.value

    for rel_name in obj._schema.relationship_names:
        if rel_name in export_relationships:
            rel: RelatedNodeSync = getattr(obj, rel_name)
            if rel.initialized:
                rel.fetch()
                data[rel_name] = rel.peer.hfid[0] if rel.peer.hfid and len(rel.peer.hfid) == 1 else rel.peer.id
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


def get_current_page():
    """This is a snippet from Zachary Blackwood using his st_pages package per
    https://discuss.streamlit.io/t/how-can-i-learn-what-page-i-am-looking-at/56980
    for getting the page name without having the script run twice as it does using
    """
    pages = get_pages("")
    ctx = get_script_run_ctx()
    try:
        current_page = pages[ctx.page_script_hash]
    except KeyError:
        current_page = [p for p in pages.values() if p["relative_page_hash"] == ctx.page_script_hash][0]
    return current_page["page_name"]


def handle_reachability_error(redirect: bool | None = True):
    st.toast(icon="🚨", body=f"Error: {st.session_state.infrahub_error_message}")
    st.cache_data.clear()  # TODO: Maybe something less violent ?
    if not redirect:
        st.stop()
    current_page = get_current_page()
    if current_page != "main":
        st.switch_page("main.py")
