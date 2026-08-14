"""Tests for emma.csv_import module."""

import numpy as np
import pandas as pd
import pytest
from infrahub_sdk.schema import GenericSchemaAPI, NodeSchemaAPI

from emma.csv_import import (
    Message,
    MessageSeverity,
    RelationshipResolutionError,
    csv_line_label,
    has_blocking_errors,
    is_generic_kind,
    normalize_dataframe,
    preprocess_and_validate_data,
    resolve_relationship_cell,
    resolve_relationship_value,
    split_relationship_reference,
    validate_columns,
)

SITE_ID = "18cbb512-48c4-83d6-3709-c517304acc89"
RACK_ID = "18cbb55b-ad24-637f-3702-c51bd62eb7fc"


@pytest.fixture(name="site_schema")
def fixture_site_schema() -> NodeSchemaAPI:
    """A node with a unique name and a mandatory dropdown."""
    return NodeSchemaAPI(
        name="Site",
        namespace="Lab",
        human_friendly_id=["name__value"],
        attributes=[
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "region", "kind": "Dropdown"},
        ],
        relationships=[],
    )


@pytest.fixture(name="rack_schema")
def fixture_rack_schema() -> NodeSchemaAPI:
    """A node with a mandatory relationship to a concrete peer."""
    return NodeSchemaAPI(
        name="Rack",
        namespace="Lab",
        human_friendly_id=["site__name__value", "name__value"],
        attributes=[
            {"name": "name", "kind": "Text"},
            {"name": "height_u", "kind": "Number", "optional": True},
        ],
        relationships=[
            {"name": "site", "peer": "LabSite", "cardinality": "one", "optional": False, "kind": "Parent"},
            {"name": "tags", "peer": "BuiltinTag", "cardinality": "many", "optional": True},
        ],
    )


@pytest.fixture(name="endpoint_schema")
def fixture_endpoint_schema() -> GenericSchemaAPI:
    """A generic, which cannot be referenced without naming a concrete kind."""
    return GenericSchemaAPI(name="Endpoint", namespace="Lab", attributes=[], relationships=[])


@pytest.fixture(name="cable_schema")
def fixture_cable_schema() -> NodeSchemaAPI:
    """A node whose relationship points at a generic."""
    return NodeSchemaAPI(
        name="Cable",
        namespace="Lab",
        attributes=[{"name": "name", "kind": "Text"}],
        relationships=[
            {"name": "endpoint", "peer": "LabEndpoint", "cardinality": "one", "optional": False},
        ],
    )


@pytest.fixture(name="branch_schemas")
def fixture_branch_schemas(site_schema, rack_schema, endpoint_schema, cable_schema) -> dict:
    """The schemas available on the branch, keyed by kind."""
    return {
        "LabSite": site_schema,
        "LabRack": rack_schema,
        "LabEndpoint": endpoint_schema,
        "LabCable": cable_schema,
    }


def resolver_returning(node_id: str):
    """Build a resolver that always resolves, recording how it was called."""
    calls = []

    def _resolve(kind: str, hfid: list) -> str:
        calls.append((kind, hfid))
        return node_id

    _resolve.calls = calls  # type: ignore[attr-defined]
    return _resolve


def resolver_raising(exc: Exception):
    """Build a resolver that always fails, as the SDK does for an unknown reference."""

    def _resolve(kind: str, hfid: list) -> str:
        raise exc

    return _resolve


class TestNormalizeDataframe:
    """Test normalize_dataframe function."""

    def test_strips_header_whitespace(self):
        """Test that surrounding whitespace is removed from column names."""
        df = pd.DataFrame({"site": ["rtp1"], "height_u ": [42], " name": ["R101"]})

        result = normalize_dataframe(df)

        assert list(result.columns) == ["site", "height_u", "name"]

    def test_strips_value_whitespace(self):
        """Test that surrounding whitespace is removed from string values."""
        df = pd.DataFrame({"site": [" rtp1 "], "name": ["R101\t"]})

        result = normalize_dataframe(df)

        assert result["site"][0] == "rtp1"
        assert result["name"][0] == "R101"

    def test_leaves_non_string_values_untouched(self):
        """Test that numeric columns survive normalisation."""
        df = pd.DataFrame({"height_u": [42, 45]})

        result = normalize_dataframe(df)

        assert list(result["height_u"]) == [42, 45]

    def test_replaces_empty_placeholders_with_nan(self):
        """Test that the placeholders for "no value" become NaN."""
        df = pd.DataFrame({"tags": ["[]", "", '""']})

        result = normalize_dataframe(df)

        assert result["tags"].isnull().all()

    def test_does_not_mutate_input(self):
        """Test that the caller's DataFrame is left alone."""
        df = pd.DataFrame({"height_u ": [42]})

        normalize_dataframe(df)

        assert list(df.columns) == ["height_u "]


