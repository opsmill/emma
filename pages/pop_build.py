from typing import Any, Dict

import streamlit as st
import pandas as pd
from infrahub_sdk import RelationshipKind


from emma.infrahub import get_candidate_related_nodes, get_client,  get_node_schema 
from emma.streamlit_utils import set_page_config
from menu import menu_with_redirect


set_page_config(title="Pop Builder")
st.markdown("# Pop Builder")
menu_with_redirect()
submit = False

def dict_remove_nan_values(dictionary: Dict[str, Any]) -> Dict[str, Any]:
    remove = [k for k, v in dictionary.items() if pd.isnull(v)]
    for k in remove:
        dictionary.pop(k)
    return dictionary

def norm_role(role: str) -> str:
    roles = {
        "ex-core": "ex_core",
        "ex-agg": "agg",
        "tor": "tor",
        "ms": "ms",
        "oob": "console",
        "ms-ag": "ms_agg",
        "ms-core": "ms_core",
    }
    return roles.get(role, role)

service_kind = "PopBuild"
service_group = "site_generator"
service_schema = get_node_schema(kind=service_kind, branch=st.session_state.infrahub_branch)

form_ignore_relationship: Dict[str, Dict[Any, Any]] = {
    "rack_details": {
        "widget": st.file_uploader,
        "args": {
            "label": "Rack details CSV",
            "type": ["csv"]
        },
        "type": "BuildDevice"
    }
}
form_values = {}
relationship_candidates = get_candidate_related_nodes(schema_node=service_schema, branch=st.session_state.infrahub_branch)

if service_schema:
    with st.form("pop-build"):
        for attribute in service_schema.attributes:
            if attribute.kind == "Text":
                form_values[attribute.name] = st.text_input(attribute.label)
            elif attribute.kind == "Number":
                form_values[attribute.name] = st.number_input(attribute.label, step=1)
            elif attribute.kind == "Dropdown":
                form_values[attribute.name] = st.selectbox(attribute.label, [choice["name"] for choice in attribute.choices])
            elif attribute.kind == "List":
                form_values[attribute.name] = st.text_area(attribute.label)

        for relation in service_schema.relationships:
            if relation.name in form_ignore_relationship:
                continue
            if relation.kind != RelationshipKind.GENERIC:
                continue
            if relation.cardinality == "many":
                form_values[relation.name] = st.multiselect(relation.label or "", [r.display_label for r in relationship_candidates[relation.peer]])
            elif relation.cardinality == "one":
                form_values[relation.name] = st.selectbox(relation.label or "", [r.display_label for r in relationship_candidates[relation.peer]])
        for relation, form_widget in form_ignore_relationship.items():
            form_values[relation] = form_widget["widget"](**form_widget["args"])
            
        submit = st.form_submit_button("Submit")

        if submit:
            client = get_client(branch=st.session_state.infrahub_branch)

            for attribute in service_schema.attributes:
                if attribute.kind == "List":
                    form_values[attribute.name] = form_values[attribute.name].split("\n")

            for relation in service_schema.relationships:
                if relation.name in form_ignore_relationship:
                    continue
                if relation.kind != RelationshipKind.GENERIC:
                    continue
                if relation.cardinality == "many":
                    ids = []
                    for value in form_values[relation.name]:
                        for r in relationship_candidates[relation.peer]:
                            if r.display_label == value:
                                ids.append(r.id)
                    form_values[relation.name] = ids
                elif relation.cardinality == "one":
                    for r in relationship_candidates[relation.peer]:
                        if r.display_label == form_values[relation.name]:
                            form_values[relation.name] = r.id
                            break

            for relation, form_widget in form_ignore_relationship.items():
                nodes = []
                dataframe = pd.read_csv(filepath_or_buffer=form_values[relation])

                for index, row in dataframe.iterrows():
                    data = dict_remove_nan_values(dict(row))
                    data["role"] = norm_role(data["role"])
                    obj = client.create(kind=form_widget["type"], **data)
                    obj.save()
                    nodes.append(obj.id)

                form_values[relation] = nodes


            obj = client.create(kind="PopBuild", **form_values)
            obj.save()

            group = client.get("CoreStandardGroup", name__value=service_group, include=["members"], prefetch_relationships=True)
            group.members.add(obj)
            group.save()
