import time
import types
from enum import Enum
from typing import Any, Dict

import pandas as pd
import streamlit as st
from infrahub_sdk.schema import NodeSchema
from infrahub_sdk.utils import compare_lists
from pandas.errors import EmptyDataError
from pydantic import BaseModel

from emma.infrahub import get_client, get_schema, handle_reachability_error
from emma.streamlit_utils import set_page_config
from menu import menu_with_redirect


class MessageSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Message(BaseModel):
    severity: MessageSeverity = MessageSeverity.INFO
    message: str


def dict_remove_nan_values(dictionary: Dict[str, Any]) -> Dict[str, Any]:
    remove = [k for k, v in dictionary.items() if pd.isnull(v)]
    for k in remove:
        dictionary.pop(k)
    return dictionary


def validate_if_df_is_compatible_with_schema(df: pd.DataFrame, target_schema: NodeSchema, schema: str) -> list[Message]:
    errors = []

    df_columns = list(df.columns.values)
    _, _, missing_mandatory = compare_lists(list1=df_columns, list2=target_schema.mandatory_input_names)
    for item in missing_mandatory:
        errors.append(
            Message(severity=MessageSeverity.ERROR, message=f"mandatory column for {schema!r} missing : {item!r}")
        )
        # errors.append(f"**ERROR**: mandatory column for {schema!r} missing : {item!r}\n")

    _, additional, _ = compare_lists(
        list1=df_columns, list2=target_schema.relationship_names + target_schema.attribute_names
    )

    for item in additional:
        errors.append(Message(severity=MessageSeverity.WARNING, message=f"unable to map {item} for {schema!r}"))

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


set_page_config(title="Import Data")
st.markdown("# Import Data from CSV file")
menu_with_redirect()

infrahub_schema = get_schema(branch=st.session_state.infrahub_branch)
if not infrahub_schema:
    handle_reachability_error()

else:
    option = st.selectbox("Select which type of data you want to import?", options=infrahub_schema.keys())

    if option:
        selected_schema = infrahub_schema[option]

        uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])

        if uploaded_file is not None:
            msg = st.toast(f"Loading file {uploaded_file}...")
            dataframe = None
            try:
                dataframe = pd.read_csv(filepath_or_buffer=uploaded_file)
            except EmptyDataError as exc:
                msg.toast(icon="❌", body=f"{str(exc)}")
                dataframe = None

            container = st.container(border=True)

            if isinstance(dataframe, types.NoneType) is True:
                st.stop()
            msg.toast("Comparing data to schema...")
            _errors = validate_if_df_is_compatible_with_schema(
                df=dataframe, target_schema=selected_schema, schema=option
            )
            if _errors:
                msg.toast(icon="❌", body=f".csv file is not valid for {option}")
                for error in _errors:
                    st.toast(icon="⚠️", body=error.message)

            if not _errors:
                edited_df = st.data_editor(dataframe, hide_index=True)

                if st.button("Import Data"):
                    nbr_errors = 0
                    client = get_client(branch=st.session_state.infrahub_branch)
                    msg.toast(body=f"Loading data for {selected_schema}")
                    for index, row in edited_df.iterrows():
                        data = dict_remove_nan_values(dict(row))
                        node = client.create(kind=option, **data, branch=st.session_state.infrahub_branch)
                        node.save(allow_upsert=True)
                        edited_df.at[index, "Status"] = "ONGOING"
                        msg.toast(icon="✅", body=f"Item {index+1} CREATED id:{node.id}")

                    time.sleep(2)
                    if nbr_errors > 0:
                        st.toast(icon="❌", body=f"Loading completed with {nbr_errors} errors")
                    else:
                        msg.toast(icon="✅", body="Load complete")
