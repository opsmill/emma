"""Tests for emma.streamlit_utils module.

Note: These tests are limited because Streamlit functions require a runtime context.
More comprehensive testing would require a Streamlit test runner.
"""


class TestStreamlitUtils:
    """Test streamlit_utils functions that don't require runtime context."""

    def test_module_imports(self):
        """Test that the module can be imported."""
        import emma.streamlit_utils

        assert hasattr(emma.streamlit_utils, "get_current_page")
        assert hasattr(emma.streamlit_utils, "set_page_config")
        assert hasattr(emma.streamlit_utils, "display_logo")
        assert hasattr(emma.streamlit_utils, "display_branch_selector")
        assert hasattr(emma.streamlit_utils, "ensure_infrahub_address_and_branch")

    def test_page_config_function(self):
        """Test that set_page_config is callable."""
        from emma.streamlit_utils import set_page_config

        # Just verify it's callable, actual execution requires Streamlit runtime
        assert callable(set_page_config)
