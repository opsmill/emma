import streamlit as st
from pandas import DataFrame

from emma.infrahub import get_client, get_objects_as_df, get_schema
from emma.streamlit_utils import set_page_config
from menu import menu_with_redirect

set_page_config(title="Data Explorer")
st.markdown("# Data Explorer")
menu_with_redirect()

@st.cache_data
def convert_df_to_csv(df: DataFrame):
    return df.to_csv(index=False).encode("utf-8")

client = get_client(branch=st.session_state.infrahub_branch)
schema = get_schema(branch=st.session_state.infrahub_branch)

option = st.selectbox("Select which models you want to explore ?", schema.keys())
selected_schema = schema[option]

df = get_objects_as_df(kind=option, include_id=False, branch=st.session_state.infrahub_branch)

# Set the configuration of the column based on the schema
# TODO need to move that out of the page into the shared library

column_mapping = {
    "Number": st.column_config.NumberColumn,
    "Text": st.column_config.TextColumn,
    "default": st.column_config.Column,
}

attr_kind_map = []
column_config = {}
for attr in selected_schema.attributes:
    column_class = column_mapping.get(attr.kind, st.column_config.Column)
    column_config[attr.name] = column_class(label=attr.label, help=attr.description)

st.dataframe(df, column_config=column_config, hide_index=True, selection_mode="single-row")

csv = convert_df_to_csv(df)

st.download_button("Download CSV File", csv, f"{option}.csv", "text/csv", key="download-csv")
