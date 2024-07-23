from typing import Dict, List

import pandas as pd
import streamlit as st
from infrahub_sdk.schema import MainSchemaTypes
from pydantic import BaseModel
from streamlit_sortables import sort_items

from emma.infrahub import get_objects_as_df, get_schema
from emma.streamlit_utils import set_page_config
from menu import menu_with_redirect


class ColumnLabels(BaseModel):
    optional: List[str]
    mandatory: List[str]


class ColumnMapping(BaseModel):
    labels: List[str]
    label_to_col: Dict[str, str]


@st.cache_data
def convert_df_to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def get_column_labels(model_schema: MainSchemaTypes) -> ColumnLabels:
    optional_columns = [attr.name for attr in model_schema.attributes if attr.optional]
    optional_columns.extend(
        [rel.name for rel in model_schema.relationships if rel.cardinality == "one" and rel.optional]
    )
    mandatory_columns = [attr.name for attr in model_schema.attributes if not attr.optional]
    mandatory_columns.extend(
        [rel.name for rel in model_schema.relationships if rel.cardinality == "one" and not rel.optional]
    )
    return ColumnLabels(optional=optional_columns, mandatory=mandatory_columns)


def create_column_label_mapping(optional_columns: List[str], mandatory_columns: List[str]) -> ColumnMapping:
    column_labels = [
        f"{col} (Mandatory)" if col in mandatory_columns else f"{col} (Optional)"
        for col in mandatory_columns + optional_columns
    ]
    label_to_col = {label: col for label, col in zip(column_labels, mandatory_columns + optional_columns)}
    return ColumnMapping(labels=column_labels, label_to_col=label_to_col)


def filter_and_reorder_columns(df: pd.DataFrame, to_omit: List[str], column_mapping: ColumnMapping) -> pd.DataFrame:
    remaining_columns = [col for col in df.columns if col not in to_omit]
    ordered_labels = sort_items(column_mapping.labels)
    ordered_columns = [
        column_mapping.label_to_col[label]
        for label in ordered_labels
        if column_mapping.label_to_col[label] in remaining_columns
    ]
    return df[ordered_columns]


set_page_config(title="Data Explorer")
st.markdown("# Data Explorer")
menu_with_redirect()

infrahub_schema = get_schema(branch=st.session_state.infrahub_branch)
selected_option = None
if infrahub_schema:
    selected_option = st.selectbox("Select which model you want to explore?", infrahub_schema.keys())

if selected_option:
    selected_schema = infrahub_schema[selected_option]
    dataframe = get_objects_as_df(kind=selected_option, include_id=False, branch=st.session_state.infrahub_branch)

    column_labels_info = get_column_labels(model_schema=selected_schema)

    st.info(
        icon="💡",
        body="""
            You can personalize the CSV by removing Optional fields or re-ordering them.

            Drag and drop the column names to reorder them
            The columns marked as '(Mandatory)' cannot be omitted.
            """,
    )
    omitted_columns = st.multiselect(
        "Select optional columns to omit:",
        options=column_labels_info.optional,
        help="Choose the colums you want to omit",
    )
    filtered_df = dataframe.drop(columns=omitted_columns)

    column_label_mapping_info = create_column_label_mapping(
        optional_columns=column_labels_info.optional, mandatory_columns=column_labels_info.mandatory
    )
    reordered_df = filter_and_reorder_columns(
        df=filtered_df, to_omit=omitted_columns, column_mapping=column_label_mapping_info
    )

    csv = convert_df_to_csv(df=reordered_df)
    st.dataframe(reordered_df, hide_index=True)
    st.download_button("Download CSV File", csv, f"{selected_option}.csv", "text/csv", key="download-csv")
