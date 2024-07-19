import os

import streamlit as st

from emma.infrahub import check_reachability, get_client, get_schema

st.set_page_config(page_title="Infrahub")

st.markdown("# Infrahub")

client = get_client()

if "infrahub_address" not in st.session_state:
    st.session_state["infrahub_address"] = os.environ.get("INFRAHUB_ADDRESS")

infrahub_address = st.session_state["infrahub_address"]

is_reachable = check_reachability(client=client)

# st.sidebar.header("Plotting Demo")
st.write(f"Infrahub : {infrahub_address}")
st.write(f"reachable : {is_reachable}")

if is_reachable:
    schemas = get_schema()
    st.write(f"Schemas : {len(schemas)}")

# progress_bar = st.sidebar.progress(0)
# status_text = st.sidebar.empty()
# last_rows = np.random.randn(1, 1)
# chart = st.line_chart(last_rows)

# for i in range(1, 101):
#     new_rows = last_rows[-1, :] + np.random.randn(5, 1).cumsum(axis=0)
#     status_text.text("%i%% Complete" % i)
#     chart.add_rows(new_rows)
#     progress_bar.progress(i)
#     last_rows = new_rows
#     time.sleep(0.05)

# progress_bar.empty()

# Streamlit widgets automatically run the script from top to bottom. Since
# this button is not connected to any other logic, it just causes a plain
# rerun.
st.button("Re-run")