class TestIsGenericKind:
    """Test is_generic_kind function."""

    def test_generic(self, branch_schemas):
        """Test that a generic is recognised."""
        assert is_generic_kind(kind="LabEndpoint", branch_schemas=branch_schemas) is True

    def test_node(self, branch_schemas):
        """Test that a node is not reported as a generic."""
        assert is_generic_kind(kind="LabSite", branch_schemas=branch_schemas) is False

    def test_unknown_kind(self, branch_schemas):
        """Test that an unknown kind is not reported as a generic."""
        assert is_generic_kind(kind="NopeMissing", branch_schemas=branch_schemas) is False


class TestSplitRelationshipReference:
    """Test split_relationship_reference function."""

    def test_bare_hfid_uses_peer_kind(self, branch_schemas):
        """Test that a bare value is resolved against the relationship's peer kind."""
        kind, hfid = split_relationship_reference(value="rtp1", peer_kind="LabSite", branch_schemas=branch_schemas)

        assert (kind, hfid) == ("LabSite", ["rtp1"])

    def test_kind_prefix_is_honoured(self, branch_schemas):
        """Test that a value naming a known kind uses that kind."""
        kind, hfid = split_relationship_reference(
            value="LabSite__rtp1", peer_kind="LabEndpoint", branch_schemas=branch_schemas
        )

        assert (kind, hfid) == ("LabSite", ["rtp1"])

    def test_multi_part_hfid_without_prefix(self, branch_schemas):
        """Test that a multi-part HFID is not mistaken for a kind prefix."""
        kind, hfid = split_relationship_reference(
            value="rtp1__R101", peer_kind="LabRack", branch_schemas=branch_schemas
        )

        assert (kind, hfid) == ("LabRack", ["rtp1", "R101"])

    def test_multi_part_hfid_with_prefix(self, branch_schemas):
        """Test that a kind prefix and a multi-part HFID combine."""
        kind, hfid = split_relationship_reference(
            value="LabRack__rtp1__R101", peer_kind="LabRack", branch_schemas=branch_schemas
        )

        assert (kind, hfid) == ("LabRack", ["rtp1", "R101"])


class TestResolveRelationshipValue:
    """Test resolve_relationship_value function."""

    def test_uuid_passes_through(self, branch_schemas):
        """Test that a UUID is used as-is without a lookup."""
        resolver = resolver_raising(AssertionError("should not be called"))

        result = resolve_relationship_value(
            value=SITE_ID,
            column="site",
            peer_kind="LabSite",
            branch_schemas=branch_schemas,
            resolver=resolver,
        )

        assert result == SITE_ID

    def test_bare_hfid_resolves(self, branch_schemas):
        """Test that a bare human-friendly ID resolves against the peer kind."""
        resolver = resolver_returning(SITE_ID)

        result = resolve_relationship_value(
            value="rtp1",
            column="site",
            peer_kind="LabSite",
            branch_schemas=branch_schemas,
            resolver=resolver,
        )

        assert result == SITE_ID
        assert resolver.calls == [("LabSite", ["rtp1"])]

    def test_kind_prefixed_hfid_resolves(self, branch_schemas):
        """Test that the kind-prefixed form still works."""
        resolver = resolver_returning(SITE_ID)

        result = resolve_relationship_value(
            value="LabSite__rtp1",
            column="site",
            peer_kind="LabSite",
            branch_schemas=branch_schemas,
            resolver=resolver,
        )

        assert result == SITE_ID
        assert resolver.calls == [("LabSite", ["rtp1"])]

    def test_lookup_failure_raises_resolution_error(self, branch_schemas):
        """Test that a failed lookup becomes a RelationshipResolutionError."""
        resolver = resolver_raising(ValueError("Unable to find the node"))

        with pytest.raises(RelationshipResolutionError) as exc_info:
            resolve_relationship_value(
                value="nope1",
                column="site",
                peer_kind="LabSite",
                branch_schemas=branch_schemas,
                resolver=resolver,
            )

        message = str(exc_info.value)
        assert "'nope1'" in message
        assert "'site'" in message
        assert "LabSite" in message

    def test_empty_result_raises_resolution_error(self, branch_schemas):
        """Test that a resolver returning nothing is treated as a failure."""
        resolver = resolver_returning("")

        with pytest.raises(RelationshipResolutionError, match="no matching node"):
            resolve_relationship_value(
                value="nope1",
                column="site",
                peer_kind="LabSite",
                branch_schemas=branch_schemas,
                resolver=resolver,
            )

    def test_generic_peer_failure_explains_kind_prefix(self, branch_schemas):
        """Test that failing against a generic peer suggests naming a concrete kind."""
        resolver = resolver_raising(ValueError("cannot use hfid on a generic"))

        with pytest.raises(RelationshipResolutionError) as exc_info:
            resolve_relationship_value(
                value="eth0",
                column="endpoint",
                peer_kind="LabEndpoint",
                branch_schemas=branch_schemas,
                resolver=resolver,
            )

        assert "generic" in str(exc_info.value)
        assert "MyKind__eth0" in str(exc_info.value)


