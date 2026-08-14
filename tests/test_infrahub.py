"""Tests for get_version_async, run_gql_query and execute_batch in emma.infrahub."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.node import InfrahubNode

from emma.infrahub import (
    describe_related_node,
    execute_batch,
    get_node_from_store,
    get_version_async,
    run_gql_query,
)


def make_node(kind: str = "LabSite", hfid=None, node_id: str = "abc123") -> MagicMock:
    """Build a stand-in for an InfrahubNode as execute_batch consumes it."""
    node = MagicMock()
    node.hfid = hfid
    node.id = node_id
    node.get_human_friendly_id_as_string.return_value = "__".join(hfid) if hfid else ""
    node._schema.kind = kind
    node._schema.default_filter = None
    return node


def make_batch(results: list) -> MagicMock:
    """Build a stand-in batch that yields the given (node, result) pairs."""

    async def _execute():
        for node, result in results:
            yield node, result

    batch = MagicMock()
    batch.execute = _execute
    batch.num_tasks = len(results)
    return batch


class TestGetVersionAsync:
    """Test get_version_async function."""

    def test_returns_version_string(self):
        """Test that the version string is returned from the GraphQL response."""
        client = MagicMock()
        client.execute_graphql = AsyncMock(return_value={"InfrahubInfo": {"version": "1.2.3"}})

        result = asyncio.run(get_version_async(client))

        assert result == "1.2.3"
        client.execute_graphql.assert_called_once_with(query="query { InfrahubInfo { version }}")

    def test_propagates_graphql_error(self):
        """Test that GraphQL errors propagate to the caller."""
        client = MagicMock()
        client.execute_graphql = AsyncMock(side_effect=GraphQLError(errors=[{"message": "bad query"}]))

        with pytest.raises(GraphQLError):
            asyncio.run(get_version_async(client))

    def test_does_not_pass_raise_for_error(self):
        """Test that raise_for_error is not explicitly passed (uses default)."""
        client = MagicMock()
        client.execute_graphql = AsyncMock(return_value={"InfrahubInfo": {"version": "0.1.0"}})

        asyncio.run(get_version_async(client))

        _, kwargs = client.execute_graphql.call_args
        assert "raise_for_error" not in kwargs


class TestRunGqlQuery:
    """Test run_gql_query function."""

    def test_success_returns_dict(self, monkeypatch):
        """Test that a successful query returns the result as a dict."""
        mock_client = MagicMock()
        mock_client.execute_graphql = AsyncMock(return_value={"TestQuery": {"name": "foo"}})
        monkeypatch.setattr("emma.infrahub.get_client_async", AsyncMock(return_value=mock_client))

        result = asyncio.run(run_gql_query.__wrapped__("{ TestQuery { name } }"))

        assert result == {"TestQuery": {"name": "foo"}}
        mock_client.execute_graphql.assert_called_once_with("{ TestQuery { name } }", branch_name=None)

    def test_success_with_branch(self, monkeypatch):
        """Test that branch_name is forwarded to execute_graphql."""
        mock_client = MagicMock()
        mock_client.execute_graphql = AsyncMock(return_value={"data": "value"})
        monkeypatch.setattr("emma.infrahub.get_client_async", AsyncMock(return_value=mock_client))

        result = asyncio.run(run_gql_query.__wrapped__("{ Q }", branch="dev"))

        assert result == {"data": "value"}
        mock_client.execute_graphql.assert_called_once_with("{ Q }", branch_name="dev")

    def test_graphql_error_returns_empty_dict(self, monkeypatch):
        """Test that a GraphQLError is caught and returns an empty dict."""
        mock_client = MagicMock()
        mock_client.execute_graphql = AsyncMock(side_effect=GraphQLError(errors=[{"message": "fail"}]))
        monkeypatch.setattr("emma.infrahub.get_client_async", AsyncMock(return_value=mock_client))

        result = asyncio.run(run_gql_query.__wrapped__("{ bad }"))

        assert result == {}

    def test_http_status_error_returns_empty_dict(self, monkeypatch):
        """Test that an HTTPStatusError is caught and returns an empty dict."""
        mock_client = MagicMock()
        response = httpx.Response(status_code=500, request=httpx.Request("POST", "http://test"))
        mock_client.execute_graphql = AsyncMock(
            side_effect=httpx.HTTPStatusError("server error", request=response.request, response=response)
        )
        monkeypatch.setattr("emma.infrahub.get_client_async", AsyncMock(return_value=mock_client))

        result = asyncio.run(run_gql_query.__wrapped__("{ bad }"))

        assert result == {}

    def test_unexpected_error_propagates(self, monkeypatch):
        """Test that unexpected exceptions are not caught and propagate."""
        mock_client = MagicMock()
        mock_client.execute_graphql = AsyncMock(side_effect=RuntimeError("unexpected"))
        monkeypatch.setattr("emma.infrahub.get_client_async", AsyncMock(return_value=mock_client))

        with pytest.raises(RuntimeError, match="unexpected"):
            asyncio.run(run_gql_query.__wrapped__("{ bad }"))

    def test_none_result_returns_empty_dict(self, monkeypatch):
        """Test that a None result from execute_graphql returns an empty dict."""
        mock_client = MagicMock()
        mock_client.execute_graphql = AsyncMock(return_value=None)
        monkeypatch.setattr("emma.infrahub.get_client_async", AsyncMock(return_value=mock_client))

        result = asyncio.run(run_gql_query.__wrapped__("{ Q }"))

        assert result == {}


class TestExecuteBatch:
    """Test execute_batch function."""

    def test_returns_zero_when_every_task_succeeds(self, monkeypatch):
        """Test that a fully successful batch reports no errors."""
        monkeypatch.setattr("emma.infrahub.st", MagicMock())
        batch = make_batch([(make_node(hfid=["rtp1"]), "ok"), (make_node(hfid=["sjc2"]), "ok")])

        assert asyncio.run(execute_batch.__wrapped__(batch=batch)) == 0

    def test_counts_failed_tasks(self, monkeypatch):
        """Test that per-task exceptions are counted rather than reported as success.

        The batch is created with return_exceptions=True, so a failing task is handed
        back as a result instead of being raised. Those failures used to be displayed
        but not counted, which made a wholly failed import report success.
        """
        mock_st = MagicMock()
        monkeypatch.setattr("emma.infrahub.st", mock_st)
        batch = make_batch(
            [
                (make_node(hfid=["rtp1"]), "ok"),
                (make_node(hfid=["RTP-BIG-SITE"]), GraphQLError(errors=[{"message": "regex violation"}])),
                (make_node(hfid=["lon3"]), GraphQLError(errors=[{"message": "bad choice"}])),
            ]
        )

        assert asyncio.run(execute_batch.__wrapped__(batch=batch)) == 2
        assert mock_st.error.call_count == 2
        assert mock_st.success.call_count == 1

    def test_counts_unexpected_errors(self, monkeypatch):
        """Test that an error raised while reporting a task is counted too."""
        mock_st = MagicMock()
        monkeypatch.setattr("emma.infrahub.st", mock_st)
        node = make_node(hfid=["rtp1"])
        node.get_human_friendly_id_as_string.side_effect = RuntimeError("boom")
        batch = make_batch([(node, "ok")])

        assert asyncio.run(execute_batch.__wrapped__(batch=batch)) == 1

    def test_reports_node_id_when_no_hfid(self, monkeypatch):
        """Test that a node without an HFID is reported by id."""
        mock_st = MagicMock()
        monkeypatch.setattr("emma.infrahub.st", mock_st)
        batch = make_batch([(make_node(hfid=None, node_id="xyz789"), "ok")])

        assert asyncio.run(execute_batch.__wrapped__(batch=batch)) == 0
        assert "xyz789" in mock_st.success.call_args[0][0]


class TestDescribeRelatedNode:
    """Test describe_related_node function."""

    def test_prefers_human_friendly_id(self):
        """Test that a node with an HFID is described by it."""
        node = make_node(hfid=["rtp1"])

        assert describe_related_node(related_node=node, fallback_id="id-1") == "rtp1"

    def test_falls_back_to_node_id(self):
        """Test that a node without an HFID is described by its own id."""
        node = make_node(hfid=None, node_id="node-9")

        assert describe_related_node(related_node=node, fallback_id="id-1") == "node-9"

    def test_falls_back_to_given_id_when_node_missing(self):
        """Test that a missing node falls back to the id we already had.

        The store lookup is best-effort, so this used to dereference None.
        """
        assert describe_related_node(related_node=None, fallback_id="id-1") == "id-1"

    def test_returns_none_when_nothing_is_known(self):
        """Test that no node and no id yields None rather than raising."""
        assert describe_related_node(related_node=None, fallback_id=None) is None


class TestGetNodeFromStore:
    """Test get_node_from_store function."""

    def test_returns_stored_node(self):
        """Test that a hit in the store is returned."""
        stored = MagicMock(spec=InfrahubNode)
        obj = MagicMock()
        obj._client.store.get.return_value = stored

        assert get_node_from_store(obj=obj, peer_id="abc") is stored
        obj._client.store.get.assert_called_once_with(key="abc", raise_when_missing=False)

    def test_returns_none_without_a_peer_id(self):
        """Test that no lookup is attempted when the peer has no id."""
        obj = MagicMock()

        assert get_node_from_store(obj=obj, peer_id=None) is None
        obj._client.store.get.assert_not_called()

    def test_returns_none_on_miss(self):
        """Test that a miss in the store yields None."""
        obj = MagicMock()
        obj._client.store.get.return_value = None

        assert get_node_from_store(obj=obj, peer_id="abc") is None
