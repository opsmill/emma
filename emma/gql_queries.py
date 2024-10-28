from typing import Optional

from graphql import (
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    build_client_schema,
    get_introspection_query,
)
from langchain.tools import tool

from emma.infrahub import get_client

EXCLUDED_TYPES = (
    "count",
    "id",
    "is_default",
    "is_inherited",
    "is_protected",
    "is_visible",
    "updated_at",
    "is_from_profile",
    "source",
    "owner",
    "color",
    "_updated_at",
    "tags",
    "member_of_groups",
    "subscriber_of_groups",
    "profiles",
    "properties",
    "__typename",
)


def exclude_keys(d, exclude_list=EXCLUDED_TYPES):
    if not isinstance(d, dict):
        return d  # Base case: if it's not a dict, return it as-is
    return {k: exclude_keys(v, exclude_list) for k, v in d.items() if k not in EXCLUDED_TYPES}


def dict_to_gql_query(d, indent_level=0):
    indent = "  " * indent_level
    gql_str = ""

    for key, value in d.items():
        # Check if filters are present
        filters = ""
        if isinstance(value, dict) and "@filters" in value:
            filter_dict = value.pop("@filters")  # Grab the filters and remove from dict
            if filter_dict:
                filters = " (" + " ".join(f'{k}: "{v}"' for k, v in filter_dict.items()) + ")"

        # If value is a dict and has other nested fields, recurse
        if isinstance(value, dict):
            gql_str += f"{indent}{key}{filters} {{\n"
            gql_str += dict_to_gql_query(value, indent_level + 1)
            gql_str += f"{indent}}}\n"
        else:
            gql_str += f"{indent}{key}\n"

    return gql_str


def get_gql_schema(branch: Optional[str] = None) -> Optional[GraphQLObjectType]:
    client = get_client(branch=branch)
    schema_query = get_introspection_query()
    introspection_result = client.execute_graphql(schema_query)

    if introspection_result:
        schema = build_client_schema(introspection_result)
        return schema.query_type  # Return the root query object directly

    return None


def generate_query(object_type: GraphQLObjectType, visited_types: Optional[set] = None) -> str: # noqa: PLR0912
    if visited_types is None:
        visited_types = set()

    query_parts = []
    for field_name, field in object_type.fields.items():
        field_type = field.type

        if field_name in EXCLUDED_TYPES:
            continue

        # Unwrap list and non-null types
        while isinstance(field_type, (GraphQLList, GraphQLNonNull)):
            field_type = field_type.of_type

        # Handle object types (e.g., GraphQLObjectType)
        if isinstance(field_type, GraphQLObjectType):
            if field_type.name not in visited_types:
                visited_types.add(field_type.name)
                sub_query = generate_query(field_type, visited_types).strip()

                # If the sub_query isn't empty, include the field
                if sub_query and sub_query != "node":
                    if field_name == "node":
                        query_parts.append(f"{field_name} {{ {sub_query} }} ")
                    else:
                        query_parts.append(f"{field_name} {{ {sub_query} }} ")

        # Handle polymorphic fields (unions or interfaces)
        elif hasattr(field_type, "possibleTypes"):
            fragment_queries = []
            for possible_type in field_type.possible_types:
                fragment_query = generate_query(possible_type, visited_types)
                if fragment_query.strip():
                    fragment_queries.append(f"... on {possible_type.name} {{ {fragment_query} }}")
            if fragment_queries:
                query_parts.append(f"{field_name} {{ {' '.join(fragment_queries)} }} ")

        # Handle scalar fields (e.g., strings, ints)
        else:
            query_parts.append(f"{field_name} ")

    # Join all valid parts into a query. If empty, return nothing.
    return " ".join(query_parts)


@tool
def generate_full_query(branch: Optional[str], root_object_name: str) -> Optional[str]:
    """
    Generates a comprehensive GraphQL query for a specified root object, including all its fields
    and nested sub-objects, based on the schema retrieved from the specified branch.

    This function is designed to dynamically build a GraphQL query that retrieves all the data
    available for a given root object, effectively showcasing everything that can be pulled from
    the GraphQL API for that object. It recursively traverses the schema to include all fields
    and nested sub-fields, ensuring that the query is exhaustive.

    Parameters:
    -----------
    branch : Optional[str]
        The branch name to target when fetching the GraphQL schema. If `None`, the default branch
        or configuration is used. This allows flexibility in environments where schema versions
        may vary across branches.

    root_object_name : str
        The name of the root object for which the query is to be generated. This is the entry
        point for the query, and the function will explore and include all fields associated
        with this object.

    Returns:
    --------
    Optional[str]
        A string containing the fully constructed GraphQL query. If the root object does not exist
        or is not of a type that can be queried (e.g., not an `OBJECT` type), the function returns
        `None`.

    Usage:
    ------
    Use this function when you need to understand or retrieve all possible data for a specific
    object in your GraphQL schema. It is particularly useful for developers or users who want
    to ensure they are querying all relevant fields, including deeply nested sub-objects, without
    manually constructing each part of the query.

    Example:
    --------
    ```
    query = generate_full_query(branch="feature-branch", root_object_name="User")
    print(query)
    # Output:
    # {
    #   User {
    #     id
    #     name
    #     email
    #     posts {
    #       id
    #       title
    #       content
    #       comments {
    #         id
    #         content
    #       }
    #     }
    #   }
    # }
    ```
    This output demonstrates a query that retrieves all fields for a "User" object, including
    nested fields for associated posts and comments.
    """
    query_type = get_gql_schema(branch)

    root_object = None if not query_type else query_type.fields.get(root_object_name)  # type: ignore[union-attr]

    if not query_type or not root_object:
        return "NOT_FOUND"

    root_object_type = root_object.type

    # Unwrap non-nullable and list types if necessary
    while isinstance(root_object_type, (GraphQLList, GraphQLNonNull)):
        root_object_type = root_object_type.of_type

    if not isinstance(root_object_type, GraphQLObjectType):
        return "NOT_FOUND"

    query = generate_query(root_object_type)

    return f"{{ {root_object_name} {{ {query} }} }}"


if __name__ == "__main__":
    # For testing sake
    print(generate_full_query.run(tool_input={"branch": None, "root_object_name": "InfraInterfaceL3"}))  # type: ignore[attr-defined]
