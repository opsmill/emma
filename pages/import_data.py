import time
from enum import Enum

import pandas as pd
import streamlit as st
from infrahub_sdk.schema import NodeSchema
from infrahub_sdk.utils import compare_lists
from pydantic import BaseModel

from emma.infrahub import get_client, get_schema
from emma.streamlit_utils import set_page_config
from menu import menu_with_redirect

set_page_config(title="Import Data")
st.markdown("# Import Data from CSV file")
menu_with_redirect()


class MessageSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Message(BaseModel):
    severity: MessageSeverity = MessageSeverity.INFO
    message: str


def validate_if_df_is_compatible_with_schema(df: pd.DataFrame, target_schema: NodeSchema) -> list[Message]:
    errors = []
    df_columns = list(df.columns.values)

    _, _, missing_mandatory = compare_lists(list1=df_columns, list2=target_schema.mandatory_input_names)
    for item in missing_mandatory:
        errors.append(
            Message(severity=MessageSeverity.ERROR, message=f"mandatory column for {option!r} missing : {item!r}")
        )
        # errors.append(f"**ERROR**: mandatory column for {option!r} missing : {item!r}\n")

    _, additional, _ = compare_lists(
        list1=df_columns, list2=target_schema.relationship_names + target_schema.attribute_names
    )

    for item in additional:
        errors.append(Message(severity=MessageSeverity.WARNING, message=f"unable to map {item} for {option!r}"))

    return errors


client = get_client(branch=st.session_state.infrahub_branch)
schema = get_schema(branch=st.session_state.infrahub_branch)

option = st.selectbox("Select which type of data you want to import?", options=schema.keys())

if option:
    selected_schema = schema[option]

    uploaded_file = st.file_uploader("Choose a CSV file")

if uploaded_file is not None:
    dataframe = pd.read_csv(uploaded_file)

    container = st.container(border=True)

    _errors = validate_if_df_is_compatible_with_schema(df=dataframe, target_schema=selected_schema)
    if _errors:
        for error in _errors:
            container.error(error.message)

    if not _errors:
        edited_df = st.data_editor(dataframe)

        if st.button("Import Data"):
            nbr_errors = 0
            with st.status("Loading data...", expanded=True) as status:
                for index, row in edited_df.iterrows():
                    node = client.create(kind=option, **dict(row), branch=st.session_state.infrahub_branch)
                    node.save(allow_upsert=True)
                    edited_df.at[index, "Status"] = "ONGOING"
                    st.write(f"Item {index} CREATED id:{node.id}\n")

                time.sleep(2)
                status.update(label=f"Loading completed with {nbr_errors} errors", state="complete", expanded=False)
