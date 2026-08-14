import asyncio
from typing import List

import pandas as pd
import streamlit as st
from pandas.errors import EmptyDataError
from streamlit.delta_generator import DeltaGenerator

from emma.csv_import import (
    Message,
    MessageSeverity,
    csv_line_label,
    has_blocking_errors,
    normalize_dataframe,
    preprocess_and_validate_data,
)
from emma.infrahub import (
    create_and_add_to_batch,
    execute_batch,
    get_cached_schema,
    get_client_async,
    get_instance_branch,
)
from emma.streamlit_utils import handle_reachability_error, set_page_config
from menu import menu_with_redirect


def resolve_node_id(kind: str, hfid: List[str]) -> str:
    """Look up a node by its human-friendly ID and return its id.

    Args:
        kind: The kind to query.
        hfid: The human-friendly ID components to query it with.

    Returns:
        The id of the matching node.
    """
    client = asyncio.run(get_client_async())
    obj = asyncio.run(client.get(kind=kind, hfid=hfid, branch=get_instance_branch()))
    return str(obj.id)


def render_messages(messages: List[Message]) -> None:
    """Display validation messages so they stay on screen.

    Toasts fade after a few seconds, which previously left the page blank with no
    indication of what was wrong, so messages are rendered inline instead.

    Args:
        messages: The messages raised while validating a file.
    """
    for message in messages:
        if message.severity == MessageSeverity.ERROR:
            st.error(message.message, icon="❌")
        elif message.severity == MessageSeverity.WARNING:
            st.warning(message.message, icon="⚠️")
        else:
            st.info(message.message)


def process_and_save_with_batch(
    data_frame: pd.DataFrame, kind: str, branch: str | None, st_msg: DeltaGenerator
) -> None:
    """Process and save data frame rows with batch operations.

    Args:
        data_frame: The rows to import.
        kind: The kind to create the rows as.
        branch: The branch to create the rows on.
        st_msg: The toast to report overall progress through.
    """
    nbr_errors = 0
    nbr_rows = len(data_frame.index)

    client = asyncio.run(get_client_async())
    batch = asyncio.run(client.create_batch(return_exceptions=True))

    # Process rows and add them to the batch
    for position, (_, row) in enumerate(data_frame.iterrows()):
        data = {key: value for key, value in dict(row).items() if not isinstance(value, float) or pd.notnull(value)}
        try:
            create_and_add_to_batch(
                branch=branch,
                kind_name=kind,
                data=data,
                batch=batch,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            nbr_errors += 1
            label = f"{csv_line_label(position)}: Item failed to be imported (creation)"
            with st.expander(icon="⚠️", label=label, expanded=False):
                st.write(f"Error: {exc}")

    # Execute the batch. execute_batch reports each failure inline and returns how
    # many of them there were, so partial failures are counted rather than assumed
    # to be successes.
    if batch.num_tasks > 0:
        try:
            nbr_errors += execute_batch(batch=batch)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            nbr_errors += 1
            with st.expander(icon="⚠️", label="Item failed to be imported (execution)", expanded=False):
                st.write(f"Error: {exc}")

    # Display final result
    if nbr_errors > 0:
        st.error(
            f"Loading completed with {nbr_errors} error(s): {nbr_rows - nbr_errors} of {nbr_rows} row(s) imported.",
            icon="❌",
        )
        st_msg.toast(icon="❌", body=f"Loading completed with {nbr_errors} errors")
    else:
        st.success(f"Loading completed with success: {nbr_rows} row(s) imported.", icon="✅")
        st_msg.toast(icon="✅", body="Loading completed with success")


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
            msg = st.toast(f"Loading file {uploaded_file.name}...")
            try:
                dataframe = normalize_dataframe(pd.read_csv(filepath_or_buffer=uploaded_file))
            except EmptyDataError as exc_error:
                msg.toast(icon="❌", body=f"{exc_error!s}")
                st.stop()

            msg.toast("Comparing data to schema...")
            processed_df, _messages = preprocess_and_validate_data(
                df=dataframe,
                schema=selected_schema,
                branch_schemas=infrahub_schema,
                resolver=resolve_node_id,
            )

            render_messages(_messages)

            if has_blocking_errors(_messages):
                msg.toast(icon="❌", body=f".csv file is not valid for {selected_option}")
            else:
                edited_df = st.data_editor(processed_df, hide_index=True)

                if st.button("Import Data"):
                    msg.toast(body=f"Loading data for {selected_schema.namespace}{selected_schema.name}")
                    process_and_save_with_batch(
                        data_frame=edited_df, kind=selected_option, branch=get_instance_branch(), st_msg=msg
                    )
