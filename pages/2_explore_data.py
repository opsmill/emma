import streamlit as st

from emma.infrahub import get_client, get_objects_as_df, get_schema
from emma.streamlit_helper import test_reachability_and_display_sidebar

st.set_page_config(page_title="Data Explorer")

test_reachability_and_display_sidebar()

@st.cache_data
def convert_df(df):
    return df.to_csv(index=False).encode("utf-8")


st.markdown("# Data Explorer")

client = get_client(branch=st.session_state["infrahub_branch"])
schema = get_schema(branch=st.session_state["infrahub_branch"])

option = st.selectbox("Select which models you want to explore ?", schema.keys())

df = get_objects_as_df(kind=option, include_id=False, branch=st.session_state["infrahub_branch"])

selected_schema = schema[option]

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

csv = convert_df(df)

st.download_button("Download CSV File", csv, f"{option}.csv", "text/csv", key="download-csv")
