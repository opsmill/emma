import os
from enum import Enum
from typing import TYPE_CHECKING, Any

import pandas as pd
import streamlit as st
from httpx import HTTPError
from infrahub_sdk import InfrahubClientSync, InfrahubNodeSync
from infrahub_sdk.exceptions import (
    AuthenticationError,
    GraphQLError,
    ServerNotReachableError,
    ServerNotResponsiveError,
)
from streamlit.delta_generator import DG

if TYPE_CHECKING:
    from infrahub_sdk.node import Attribute


class InfrahubStatus(str, Enum):
    UNKNOWN = "unknown"
    OK = "ok"
    ERROR = "error"


@st.cache_resource
def get_client(branch: str | None = None) -> InfrahubClientSync:
    st.session_state["infrahub_address"] = os.environ.get("INFRAHUB_ADDRESS")
    return InfrahubClientSync(address=st.session_state["infrahub_address"])


@st.cache_data
def get_schema(branch: str | None = None):
    client = get_client(branch=branch)
    return client.schema.all(branch=branch)


def get_branches():
    client = get_client()
    return client.branch.all()


def check_reacheability(client: InfrahubClientSync) -> bool:
    try:
        get_version(client=client)
        st.session_state["infrahub_status"] = InfrahubStatus.OK
        return True
    except (AuthenticationError, GraphQLError, HTTPError, ServerNotReachableError, ServerNotResponsiveError) as exc:
        st.session_state["infrahub_error_message"] = str(exc)
        st.session_state["infrahub_status"] = InfrahubStatus.ERROR
        return False


def get_version(client: InfrahubClientSync) -> str:
    query = "query { InfrahubInfo { version }}"
    response = client.execute_graphql(query=query, raise_for_error=True)
    return response["InfrahubInfo"]["version"]


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


def add_branch_selector(sidebar: DG):
    branches = get_branches()
    if "infrahub_branch" not in st.session_state:
        st.session_state["infrahub_branch"] = "main"
    sidebar.selectbox(label="branch", options=branches.keys(), key="infrahub_branch")
