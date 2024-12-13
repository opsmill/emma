import asyncio
from ast import literal_eval
from enum import Enum
from typing import Any, List, Union

import numpy as np
import pandas as pd
import streamlit as st
from infrahub_sdk.schema import GenericSchema, MainSchemaTypes, NodeSchema
from infrahub_sdk.utils import compare_lists
from pandas.errors import EmptyDataError
from pydantic import BaseModel

from emma.infrahub import (
    create_and_add_to_batch,
    execute_batch,
    get_cached_schema,
    get_client_async,
    get_instance_branch,
)
from emma.streamlit_utils import handle_reachability_error, set_page_config
from emma.utils import is_uuid, parse_hfid
from menu import menu_with_redirect


class MessageSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Message(BaseModel):
    severity: MessageSeverity = MessageSeverity.INFO
    message: str


def parse_item(item: str, is_generic: bool) -> Union[str, List[str]]:
    """Parse a single item as a UUID, HFID, or leave as-is."""
    if is_uuid(item):
        return item
    # FIXME: Need feature in thee SDK to avoid this
    # If the relationship is toward Generic we will retrieve the ID as we can't use HFID with a relationship to Generic
    if is_generic:
        tmp_hfid = parse_hfid(hfid=item)
        client = asyncio.run(get_client_async())
        obj = asyncio.run(client.get(kind=tmp_hfid[0], hfid=tmp_hfid[1:], branch=get_instance_branch()))
        return obj.id
    # If it's not a Generic we gonna parse the HFID
    return parse_hfid(hfid=item)[1:]


def parse_value(value: Union[str, List[str]], is_generic: bool) -> Union[str, List[str]]:
    """Parse a single value, either a UUID, HFID, or a list."""
    if isinstance(value, str):
        return parse_item(item=value, is_generic=is_generic)
    return value


def parse_list_value(value: str, is_generic: bool) -> Union[str, List[Union[str, List[str]]]]:
    """Convert list-like string to a list and parse items as UUIDs or HFIDs."""
    parsed_value = literal_eval(value)
    if isinstance(parsed_value, list):
        return [parse_item(item=item, is_generic=is_generic) for item in parsed_value]
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
    infrahub_schema: dict[str, MainSchemaTypes] | None,
) -> tuple[pd.DataFrame, list[Message]]:
    """Process DataFrame rows to handle HFIDs, UUIDs, and empty lists."""
    errors = validate_columns(list(df.columns), target_schema)
    processed_rows = []

    for _, items_row in df.iterrows():
        processed_row: dict[str, Any] = {}
        for column, value in items_row.items():
            if pd.isnull(value):
                continue

            if column in target_schema.relationship_names:
                relation_schema = target_schema.get_relationship(column)
                peer_schema = infrahub_schema[relation_schema.peer]
                is_generic = False
                if isinstance(peer_schema, GenericSchema):
                    is_generic = True
                # Process relationships for HFID or UUID
                if isinstance(value, str) and value.startswith("[") and value.endswith("]"):
                    processed_row[column] = parse_list_value(value=value, is_generic=is_generic)
                else:
                    processed_row[column] = parse_value(value=value, is_generic=is_generic)

            elif column in target_schema.attribute_names:
                # Directly use attribute values
                processed_row[column] = value

        processed_rows.append(processed_row)

    prepocessed_df = pd.DataFrame(processed_rows)
    return prepocessed_df, errors


def process_and_save_with_batch(edited_df: pd.DataFrame, selected_option: str, branch: str):
    nbr_errors = 0

    client = asyncio.run(get_client_async())
    batch = asyncio.run(client.create_batch())

    # Process rows and add them to the batch
    for index, row in edited_df.iterrows():
        data = {key: value for key, value in dict(row).items() if not isinstance(value, float) or pd.notnull(value)}
        try:
            create_and_add_to_batch(
                client=client,
                branch=branch,
                kind_name=selected_option,
                data=data,
                batch=batch,
            )
            edited_df.at[index, "Status"] = "ONGOING"
        except Exception as exc:
            nbr_errors += 1
            with st.expander(icon="⚠️", label=f"Line {index}: Item failed to be imported", expanded=False):
                st.write(f"Error: {exc}")

    # Execute the batch
    if batch.num_tasks > 0:
        try:
            execute_batch(batch=batch)
        except Exception:
            nbr_errors += 1

    # Display final toast message
    if nbr_errors > 0:
        msg.toast(icon="❌", body=f"Loading completed with {nbr_errors} errors")
    else:
        msg.toast(icon="✅", body="Loading completed with success")


set_page_config(title="Import Data")
st.markdown("# Import Data from CSV file")
menu_with_redirect()

infrahub_schema = get_cached_schema(branch=st.session_state.infrahub_branch)
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
            processed_df, _errors = preprocess_and_validate_data(
                df=dataframe, target_schema=selected_schema, infrahub_schema=infrahub_schema
            )

            if _errors:
                msg.toast(icon="❌", body=f".csv file is not valid for {selected_option}")
                for error in _errors:
                    st.toast(icon="⚠️", body=error.message)
            else:
                edited_df = st.data_editor(processed_df, hide_index=True)

                if st.button("Import Data"):
                    nbr_errors = 0
                    st.write()
                    msg.toast(body=f"Loading data for {selected_schema.namespace}{selected_schema.name}")
                    process_and_save_with_batch(
                        edited_df=edited_df, selected_option=selected_option, branch=get_instance_branch()
                    )
