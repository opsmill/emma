"""Validation and preprocessing logic for the CSV Data Importer.

This module holds the pure, Streamlit-independent part of the importer so it can be
unit tested. The page in ``pages/data_importer.py`` owns the UI and supplies the
callable that resolves relationship references against a live Infrahub instance.
"""

from __future__ import annotations

from ast import literal_eval
from enum import Enum
from typing import Any, Callable, List, Union

import numpy as np
import pandas as pd
from infrahub_sdk.schema import GenericSchema, GenericSchemaAPI, MainSchemaTypesAPI
from infrahub_sdk.utils import compare_lists
from pandas.api.types import is_object_dtype, is_string_dtype
from pydantic import BaseModel

from emma.utils import is_uuid, parse_hfid

# Resolves (kind, hfid components) to the id of the matching node.
NodeResolver = Callable[[str, List[str]], str]

# Cell contents that stand for "no value" rather than a value.
EMPTY_PLACEHOLDERS = frozenset(["", "[]", '""'])


class MessageSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Message(BaseModel):
    severity: MessageSeverity = MessageSeverity.INFO
    message: str


class RelationshipResolutionError(Exception):
    """Raised when a relationship value in a CSV file cannot be matched to a node."""

    def __init__(self, *, column: str, value: str, kind: str, hfid: List[str], reason: str, hint: str = "") -> None:
        self.column = column
        self.value = value
        self.kind = kind
        self.hfid = hfid
        self.reason = reason
        self.hint = hint
        message = (
            f"could not resolve {value!r} in column {column!r}: "
            f"no {kind} found with human-friendly ID {hfid}. ({reason})"
        )
        if hint:
            message = f"{message} {hint}"
        super().__init__(message)


def _clean_cell(value: Any) -> Any:
    """Strip a string cell and turn the "no value" placeholders into NaN.

    Args:
        value: The raw cell value.

    Returns:
        The stripped value, NaN if it only held a placeholder, or the value unchanged
        if it is not a string.
    """
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    return np.nan if stripped in EMPTY_PLACEHOLDERS else stripped


def normalize_dataframe(data_frame: pd.DataFrame) -> pd.DataFrame:
    """Clean up a freshly parsed CSV file.

    Surrounding whitespace in a header or a cell is almost always accidental, but it
    makes a column fail to match the schema and a relationship reference fail to
    resolve, so it is stripped here. Placeholders for "no value" are normalised to
    NaN so downstream code can skip them with a single ``pd.isnull`` check.

    Args:
        data_frame: The DataFrame as returned by ``pd.read_csv``.

    Returns:
        A new DataFrame with stripped headers and values.
    """
    cleaned = data_frame.copy()
    cleaned.columns = [str(column).strip() for column in cleaned.columns]
    for column in cleaned.columns:
        # pandas 2 reads text columns as object, pandas 3 as its own str dtype, so both
        # have to be recognised here or the cells go unprocessed.
        if is_object_dtype(cleaned[column]) or is_string_dtype(cleaned[column]):
            cleaned[column] = cleaned[column].map(_clean_cell)
    return cleaned


def is_generic_kind(kind: str, branch_schemas: dict[str, MainSchemaTypesAPI]) -> bool:
    """Check whether a kind refers to a generic rather than a node.

    Args:
        kind: The kind to look up.
        branch_schemas: All schemas available on the current branch, keyed by kind.

    Returns:
        True if the kind is known and is a generic.
    """
    schema = branch_schemas.get(kind)
    return isinstance(schema, (GenericSchema, GenericSchemaAPI))


def split_relationship_reference(
    value: str,
    peer_kind: str,
    branch_schemas: dict[str, MainSchemaTypesAPI],
) -> tuple[str, List[str]]:
    """Work out which kind to query and which HFID components to query it with.

    Two forms are accepted. A bare human-friendly ID (``rtp1``, or ``rtp1__R101``
    for a multi-part HFID) is resolved against the kind declared by the
    relationship. A value may also name the kind explicitly (``LabSite__rtp1``),
    which is the only way to reference a peer when the relationship points at a
    generic and the concrete kind cannot be inferred.

    Args:
        value: The raw cell value.
        peer_kind: The kind the relationship points at, per the schema.
        branch_schemas: All schemas available on the current branch, keyed by kind.

    Returns:
        The kind to query and the HFID components to query it with.
    """
    components = parse_hfid(hfid=value)
    if len(components) > 1 and components[0] in branch_schemas:
        return components[0], components[1:]
    return peer_kind, components


def resolve_relationship_value(
    value: Any,
    column: str,
    peer_kind: str,
    branch_schemas: dict[str, MainSchemaTypesAPI],
    resolver: NodeResolver,
) -> str:
    """Resolve a single relationship reference to the id of the peer node.

    Args:
        value: The raw cell value: a UUID, a human-friendly ID, or a kind-prefixed
            human-friendly ID.
        column: The column the value came from, used for error reporting.
        peer_kind: The kind the relationship points at, per the schema.
        branch_schemas: All schemas available on the current branch, keyed by kind.
        resolver: Callable that looks up a node and returns its id.

    Returns:
        The id of the peer node.

    Raises:
        RelationshipResolutionError: When no node matches the reference.
    """
    if is_uuid(value):
        return str(value)

    # A cell may hold a number, for example a list of numeric names, so work with the
    # string form from here on.
    reference = str(value)
    kind, hfid = split_relationship_reference(value=reference, peer_kind=peer_kind, branch_schemas=branch_schemas)
    hint = ""
    if is_generic_kind(kind=kind, branch_schemas=branch_schemas):
        hint = (
            f"{kind} is a generic, so the value must name the concrete kind of the peer, "
            f"for example 'MyKind__{reference}'."
        )

    try:
        node_id = resolver(kind, hfid)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        raise RelationshipResolutionError(
            column=column, value=reference, kind=kind, hfid=hfid, reason=str(exc), hint=hint
        ) from exc

    if not node_id:
        raise RelationshipResolutionError(
            column=column, value=reference, kind=kind, hfid=hfid, reason="no matching node", hint=hint
        )
    return str(node_id)