class TestResolveRelationshipCell:
    """Test resolve_relationship_cell function."""

    def test_single_reference(self, branch_schemas):
        """Test that a plain value resolves to one id."""
        result = resolve_relationship_cell(
            value="rtp1",
            column="site",
            peer_kind="LabSite",
            branch_schemas=branch_schemas,
            resolver=resolver_returning(SITE_ID),
        )

        assert result == SITE_ID

    def test_list_of_references(self, branch_schemas):
        """Test that a list-like value resolves to a list of ids."""
        resolver = resolver_returning(SITE_ID)

        result = resolve_relationship_cell(
            value="['rtp1', 'sjc2']",
            column="site",
            peer_kind="LabSite",
            branch_schemas=branch_schemas,
            resolver=resolver,
        )

        assert result == [SITE_ID, SITE_ID]
        assert resolver.calls == [("LabSite", ["rtp1"]), ("LabSite", ["sjc2"])]

    def test_unparseable_bracketed_value_is_reported_not_raised(self, branch_schemas):
        """Test that a bracketed value that is not a list literal fails cleanly.

        ``literal_eval`` raises SyntaxError on input like this, which previously
        escaped as an unhandled traceback.
        """
        with pytest.raises(RelationshipResolutionError, match=r"\[1:2\]"):
            resolve_relationship_cell(
                value="[1:2]",
                column="site",
                peer_kind="LabSite",
                branch_schemas=branch_schemas,
                resolver=resolver_raising(ValueError("Unable to find the node")),
            )

    def test_bracketed_non_list_literal_is_resolved_as_one_reference(self, branch_schemas):
        """Test that a bracketed non-list literal falls back to a single lookup."""
        resolver = resolver_returning(SITE_ID)

        result = resolve_relationship_cell(
            value="[42]",
            column="site",
            peer_kind="LabSite",
            branch_schemas=branch_schemas,
            resolver=resolver,
        )

        # literal_eval yields a list here, so each item is resolved individually.
        assert result == [SITE_ID]


class TestValidateColumns:
    """Test validate_columns function."""

    def test_all_columns_present(self, rack_schema):
        """Test that a usable file produces no messages."""
        messages = validate_columns(["site", "name", "height_u"], rack_schema)

        assert messages == []

    def test_missing_mandatory_column_is_an_error(self, rack_schema):
        """Test that a missing mandatory column is reported as an error."""
        messages = validate_columns(["name", "height_u"], rack_schema)

        assert len(messages) == 1
        assert messages[0].severity == MessageSeverity.ERROR
        assert "'site'" in messages[0].message

    def test_unmappable_column_is_a_warning(self, rack_schema):
        """Test that an unrecognised column only warns, since the rest is importable."""
        messages = validate_columns(["site", "name", "nope"], rack_schema)

        assert len(messages) == 1
        assert messages[0].severity == MessageSeverity.WARNING
        assert "'nope'" in messages[0].message

    def test_unmappable_column_message_quotes_whitespace(self, rack_schema):
        """Test that invisible whitespace in a column name is visible in the message."""
        messages = validate_columns(["site", "name", "height_u "], rack_schema)

        assert "'height_u '" in messages[0].message


