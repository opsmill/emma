import types
from ipaddress import IPv4Network, IPv6Network
from typing import Any, Dict, List

import pandas as pd
import streamlit as st
from pydantic import BaseModel
from streamlit_sortables import sort_items

from emma.infrahub import get_cached_schema, get_objects_as_df
from emma.streamlit_utils import handle_reachability_error, set_page_config
from menu import menu_with_redirect


class ColumnLabels(BaseModel):
    optional: List[str]
    mandatory: List[str]


class ColumnMapping(BaseModel):
    labels: List[str]
    label_to_col: Dict[str, str]


@st.cache_data
def convert_df_to_csv(df: pd.DataFrame) -> bytes:
    """Convert DataFrame to CSV in bytes format."""
    csv_str = df.to_csv(index=False)
    return csv_str.encode("utf-8") if csv_str else b""


@st.cache_data
def fetch_data(kind: str, branch: str) -> pd.DataFrame:
    """Fetches data once per session for the selected model."""
    df = get_objects_as_df(kind=kind, include_id=False, branch=branch, prefetch_relationships=False)
    # Only convert IPv4Network and IPv6Network objects to strings
    for col in df.columns:
        if df[col].dtype == "object":  # Only check object columns
            if df[col].apply(lambda x: isinstance(x, (IPv4Network, IPv6Network))).any():
                df[col] = df[col].apply(lambda x: str(x) if isinstance(x, (IPv4Network, IPv6Network)) else x)

    return df


def get_column_labels(model_schema: Any) -> ColumnLabels:
    """Retrieve column labels for optional and mandatory columns."""
    optional_columns = [attr.name for attr in model_schema.attributes if attr.optional]
    optional_columns.extend([rel.name for rel in model_schema.relationships if rel.optional])
    mandatory_columns = [attr.name for attr in model_schema.attributes if not attr.optional]
    mandatory_columns.extend([rel.name for rel in model_schema.relationships if not rel.optional])
    return ColumnLabels(optional=optional_columns, mandatory=mandatory_columns)


def create_column_label_mapping(
    to_omit: List[str], optional_columns: List[str], mandatory_columns: List[str]
) -> ColumnMapping:
    """Map column labels with omitted columns."""
    column_labels = [
        f"{col} (Mandatory)" if col in mandatory_columns and col not in to_omit else f"{col} (Optional)"
        for col in mandatory_columns + optional_columns
    ]
    label_to_col = {label: col for label, col in zip(column_labels, mandatory_columns + optional_columns, strict=True)}
    return ColumnMapping(labels=column_labels, label_to_col=label_to_col)


def filter_and_reorder_columns(df: pd.DataFrame, to_omit: List[str], column_mapping: ColumnMapping) -> pd.DataFrame:
    """Filter and reorder columns based on user selections."""
    remaining_columns = [col for col in df.columns if col not in to_omit]
    ordered_labels = sort_items(column_mapping.labels)
    ordered_columns = [
        column_mapping.label_to_col[label]
        for label in ordered_labels
        if column_mapping.label_to_col[label] in remaining_columns
    ]
    return df[ordered_columns]


set_page_config(title="Data Exporter")
st.markdown("# Data Exporter")
menu_with_redirect()

infrahub_schema = get_cached_schema(branch=st.session_state.infrahub_branch)
if not infrahub_schema:
    st.session_state.infrahub_error_message = "No schema"
    handle_reachability_error()
else:
    selected_option = st.selectbox("Select which model you want to explore?", infrahub_schema.keys())

    # Check if `selected_option` has changed to reset `dataframe` and `reordered_df`
    if "last_selected_option" not in st.session_state or st.session_state.last_selected_option != selected_option:
        with st.spinner("Loading data, please wait..."):
            st.session_state["dataframe"] = fetch_data(selected_option, st.session_state.infrahub_branch)
            if isinstance(st.session_state["dataframe"], types.NoneType):
                st.session_state.infrahub_error_message = "No dataframe"
                handle_reachability_error(redirect=False)
            else:
                st.session_state["reordered_df"] = st.session_state["dataframe"]  # Reset reordered_df
                st.session_state["last_selected_option"] = selected_option
                st.session_state["omitted_columns"] = []

        # Fetch schema and column labels only when `selected_option` changes
        selected_schema = infrahub_schema[selected_option]
        column_labels_info = get_column_labels(model_schema=selected_schema)
        st.session_state["column_labels_info"] = column_labels_info  # Save for later access

    # UI elements outside the selection check, so they persist during re-runs
    column_labels_info = st.session_state["column_labels_info"]

    st.info(
        icon="💡",
        body="""
            You can personalize the CSV by removing Optional fields or re-ordering them.
            Drag and drop the column names to reorder them.
            The columns marked as '(Mandatory)' cannot be omitted.
            """,
    )
    # Omit all optional columns by default
    st.session_state["omitted_columns"] = column_labels_info.optional

    # Multiselect for omitting columns
    omitted_columns = st.multiselect(
        "Select optional columns to omit:",
        options=column_labels_info.optional,
        default=st.session_state["omitted_columns"],
        help="Choose the columns you want to omit",
    )

    # Update omitted columns in session state only if changed
    if omitted_columns != st.session_state["omitted_columns"]:
        st.session_state["omitted_columns"] = omitted_columns

    # Create the column mapping and filter/reorder DataFrame
    column_label_mapping_info = create_column_label_mapping(
        to_omit=omitted_columns,
        optional_columns=column_labels_info.optional,
        mandatory_columns=column_labels_info.mandatory,
    )

    # Re-filter only when omitted_columns changes
    st.session_state["reordered_df"] = filter_and_reorder_columns(
        df=st.session_state["dataframe"],
        to_omit=omitted_columns,
        column_mapping=column_label_mapping_info,
    )

    # Display and provide download button for the CSV
    csv = convert_df_to_csv(df=st.session_state["reordered_df"])
    st.dataframe(st.session_state["reordered_df"], hide_index=True)
    st.download_button("Download CSV File", csv, f"{selected_option}.csv", "text/csv", key="download-csv")
