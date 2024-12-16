import asyncio
import os
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Tuple

import pandas as pd
import streamlit as st
from httpx import HTTPError
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.batch import InfrahubBatch
from infrahub_sdk.branch import BranchData
from infrahub_sdk.exceptions import (
    AuthenticationError,
    GraphQLError,
    JsonDecodeError,
    ServerNotReachableError,
    ServerNotResponsiveError,
)
from infrahub_sdk.node import (
    InfrahubNode,
    RelatedNode,
    RelationshipManager,
)
from infrahub_sdk.schema import GenericSchema, MainSchemaTypes, NodeSchema, SchemaLoadResponse
from infrahub_sdk.utils import find_files
from infrahub_sdk.yaml import SchemaFile
from pydantic import BaseModel

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


def run_async(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Check if an event loop is already running
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No event loop, run the async function with asyncio.run
            return asyncio.run(func(*args, **kwargs))

        # If an event loop is running, run the coroutine and await its result
        if loop.is_running():
            coroutine = func(*args, **kwargs)
            return asyncio.run_coroutine_threadsafe(coroutine, loop).result()

        return loop.run_until_complete(func(*args, **kwargs))

    return wrapper


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


async def convert_node_to_dict(obj: InfrahubNode, include_id: bool = True) -> dict[str, Any]:
    data = {}

    if include_id:
        data["index"] = obj.id or None

    for attr_name in obj._schema.attribute_names:
        attr: Attribute = getattr(obj, attr_name)
        data[attr_name] = attr.value

    for rel_name in obj._schema.relationship_names:
        rel = getattr(obj, rel_name)
        if rel and isinstance(rel, RelatedNode):
            if rel.initialized:
                await rel.fetch()
                related_node = obj._client.store.get(key=rel.peer.id, raise_when_missing=False)
                data[rel_name] = (
                    related_node.get_human_friendly_id_as_string(include_kind=True)
                    if related_node.hfid
                    else related_node.id
                )
        elif rel and isinstance(rel, RelationshipManager):
            peers: List[dict[str, Any]] = []
            if not rel.initialized:
                await rel.fetch()
            for peer in rel.peers:
                # FIXME: We are using the store to avoid doing to many queries to Infrahub
                # but we could end up doing store+infrahub if the store is not populated
                related_node = obj._client.store.get(key=peer.id, raise_when_missing=False)
                if not related_node:
                    await peer.fetch()
                    related_node = peer.peer
                peers.append(
                    related_node.get_human_friendly_id_as_string(include_kind=True)
                    if related_node.hfid
                    else related_node.id
                )
            data[rel_name] = peers
    return data


# This is coming from https://github.com/opsmill/infrahub-sdk-python/blob/e9631aef895547f4b8337d6e174063338acbaf76/infrahub_sdk/yaml.py#L60
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


async def get_client_async(address: str | None = None, branch: str | None = None) -> InfrahubClient:
    if branch:
        return InfrahubClient(address=address, config=Config(timeout=60, default_branch=branch))
    return InfrahubClient(address=address, config=Config(timeout=60))


@st.cache_data
def get_cached_schema(branch: str | None = None) -> dict[str, MainSchemaTypes] | None:
    return asyncio.run(get_schema_async(branch=branch))


async def get_schema_async(branch: str | None = None) -> dict[str, MainSchemaTypes] | None:
    client: InfrahubClient = await get_client_async()
    if await check_reachability_async(client=client):
        return await client.schema.all(branch=branch)
    return None


@run_async
async def create_and_save(kind: str, data: dict, branch: str):
    node = None
    client: InfrahubClient = await get_client_async()
    if await check_reachability_async(client=client):
        try:
            node = await client.create(kind=kind, branch=branch, **data)
            await node.save(allow_upsert=True)
            st.success(f"{node.id} created with success (with {data})")
        except ValueError as exc:
            st.error(f"Failed to create: [{kind}] '{data}'. Error: {exc}")
            raise
        except GraphQLError as exc:
            st.error(f"Failed to create: [{kind}] '{data}'. Error: {exc}")
            raise

    return node


@run_async
async def create_and_add_to_batch(  # noqa: PLR0913, PLR0917  # pylint: disable=too-many-arguments
    client: InfrahubClient,
    branch: str,
    kind_name: str,
    data: dict,
    batch: InfrahubBatch,
    allow_upsert: bool = True,
) -> InfrahubNode:
    """Creates an object and adds it to a batch for deferred saving."""
    # client: InfrahubClient = await get_client_async()
    try:
        obj = await client.create(branch=branch, kind=kind_name, data=data)
        batch.add(task=obj.save, allow_upsert=allow_upsert, node=obj)
        return obj
    except ValueError as exc:
        st.error(f"Failed to create: [{kind_name}] '{data}'. Error: {exc}")
        raise


@run_async
async def execute_batch(batch: InfrahubBatch) -> None:
    """Executes a batch and provides feedback for each task."""
    try:
        async for node, _ in batch.execute():
            object_reference = None
            if node.hfid:
                object_reference = node.get_human_friendly_id_as_string()
            elif node._schema.default_filter:
                accessors = node._schema.default_filter.split("__")
                object_reference = ""

                for i, accessor in enumerate(accessors):
                    value = getattr(node, accessor).value
                    object_reference += value
                    if i < len(accessors) - 1:
                        object_reference += "__"
            if object_reference:
                st.success(f"Created: [{node._schema.kind}] '{object_reference}'")
            else:
                st.success(f"Created: [{node._schema.kind}]")
    except GraphQLError as exc:
        st.error(f"Batch execution failed due to GraphQL error: {exc}")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        st.error(f"Batch execution failed due to unexpected error: {exc}")


async def get_version_async(client: InfrahubClient) -> str:
    query = "query { InfrahubInfo { version }}"
    response = await client.execute_graphql(query=query, raise_for_error=True)
    return response["InfrahubInfo"]["version"]


async def check_reachability_async(client: InfrahubClient) -> bool:
    try:
        await get_version_async(client=client)
        st.session_state.infrahub_status = InfrahubStatus.OK
        st.session_state.infrahub_error_message = ""
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


@run_async
async def fetch_schema(branch: str | None = None) -> dict[str, MainSchemaTypes] | None:
    client: InfrahubClient = await get_client_async()
    if await check_reachability_async(client=client):
        return await client.schema.all(branch=branch)
    return None


@run_async
async def run_gql_query(query: str, branch: str | None = None) -> dict[str, MainSchemaTypes]:
    client: InfrahubClient = get_client_async()
    return await client.execute_graphql(query, branch_name=branch, raise_for_error=False)


@run_async
async def load_schema(branch: str, schemas: list[dict] | None = None) -> SchemaLoadResponse | None:
    client: InfrahubClient = await get_client_async()
    if await check_reachability_async(client=client):
        return await client.schema.load(schemas, branch)
    return None


@run_async
async def check_schema(branch: str, schemas: list[dict] | None = None) -> SchemaCheckResponse | None:
    client: InfrahubClient = await get_client_async()
    if await check_reachability_async(client=client):
        success, response = await client.schema.check(schemas=schemas, branch=branch)
        schema_check = SchemaCheckResponse(success=success, response=response)
        return schema_check
    return None


@run_async
async def get_branches(address: str | None = None) -> dict[str, BranchData] | None:
    client: InfrahubClient = await get_client_async(address=address)
    if await check_reachability_async(client=client):
        return await client.branch.all()
    return None


@run_async
async def create_branch(branch_name: str) -> BranchData | None:
    client: InfrahubClient = await get_client_async()
    if await check_reachability_async(client=client):
        return await client.branch.create(branch_name=branch_name)
    return None


@run_async
async def get_objects_as_df(kind: str, include_id: bool = True, branch: str | None = None) -> pd.DataFrame | None:
    client: InfrahubClient = await get_client_async()
    if not await check_reachability_async(client=client):
        return None

    objs = await retrieve_nodes(client=client, kind=kind, branch=branch)

    df = pd.DataFrame([await convert_node_to_dict(obj, include_id=include_id) for obj in objs])
    return df


# FIXME: Until https://github.com/opsmill/infrahub-sdk-python/issues/159
async def retrieve_nodes(
    client: InfrahubClient,
    kind: str,
    branch: str | None = "main",
    page_size: int = 100,
) -> list[InfrahubNode]:
    # Retrieve the number of objects for this Kind
    resp = await client.execute_graphql(query="query { " + f"{kind}" + " { count }}", branch_name=branch)
    count = int(resp[f"{kind}"]["count"])

    batch = await client.create_batch()
    has_remaining_items = True
    page_number = 1
    # Creatting one client.all() query per page_size
    while has_remaining_items:
        page_offset = (page_number - 1) * page_size
        batch.add(
            task=client.all,
            kind=kind,
            offset=page_offset,
            limit=page_size,
            populate_store=True,
            prefetch_relationships=True,
            branch=branch,
        )
        remaining_items = count - (page_offset + page_size)

        if remaining_items < 0:
            has_remaining_items = False
        page_number += 1

    nodes = []
    async for _, response in batch.execute():
        nodes.extend(response)

    return nodes