def resolve_relationship_cell(
    value: Any,
    column: str,
    peer_kind: str,
    branch_schemas: dict[str, MainSchemaTypesAPI],
    resolver: NodeResolver,
) -> Union[str, List[str]]:
    """Resolve a relationship cell holding either one reference or a list of them.

    Args:
        value: The raw cell value. A list is written as ``"['rtp1', 'sjc2']"``.
        column: The column the value came from, used for error reporting.
        peer_kind: The kind the relationship points at, per the schema.
        branch_schemas: All schemas available on the current branch, keyed by kind.
        resolver: Callable that looks up a node and returns its id.

    Returns:
        The id of the peer node, or the list of ids for a cardinality-many
        relationship.

    Raises:
        RelationshipResolutionError: When a reference cannot be matched to a node.
    """
    if isinstance(value, str) and value.startswith("[") and value.endswith("]"):
        try:
            parsed_value: Any = literal_eval(value)
        except (SyntaxError, ValueError):
            # Not a Python list literal after all, so treat it as one reference and
            # let resolution report it against its line.
            parsed_value = None
        if isinstance(parsed_value, list):
            return [
                resolve_relationship_value(
                    value=item,
                    column=column,
                    peer_kind=peer_kind,
                    branch_schemas=branch_schemas,
                    resolver=resolver,
                )
                for item in parsed_value
            ]

    return resolve_relationship_value(
        value=value,
        column=column,
        peer_kind=peer_kind,
        branch_schemas=branch_schemas,
        resolver=resolver,
    )


def validate_columns(df_columns: list, target_schema: MainSchemaTypesAPI) -> List[Message]:
    """Check the CSV columns against the schema.

    A missing mandatory column is an error: the import cannot succeed. A column that
    matches nothing in the schema is only a warning, because the rest of the file is
    still importable without it.

    Args:
        df_columns: The column names found in the CSV file.
        target_schema: The schema of the kind being imported.

    Returns:
        One message per problem found, empty if the columns are usable as-is.
    """
    messages = []
    _, _, missing_mandatory = compare_lists(list1=df_columns, list2=target_schema.mandatory_input_names)
    for item in missing_mandatory:
        messages.append(Message(severity=MessageSeverity.ERROR, message=f"Mandatory column missing: {item!r}"))

    _, additional, _ = compare_lists(
        list1=df_columns, list2=target_schema.relationship_names + target_schema.attribute_names
    )
    for item in additional:
        messages.append(
            Message(
                severity=MessageSeverity.WARNING,
                message=(
                    f"Column {item!r} does not match any attribute or relationship of "
                    f"{target_schema.kind} and will be ignored"
                ),
            )
        )
    return messages


def preprocess_and_validate_data(
    df: pd.DataFrame,
    schema: MainSchemaTypesAPI,
    branch_schemas: dict[str, MainSchemaTypesAPI],
    resolver: NodeResolver,
) -> tuple[pd.DataFrame, List[Message]]:
    """Turn a parsed CSV file into rows ready to be sent to Infrahub.

    Attribute values are passed through untouched; relationship references are
    resolved to peer node ids. A reference that cannot be resolved is reported as an
    error against its line rather than aborting the whole file, so the user sees every
    problem in one pass.

    Args:
        df: The normalised DataFrame to process.
        schema: The schema of the kind being imported.
        branch_schemas: All schemas available on the current branch, keyed by kind.
        resolver: Callable that looks up a node and returns its id.

    Returns:
        The processed rows, and the messages raised while validating them.
    """
    messages = validate_columns(list(df.columns), schema)
    processed_rows = []

    for position, (_, items_row) in enumerate(df.iterrows()):
        processed_row: dict[str, Any] = {}
        for column, value in items_row.items():
            if pd.isnull(value):
                continue

            if column in schema.relationship_names:
                relation_schema = schema.get_relationship(column)
                try:
                    processed_row[column] = resolve_relationship_cell(
                        value=value,
                        column=str(column),
                        peer_kind=relation_schema.peer,
                        branch_schemas=branch_schemas,
                        resolver=resolver,
                    )
                except RelationshipResolutionError as exc:
                    messages.append(
                        Message(severity=MessageSeverity.ERROR, message=f"{csv_line_label(position)}: {exc}")
                    )

            elif column in schema.attribute_names:
                # Directly use attribute values
                processed_row[column] = value

        processed_rows.append(processed_row)

    return pd.DataFrame(processed_rows), messages


def csv_line_label(position: int) -> str:
    """Describe a row by its line number in the original file.

    Args:
        position: The zero-based position of the row within the data rows.

    Returns:
        A label naming the line as it appears in the CSV file, header included.
    """
    return f"Line {position + 2}"


def has_blocking_errors(messages: List[Message]) -> bool:
    """Check whether any message is severe enough to stop the import.

    Args:
        messages: The messages raised while validating a file.

    Returns:
        True if at least one message is an error.
    """
    return any(message.severity == MessageSeverity.ERROR for message in messages)
