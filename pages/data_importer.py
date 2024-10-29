import time
from enum import Enum
from typing import List, Union

import numpy as np
import pandas as pd
import streamlit as st
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.schema import NodeSchema
from infrahub_sdk.utils import compare_lists
from pandas.errors import EmptyDataError
from pydantic import BaseModel

from emma.infrahub import get_client, get_schema, handle_reachability_error, is_uuid, parse_hfid
from emma.streamlit_utils import set_page_config
from menu import menu_with_redirect


class MessageSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Message(BaseModel):
    severity: MessageSeverity = MessageSeverity.INFO
    message: str


def parse_item(item: str) -> Union[str, List[str]]:
    """Parse a single item as a UUID, HFID, or leave as-is."""
    if is_uuid(item):
        return item
    return parse_hfid(item)


def parse_value(value: Union[str, List[str]]) -> Union[str, List[str]]:
    """Parse a single value, either a UUID, HFID, or a list."""
    if isinstance(value, str):
        return parse_item(value)
    return value


def parse_list_value(value: str) -> Union[str, List[Union[str, List[str]]]]:
    """Convert list-like string to a list and parse items as UUIDs or HFIDs."""
    try:
        parsed_value = eval(value)
        if isinstance(parsed_value, list):
            return [parse_item(item) for item in parsed_value]
    except Exception:
        pass  # Handle invalid format or return as-is upstream
    return value


def validate_columns(df_columns: list, target_schema: NodeSchema) -> list[Message]:
    """Validate missing and additional columns."""
    errors = []
    _, _, missing_mandatory = compare_lists(list1=df_columns, list2=target_schema.mandatory_input_names)
    for item in missing_mandatory:
        errors.append(Message(severity=MessageSeverity.ERROR, message=f"Mandatory column missing: {item!r}"))

    _, additional, _ = compare_lists(
        list1=df_columns, list2=target_schema.relationship_names + target_schema.attribute_names
    )
    for item in additional:
        errors.append(Message(severity=MessageSeverity.WARNING, message=f"Unable to map {item}"))
    return errors


def preprocess_and_validate_data(
    df: pd.DataFrame,
    target_schema: NodeSchema,
) -> tuple[pd.DataFrame, list[Message]]:
    """Process DataFrame rows to handle HFIDs, UUIDs, and empty lists."""
    errors = validate_columns(list(df.columns), target_schema)
    processed_rows = []

    for _, row in df.iterrows():
        processed_row = {}
        for column, value in row.items():
            if pd.isnull(value):
                continue

            if column in target_schema.relationship_names:
                # Process relationships for HFID or UUID
                if isinstance(value, str) and value.startswith("[") and value.endswith("]"):
                    processed_row[column] = parse_list_value(value=value)
                else:
                    processed_row[column] = parse_value(value=value)
            elif column in target_schema.attribute_names:
                # Directly use attribute values
                processed_row[column] = value

        processed_rows.append(processed_row)

    processed_df = pd.DataFrame(processed_rows)
    return processed_df, errors


set_page_config(title="Import Data")
st.markdown("# Import Data from CSV file")
menu_with_redirect()

infrahub_schema = get_schema(branch=st.session_state.infrahub_branch)
if not infrahub_schema:
    handle_reachability_error()

else:
    selected_option = st.selectbox("Select which type of data you want to import?", options=infrahub_schema.keys())

    if selected_option:
        selected_schema = infrahub_schema[selected_option]
        uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])

        if uploaded_file is not None:
            msg = st.toast(f"Loading file {uploaded_file}...")
            try:
                dataframe = pd.read_csv(filepath_or_buffer=uploaded_file)
                # Replace any "[]" string with NaN
                dataframe.replace(["[]", "", '""'], np.nan, inplace=True)
            except EmptyDataError as exc:
                msg.toast(icon="❌", body=f"{str(exc)}")
                st.stop()

            msg.toast("Comparing data to schema...")
            processed_df, _errors = preprocess_and_validate_data(df=dataframe, target_schema=selected_schema)

            if _errors:
                msg.toast(icon="❌", body=f".csv file is not valid for {selected_option}")
                for error in _errors:
                    st.toast(icon="⚠️", body=error.message)
            else:
                edited_df = st.data_editor(processed_df, hide_index=True)

                if st.button("Import Data"):
                    nbr_errors = 0
                    client = get_client(branch=st.session_state.infrahub_branch)
                    st.write()
                    msg.toast(body=f"Loading data for {selected_schema.namespace}{selected_schema.name}")
                    for index, row in edited_df.iterrows():
                        # Convert row to a dictionary and remove NaN values
                        data = {
                            key: value
                            for key, value in dict(row).items()
                            if not isinstance(value, float) or pd.notnull(value)
                        }
                        node = client.create(kind=selected_option, **data, branch=st.session_state.infrahub_branch)
                        try:
                            node.save(allow_upsert=True)
                            edited_df.at[index, "Status"] = "ONGOING"
                            with st.expander(icon="✅", label=f"Line {index}: Item created with success"):
                                st.write(f"Node id: {node.id}")
                        except GraphQLError as exc:
                            with st.expander(
                                icon="⚠️", label=f"Line {index}: Item failed to be imported", expanded=False
                            ):
                                st.write(f"Error: {exc}")
                            nbr_errors += 1

                    time.sleep(2)
                    if nbr_errors > 0:
                        msg.toast(icon="❌", body=f"Loading completed with {nbr_errors} errors")
                    else:
                        msg.toast(icon="✅", body="Loading completed with success")