class TestPreprocessAndValidateData:
    """Test preprocess_and_validate_data function."""

    def test_attributes_pass_through(self, site_schema, branch_schemas):
        """Test that attribute values are used unchanged."""
        df = pd.DataFrame({"name": ["rtp1", "sjc2"], "region": ["amer", "amer"]})

        processed, messages = preprocess_and_validate_data(
            df=df,
            schema=site_schema,
            branch_schemas=branch_schemas,
            resolver=resolver_raising(AssertionError("no relationships here")),
        )

        assert messages == []
        assert processed.to_dict("records") == [
            {"name": "rtp1", "region": "amer"},
            {"name": "sjc2", "region": "amer"},
        ]

    def test_relationship_resolved_to_id(self, rack_schema, branch_schemas):
        """Test that a bare relationship reference is resolved to the peer id."""
        df = pd.DataFrame({"site": ["rtp1"], "name": ["R101"], "height_u": [42]})

        processed, messages = preprocess_and_validate_data(
            df=df,
            schema=rack_schema,
            branch_schemas=branch_schemas,
            resolver=resolver_returning(SITE_ID),
        )

        assert messages == []
        assert processed.to_dict("records") == [{"site": SITE_ID, "name": "R101", "height_u": 42}]

    def test_unresolvable_relationship_reported_per_line(self, rack_schema, branch_schemas):
        """Test that a bad reference is reported against its CSV line, not raised."""
        df = pd.DataFrame({"site": ["rtp1", "nope1"], "name": ["R101", "R102"]})

        def _resolve(kind: str, hfid: list) -> str:
            if hfid == ["nope1"]:
                raise ValueError("Unable to find the node")
            return SITE_ID

        processed, messages = preprocess_and_validate_data(
            df=df,
            schema=rack_schema,
            branch_schemas=branch_schemas,
            resolver=_resolve,
        )

        errors = [message for message in messages if message.severity == MessageSeverity.ERROR]
        assert len(errors) == 1
        assert errors[0].message.startswith("Line 3:")
        # The good row is still processed, so the user sees every problem in one pass.
        assert processed.to_dict("records")[0]["site"] == SITE_ID

    def test_null_values_are_skipped(self, rack_schema, branch_schemas):
        """Test that empty cells are omitted rather than sent as NaN."""
        df = pd.DataFrame({"site": ["rtp1"], "name": ["R101"], "height_u": [np.nan]})

        processed, _ = preprocess_and_validate_data(
            df=df,
            schema=rack_schema,
            branch_schemas=branch_schemas,
            resolver=resolver_returning(SITE_ID),
        )

        assert "height_u" not in processed.columns

    def test_unmappable_column_is_dropped_but_warned(self, rack_schema, branch_schemas):
        """Test that an unrecognised column warns and does not reach Infrahub."""
        df = pd.DataFrame({"site": ["rtp1"], "name": ["R101"], "nope": ["x"]})

        processed, messages = preprocess_and_validate_data(
            df=df,
            schema=rack_schema,
            branch_schemas=branch_schemas,
            resolver=resolver_returning(SITE_ID),
        )

        assert [message.severity for message in messages] == [MessageSeverity.WARNING]
        assert "nope" not in processed.columns

    def test_whitespace_header_is_usable_after_normalisation(self, rack_schema, branch_schemas):
        """Test the reported case: a trailing space in a header no longer blocks import."""
        raw = pd.DataFrame({"site": ["rtp1"], "name": ["R101"], "height_u ": [42]})

        processed, messages = preprocess_and_validate_data(
            df=normalize_dataframe(raw),
            schema=rack_schema,
            branch_schemas=branch_schemas,
            resolver=resolver_returning(SITE_ID),
        )

        assert messages == []
        assert processed.to_dict("records") == [{"site": SITE_ID, "name": "R101", "height_u": 42}]


class TestCsvLineLabel:
    """Test csv_line_label function."""

    def test_accounts_for_the_header_row(self):
        """Test that the first data row is reported as line 2."""
        assert csv_line_label(0) == "Line 2"
        assert csv_line_label(3) == "Line 5"


class TestHasBlockingErrors:
    """Test has_blocking_errors function."""

    def test_empty(self):
        """Test that no messages means nothing is blocking."""
        assert has_blocking_errors([]) is False

    def test_warnings_do_not_block(self):
        """Test that warnings alone do not stop an import."""
        messages = [Message(severity=MessageSeverity.WARNING, message="ignored column")]

        assert has_blocking_errors(messages) is False

    def test_info_does_not_block(self):
        """Test that informational messages do not stop an import."""
        messages = [Message(severity=MessageSeverity.INFO, message="fyi")]

        assert has_blocking_errors(messages) is False

    def test_errors_block(self):
        """Test that a single error stops an import."""
        messages = [
            Message(severity=MessageSeverity.WARNING, message="ignored column"),
            Message(severity=MessageSeverity.ERROR, message="missing column"),
        ]

        assert has_blocking_errors(messages) is True
