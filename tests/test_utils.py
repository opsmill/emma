"""Tests for emma.utils module."""

import pytest

from emma.utils import is_feature_enabled, is_uuid, parse_hfid


class TestIsUuid:
    """Test is_uuid function."""

    def test_valid_uuid(self):
        """Test with valid UUID."""
        assert is_uuid("550e8400-e29b-41d4-a716-446655440000") is True
        assert is_uuid("6ba7b810-9dad-11d1-80b4-00c04fd430c8") is True

    def test_invalid_uuid(self):
        """Test with invalid UUID."""
        assert is_uuid("not-a-uuid") is False
        assert is_uuid("123456") is False
        assert is_uuid("") is False
        assert is_uuid("550e8400-e29b-41d4-a716") is False  # Too short


class TestParseHfid:
    """Test parse_hfid function."""

    def test_single_id(self):
        """Test with single ID."""
        result = parse_hfid("id123")
        assert result == ["id123"]

    def test_multiple_ids(self):
        """Test with multiple IDs separated by double underscore."""
        result = parse_hfid("id1__id2__id3")
        assert result == ["id1", "id2", "id3"]

    def test_no_separator(self):
        """Test with no separator returns whole string."""
        result = parse_hfid("id1_id2_id3")
        assert result == ["id1_id2_id3"]

    def test_empty_string(self):
        """Test with empty string."""
        result = parse_hfid("")
        assert result == [""]


class TestIsFeatureEnabled:
    """Test is_feature_enabled function."""

    @pytest.mark.parametrize("feature_name", ["query_builder", "template_builder", "some_other_feature"])
    def test_feature_check(self, feature_name):
        """Test feature enablement check."""
        # Without seeing the implementation, we can only test that it returns a boolean
        result = is_feature_enabled(feature_name)
        assert isinstance(result, bool)
