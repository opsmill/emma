import os
import uuid
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Tuple

import pandas as pd
import streamlit as st
from graphql import get_introspection_query
from httpx import HTTPError
from infrahub_sdk import Config, InfrahubClientSync
from infrahub_sdk.branch import BranchData
from infrahub_sdk.exceptions import (
    AuthenticationError,
    GraphQLError,
    JsonDecodeError,
    ServerNotReachableError,
    ServerNotResponsiveError,
)
from infrahub_sdk.node import InfrahubNodeSync, RelatedNodeSync, RelationshipManagerSync
from infrahub_sdk.schema import GenericSchema, MainSchemaTypes, NodeSchema, SchemaLoadResponse
from infrahub_sdk.utils import find_files
from infrahub_sdk.yaml import SchemaFile
from pydantic import BaseModel
from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit.source_util import get_pages

if TYPE_CHECKING:
    from infrahub_sdk.node import Attribute


class InfrahubStatus(str, Enum):
    UNKNOWN = "unknown"
    OK = "ok"
    ERROR = "error"


class SchemaCheckResponse(BaseModel):
    success: bool
    response: dict | None = None


class FileNotValidError(Exception):
    def __init__(self, name: str, message: str = ""):
        self.message = message or f"Cannot parse '{name}' content."
        super().__init__(self.message)


def is_current_schema_empty() -> bool:
    DEFAULT_NAMESPACES = ["Core", "Profile", "Builtin", "Ipam", "Lineage"]

    # FIXME: Here the fact that the schema is cached creates issue
    # e.g. if I trash the schema on Infrahub side I need to reboot emma for this to be taken into account...
    branch: str = get_instance_branch()
    if branch is None:
        branch = "main"
    schema: dict[str, Any] | None = fetch_schema(branch)
    # FIXME: Here the fact that the schema is cached creates issue

    result: bool = True

    if schema is not None:
        for node in schema.values():
            if node.namespace not in DEFAULT_NAMESPACES:
                result = False
                break

    return result


def get_schema_library_path() -> str | None:
    if "schema_library_path" not in st.session_state or not st.session_state.schema_library_path:
        st.session_state.schema_library_path = os.environ.get("SCHEMA_LIBRARY_PATH")
    return st.session_state.schema_library_path


def get_instance_address() -> str | None:
    if "infrahub_address" not in st.session_state or not st.session_state.infrahub_address:
        st.session_state.infrahub_address = os.environ.get("INFRAHUB_ADDRESS")
    return st.session_state.infrahub_address


def get_instance_branch() -> str:
    if "infrahub_branch" not in st.session_state:
        st.session_state.infrahub_branch = None
    return st.session_state.infrahub_branch


@st.cache_resource
def get_client(address: str | None = None, branch: str | None = None) -> InfrahubClientSync:  # pylint: disable=unused-argument
    return InfrahubClientSync(address=address, config=Config(timeout=60))


@st.cache_data
def get_schema(branch: str | None = None) -> dict[str, MainSchemaTypes] | None:
    client = get_client(branch=branch)
    if check_reachability(client=client):
        return client.schema.all(branch=branch)
    return None


def fetch_schema(branch: str | None = None) -> dict[str, MainSchemaTypes] | None:
    client = get_client(branch=branch)
    if check_reachability(client=client):
        return client.schema.fetch(branch=branch)
    return None


@st.cache_data
def get_gql_schema(branch: str | None = None) -> dict[str, Any] | None:
    client = get_client(branch=branch)
    schema_query = get_introspection_query()
    return client.execute_graphql(schema_query)


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

    objs = client.all(kind=kind, branch=branch, populate_store=True, prefetch_relationships=True)

    df = pd.DataFrame(
        [convert_node_to_dict(obj, include_id=include_id) for obj in objs]
    )
    return df


def convert_node_to_dict(
    obj: InfrahubNodeSync, include_id: bool = True
) -> dict[str, Any]:
    data = {}

    if include_id:
        data["index"] = obj.id or None

    for attr_name in obj._schema.attribute_names:
        attr: Attribute = getattr(obj, attr_name)
        data[attr_name] = attr.value

    for rel_name in obj._schema.relationship_names:
        rel = getattr(obj, rel_name)
        if rel and isinstance(rel, RelatedNodeSync):
            if rel.initialized:
                rel.fetch()
                related_node = obj._client.store.get(key=rel.peer.id, raise_when_missing=False)
                data[rel_name] = (
                    related_node.get_human_friendly_id_as_string(include_kind=False) if related_node.hfid else related_node.id
                )
        elif rel and isinstance(rel, RelationshipManagerSync):
            peers: List[dict[str, Any]] = []
            # FIXME: Seem dirty
            if not rel.initialized:
                rel.fetch()
            for peer in rel.peers:
                # TODO: Should we use the store to speed things up ? Will the HFID be populated ?
                related_node = obj._client.store.get(key=peer.id, raise_when_missing=False)
                if not related_node:
                    peer.fetch()
                    related_node = peer.peer
                peers.append(
                    related_node.get_human_friendly_id_as_string(include_kind=False)
                    if related_node.hfid
                    else related_node.id
                )
            data[rel_name] = peers
    return data


# This is coming from https://github.com/opsmill/infrahub/blob/develop/python_sdk/infrahub_sdk/ctl/schema.py#L33
# TODO: Maybe move it somewhere else ...
def load_schemas_from_disk(schemas: list[Path]) -> list[SchemaFile]:
    schemas_data: list[SchemaFile] = []
    for schema in schemas:
        if schema.is_file():
            schema_file = SchemaFile(location=schema)
            schema_file.load_content()
            schemas_data.append(schema_file)
        elif schema.is_dir():
            files = find_files(extension=["yaml", "yml", "json"], directory=schema)
            for item in files:
                schema_file = SchemaFile(location=item)
                schema_file.load_content()
                schemas_data.append(schema_file)
        else:
            raise FileNotValidError(name=str(schema), message=f"Schema path: {schema} does not exist!")

    return schemas_data


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
        "inherit_from": (", ".join(node.inherit_from) if hasattr(node, "inherit_from") else None),
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


def is_feature_enabled(feature_name: str) -> bool:
    """Feature flags implementation"""
    feature_flags = {}
    feature_flags_env = os.getenv("EMMA_FEATURE_FLAGS", "")
    if feature_flags_env:
        for feature in feature_flags_env.split(","):
            feature_flags[feature.strip()] = True
    return feature_flags.get(feature_name, False)


def run_gql_query(query: str, branch: str | None = None) -> dict[str, MainSchemaTypes]:
    client = get_client(branch=branch)
    return client.execute_graphql(query, raise_for_error=False)


def is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


# Could be move to the SDK later on
def parse_hfid(hfid: str) -> List[str]:
    """Parse a single HFID string into its components if it contains '__'."""
    return hfid.split("__") if "__" in hfid else [hfid]
