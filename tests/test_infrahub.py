"""Tests for get_version_async and run_gql_query in emma.infrahub."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from infrahub_sdk.exceptions import GraphQLError

from emma.infrahub import get_version_async, run_gql_query


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
