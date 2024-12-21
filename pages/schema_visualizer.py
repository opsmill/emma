from typing import List

import streamlit as st
from infrahub_sdk.schema import GenericSchema, NodeSchema
from streamlit_flow import streamlit_flow
from streamlit_flow.elements import StreamlitFlowEdge, StreamlitFlowNode
from streamlit_flow.layouts import LayeredLayout
from streamlit_flow.state import StreamlitFlowState

from emma.infrahub import convert_schema_to_dict, dict_to_df, get_cached_schema
from emma.streamlit_utils import display_expander, handle_reachability_error, set_page_config
from menu import menu_with_redirect

set_page_config(title="Schema Visualizer")
st.markdown("# Schema Visualizer")
menu_with_redirect()


def visualize_schema_flow(generics: List[GenericSchema], nodes: List[NodeSchema], key: str) -> str:
    """
    Visualize the schema using Streamlit Flow.

    Parameters:
        generics (List[GenericSchema]): List of generic schema items.
        nodes (List[NodeSchema]): List of node schema items.
        key (str): Unique key for the Streamlit Flow component.

    Returns:
        str: The ID of the selected node or edge.
    """
    flow_nodes = []
    flow_edges = []

    # Add Generics to the network
    for generic in generics:
        node_id = f"{generic.namespace}{generic.name}"
        flow_nodes.append(
            StreamlitFlowNode(
                id=node_id,
                pos=(0, 0),
                data={"content": node_id},
                node_type="input",
                source_position="right",
                style={"backgroundColor": "lightblue"},
            )
        )
        for rel in generic.relationships:
            peer_id = f"{rel.peer}"
            flow_edges.append(
                StreamlitFlowEdge(
                    id=f"{node_id}-{peer_id}",
                    source=node_id,
                    target=peer_id,
                    animated=True,
                    label=rel.name,
                    style={"stroke": "#8884d8"},
                )
            )

    # Add Nodes to the network
    for node in nodes:
        node_id = f"{node.namespace}{node.name}"
        flow_nodes.append(
            StreamlitFlowNode(
                id=node_id,
                pos=(0, 0),
                data={"content": node_id},
                node_type="default",
                source_position="right",
                style={"backgroundColor": "orange"},
            )
        )
        for rel in node.relationships:
            peer_id = f"{rel.peer}"
            edge_style = {"stroke": "#82ca9d"} if rel.kind == "Parent" else {}
            flow_edges.append(
                StreamlitFlowEdge(
                    id=f"{node_id}-{peer_id}",
                    source=node_id,
                    target=peer_id,
                    animated=True,
                    label=rel.name,
                    style=edge_style,
                )
            )

    # Display the flow graph and get clicked item
    flow_state = StreamlitFlowState(nodes=flow_nodes, edges=flow_edges)
    selected_id = streamlit_flow(
        key=key,
        state=flow_state,
        layout=LayeredLayout(direction="right", node_layer_spacing=200),
        fit_view=True,
        show_minimap=True,
        show_controls=True,
        pan_on_drag=True,
        allow_zoom=True,
        height=1000,
        get_node_on_click=True,
        get_edge_on_click=True,
        hide_watermark=True,
    )

    return selected_id


def display_node_info(selected_id: str, generics: List[GenericSchema], nodes: List[NodeSchema]) -> None:
    """
    Display detailed information about the selected node.

    Parameters:
        selected_id (str): The ID of the selected node.
        generics (List[GenericSchema]): List of generic schema items.
        nodes (List[NodeSchema]): List of node schema items.
    """
    node = next((item for item in generics + nodes if f"{item.namespace}{item.name}" == selected_id), None)
    if node:
        st.markdown("#### Node Information")

        node_data = convert_schema_to_dict(node=node)
        main_info_df, attributes_df, relationships_df = dict_to_df(node_data)

        inherit_or_use_label = "Inherit from" if "Inherit from" in main_info_df.columns else "Used by"

        st.markdown(f"""
        - **Name**: {main_info_df["Name"].iloc[0]}
        - **Namespace**: {main_info_df["Namespace"].iloc[0]}
        - **Label**: {main_info_df["Label"].iloc[0]}
        - **Description**: {main_info_df["Description"].iloc[0]}
        - **{inherit_or_use_label}**: {main_info_df[inherit_or_use_label].iloc[0]}
        """)

        st.markdown("##### Attributes")
        if not attributes_df.empty:
            st.dataframe(data=attributes_df, hide_index=True)
        else:
            st.markdown("No Attributes found.")

        st.markdown("##### Relationships")
        if not relationships_df.empty:
            st.dataframe(data=relationships_df, hide_index=True)
        else:
            st.markdown("No Relationships found.")
    else:
        st.markdown("No additional information available for this ID.")


# Fetch schema data based on the branch
infrahub_schema = get_cached_schema(branch=st.session_state.infrahub_branch)

if not infrahub_schema:
    handle_reachability_error()

else:
    # Process schema data to separate Generics and Nodes
    _generics = [item for item in infrahub_schema.values() if isinstance(item, GenericSchema)]
    _nodes = [item for item in infrahub_schema.values() if isinstance(item, NodeSchema)]

    # Create a Tab for "All Nodes" So if we want more Tab (i.e per Namespace) we could
    tabs = st.tabs(["All Nodes"])

    with tabs[0]:
        col1, col2 = st.columns([3, 1])

        with col1:
            _selected_id = visualize_schema_flow(generics=_generics, nodes=_nodes, key="schema_flow_all")

        with col2:
            # Display Tips
            display_expander(
                name="Interaction Tips",
                content="""
                - **Click on nodes** to view detailed information.
                - **Drag nodes** to reposition them in the graph.
                - **Use the controls** on the graph to zoom and pan.
                - **Hover over edges** to see relationship labels.
                - **Toggle the minimap** for an overview of the graph.
                """,
            )
            if _selected_id:
                st.markdown(f"### {_selected_id}")
                display_node_info(_selected_id, _generics, _nodes)
