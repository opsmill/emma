import time
from enum import Enum

import pandas as pd
import streamlit as st
from infrahub_sdk.schema import NodeSchema
from infrahub_sdk.utils import compare_lists
from pydantic import BaseModel

from emma.infrahub import add_branch_selector, get_client, get_schema

st.set_page_config(page_title="Import Data")

add_branch_selector(st.sidebar)

st.markdown("# Import Data from CSV file")

client = get_client(branch=st.session_state["infrahub_branch"])
schema = get_schema(branch=st.session_state["infrahub_branch"])

option = st.selectbox("Select which type of data you want to import?", options=schema.keys())

selected_schema = schema[option]

uploaded_file = st.file_uploader("Choose a CSV file")


class MessageSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Message(BaseModel):
    severity: MessageSeverity = MessageSeverity.INFO
    message: str


def validate_if_df_is_compatible_with_schema(df: pd.DataFrame, schema: NodeSchema) -> list[Message]:
    errors = []
    df_columns = list(df.columns.values)

    _, _, missing_mandatory = compare_lists(list1=df_columns, list2=schema.mandatory_input_names)
    for item in missing_mandatory:
        errors.append(
            Message(severity=MessageSeverity.ERROR, message=f"mandatory column for {option!r} missing : {item!r}")
        )
        # errors.append(f"**ERROR**: mandatory column for {option!r} missing : {item!r}\n")

    _, additional, _ = compare_lists(list1=df_columns, list2=schema.relationship_names + schema.attribute_names)

    for item in additional:
        errors.append(Message(severity=MessageSeverity.WARNING, message=f"unable to map {item} for {option!r}"))

    return errors


if uploaded_file is not None:
    dataframe = pd.read_csv(uploaded_file)

    container = st.container(border=True)

    errors = validate_if_df_is_compatible_with_schema(df=dataframe, schema=selected_schema)
    if errors:
        for error in errors:
            container.error(error.message)

    if not errors:
        edited_df = st.data_editor(dataframe)

        if st.button("Import Data"):
            nbr_errors = 0
            with st.status("Loading data...", expanded=True) as status:
                clean_df = edited_df.drop(edited_df.columns[0], axis=1)

                for index, row in clean_df.iterrows():
                    node = client.create(kind=option, **dict(row), branch=st.session_state["infrahub_branch"])
                    node.save(allow_upsert=True)
                    edited_df.at[index, "Status"] = "ONGOING"
                    st.write(f"Item {index} CREATED id:{node.id}\n")

                time.sleep(2)
                status.update(label=f"Loading completed with {nbr_errors} errors", state="complete", expanded=False)
