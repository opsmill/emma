from typing import Dict, List

import pandas as pd
import streamlit as st
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
def convert_df_to_csv(dataframe: pd.DataFrame) -> bytes:
    return dataframe.to_csv(index=False).encode("utf-8")


def get_column_labels(selected_schema: dict) -> ColumnLabels:
    optional_columns = [attr.name for attr in selected_schema.attributes if attr.optional]
    mandatory_columns = [attr.name for attr in selected_schema.attributes if not attr.optional]
    return ColumnLabels(optional=optional_columns, mandatory=mandatory_columns)


def create_column_label_mapping(optional_columns: List[str], mandatory_columns: List[str]) -> ColumnMapping:
    column_labels = [
        f"{col} (Mandatory)" if col in mandatory_columns else f"{col} (Optional)"
        for col in mandatory_columns + optional_columns
    ]
    label_to_col = {label: col for label, col in zip(column_labels, mandatory_columns + optional_columns)}
    return ColumnMapping(labels=column_labels, label_to_col=label_to_col)


def filter_and_reorder_columns(
    dataframe: pd.DataFrame, omitted_columns: List[str], column_mapping: ColumnMapping
) -> pd.DataFrame:
    remaining_columns = [col for col in dataframe.columns if col not in omitted_columns]
    ordered_labels = sort_items(column_mapping.labels)
    ordered_columns = [
        column_mapping.label_to_col[label]
        for label in ordered_labels
        if column_mapping.label_to_col[label] in remaining_columns
    ]
    return dataframe[ordered_columns]


set_page_config(title="Data Explorer")
st.markdown("# Data Explorer")
menu_with_redirect()

schema = get_schema(branch=st.session_state.infrahub_branch)

option = st.selectbox("Select which models you want to explore?", schema.keys())
selected_schema = schema[option]

if option:
    dataframe = get_objects_as_df(kind=option, include_id=False, branch=st.session_state.infrahub_branch)

    column_labels = get_column_labels(selected_schema)

    with st.expander(label="Personalization Tips", icon="💡"):
        st.info("""
        Drag and drop the column names to reorder them.
        The columns marked as '(Mandatory)' cannot be omitted.
        """)
        omitted_columns = st.multiselect("Select optional columns to omit:", options=column_labels.optional)
        dataframe = dataframe.drop(columns=omitted_columns)

        column_mapping = create_column_label_mapping(
            optional_columns=column_labels.optional, mandatory_columns=column_labels.mandatory
        )
        dataframe = filter_and_reorder_columns(
            dataframe=dataframe, omitted_columns=omitted_columns, column_mapping=column_mapping
        )

    csv = convert_df_to_csv(dataframe=dataframe)
    st.dataframe(dataframe, hide_index=True)
    st.download_button("Download CSV File", csv, f"{option}.csv", "text/csv", key="download-csv")
