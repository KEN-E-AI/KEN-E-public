"""Comprehensive tests for shared.secrets module.

Tests cover:
- Raw value handling
- sm:// format secret resolution
- Full GCP path format secret resolution
- Error handling and edge cases
- Cache behavior
- Integration scenarios
"""

import json
import os
from unittest.mock import Mock, patch

from ..secrets import (
    _fetch_secret_from_full_path,
    _fetch_secret_from_sm_path,
    get_env_or_secret,
)


class TestGetEnvOrSecret:
    """Test cases for get_env_or_secret function with all three supported formats."""

    def test_raw_value(self):
        """Test with raw/plain environment variable value."""
        env_var = "TEST_VAR"
        raw_value = "my_raw_password"

        with patch.dict(os.environ, {env_var: raw_value}, clear=True):
            result = get_env_or_secret(env_var)
            assert result == raw_value

    def test_numeric_raw_value(self):
        """Test with numeric raw value (should be returned as string)."""
        env_var = "PORT"
        with patch.dict(os.environ, {env_var: "8000"}, clear=True):
            result = get_env_or_secret(env_var)
            assert result == "8000"

    def test_boolean_raw_value(self):
        """Test with boolean-like raw value."""
        env_var = "DEBUG"
        with patch.dict(os.environ, {env_var: "true"}, clear=True):
            result = get_env_or_secret(env_var)
            assert result == "true"

    @patch("shared.secrets._fetch_secret_from_full_path")
    def test_sm_format_with_project_id(self, mock_fetch):
        """Test sm:// format with project ID included."""
        env_var = "TEST_SECRET"
        secret_value = "actual_secret_value"
        mock_fetch.return_value = secret_value

        with patch.dict(
            os.environ, {env_var: "sm://525657242938/NEO4J_PASSWORD"}, clear=True
        ):
            result = get_env_or_secret(env_var)

            assert result == secret_value
            mock_fetch.assert_called_once_with(
                "projects/525657242938/secrets/NEO4J_PASSWORD/versions/latest"
            )

    @patch("shared.secrets._fetch_secret_from_full_path")
    def test_sm_format_without_project_id(self, mock_fetch):
        """Test sm:// format using default project from GOOGLE_CLOUD_PROJECT."""
        env_var = "TEST_SECRET"
        secret_value = "actual_secret_value"
        mock_fetch.return_value = secret_value

        with patch.dict(
            os.environ,
            {env_var: "sm://wandb_api_key", "GOOGLE_CLOUD_PROJECT": "ken-e-staging"},
            clear=True,
        ):
            result = get_env_or_secret(env_var)

            assert result == secret_value
            mock_fetch.assert_called_once_with(
                "projects/ken-e-staging/secrets/wandb_api_key/versions/latest"
            )

    @patch("shared.secrets._fetch_secret_from_full_path")
    def test_full_gcp_path_format(self, mock_fetch):
        """Test with full GCP Secret Manager path."""
        env_var = "NEO4J_PASSWORD"
        secret_value = "actual_secret_value"
        secret_path = "projects/391472102753/secrets/neo4j-password/versions/latest"
        mock_fetch.return_value = secret_value

        with patch.dict(os.environ, {env_var: secret_path}, clear=True):
            result = get_env_or_secret(env_var)

            assert result == secret_value
            mock_fetch.assert_called_once_with(secret_path)

    @patch("shared.secrets._fetch_secret_from_full_path")
    def test_secret_fetch_failure_returns_default(self, mock_fetch):
        """Test returns default value when Secret Manager fetch fails."""
        env_var = "TEST_SECRET"
        default_value = "fallback_value"
        mock_fetch.side_effect = Exception("Secret access denied")

        with patch.dict(os.environ, {env_var: "sm://test-secret"}, clear=True):
            result = get_env_or_secret(env_var, default=default_value)

            assert result == default_value

    def test_missing_env_var_returns_default(self):
        """Test with missing environment variable."""
        env_var = "NONEXISTENT_VAR"
        default_value = "default_value"

        if env_var in os.environ:
            del os.environ[env_var]

        result = get_env_or_secret(env_var, default=default_value)
        assert result == default_value

    def test_empty_env_var_returns_none(self):
        """Test with empty environment variable returns the empty string."""
        env_var = "EMPTY_VAR"

        with patch.dict(os.environ, {env_var: ""}, clear=True):
            result = get_env_or_secret(env_var)
            assert result == ""

    def test_partial_secret_path_returned_as_raw(self):
        """Test with partial Secret Manager path returns as raw value."""
        env_var = "TEST_VAR"
        partial_path = "projects/123/secrets/"  # Missing versions part

        with patch.dict(os.environ, {env_var: partial_path}, clear=True):
            result = get_env_or_secret(env_var)
            assert result == partial_path

    @patch("shared.secrets._fetch_secret_from_full_path")
    def test_caching_same_sm_path(self, mock_fetch):
        """Test that secrets are cached to avoid redundant fetches."""
        mock_fetch.return_value = "cached_value"

        with patch.dict(
            os.environ,
            {"VAR1": "sm://test-secret", "VAR2": "sm://test-secret"},
            clear=True,
        ):
            # First call
            result1 = get_env_or_secret("VAR1")
            # Second call with same sm:// path should use cache
            result2 = get_env_or_secret("VAR2")

            assert result1 == "cached_value"
            assert result2 == "cached_value"
            # Should only fetch once due to caching
            assert mock_fetch.call_count == 1

    @patch("shared.secrets._fetch_secret_from_full_path")
    def test_caching_same_full_path(self, mock_fetch):
        """Test that full GCP paths are also cached."""
        mock_fetch.return_value = "cached_value"
        full_path = "projects/123/secrets/test/versions/latest"

        with patch.dict(os.environ, {"VAR1": full_path, "VAR2": full_path}, clear=True):
            result1 = get_env_or_secret("VAR1")
            result2 = get_env_or_secret("VAR2")

            assert result1 == "cached_value"
            assert result2 == "cached_value"
            assert mock_fetch.call_count == 1


class TestFetchSecretFromFullPath:
    """Test cases for _fetch_secret_from_full_path() function."""

    @patch("google.cloud.secretmanager.SecretManagerServiceClient")
    def test_fetch_success(self, mock_client_class):
        """Test successful secret fetch from full GCP path."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_response = Mock()
        mock_response.payload.data = b"test_secret_value"
        mock_client.access_secret_version.return_value = mock_response

        full_path = "projects/123/secrets/test-secret/versions/latest"

        # Clear cache to ensure fresh call
        _fetch_secret_from_full_path.cache_clear()

        result = _fetch_secret_from_full_path(full_path)

        assert result == "test_secret_value"
        mock_client.access_secret_version.assert_called_once_with(
            request={"name": full_path}
        )

    @patch("google.cloud.secretmanager.SecretManagerServiceClient")
    def test_api_call_parameters(self, mock_client_class):
        """Verify correct parameters are passed to Secret Manager API."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_response = Mock()
        mock_response.payload.data = b"secret"
        mock_client.access_secret_version.return_value = mock_response

        full_path = "projects/525657242938/secrets/my-secret/versions/latest"

        _fetch_secret_from_full_path.cache_clear()
        _fetch_secret_from_full_path(full_path)

        call_args = mock_client.access_secret_version.call_args
        assert call_args[1]["request"]["name"] == full_path

    @patch("google.cloud.secretmanager.SecretManagerServiceClient")
    def test_utf8_decode(self, mock_client_class):
        """Test UTF-8 decoding of secret payload."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_response = Mock()
        # Test with UTF-8 encoded bytes including special characters
        mock_response.payload.data = "Test™ Secret©".encode()
        mock_client.access_secret_version.return_value = mock_response

        _fetch_secret_from_full_path.cache_clear()
        result = _fetch_secret_from_full_path(
            "projects/123/secrets/test/versions/latest"
        )

        assert result == "Test™ Secret©"
        assert isinstance(result, str)


class TestErrorHandling:
    """Test cases for error handling scenarios."""

    @patch("shared.secrets._fetch_secret_from_full_path")
    def test_permission_denied_403(self, mock_fetch):
        """Test handling of permission denied errors."""
        from google.api_core import exceptions

        # Clear cache to ensure test doesn't hit cached value
        from ..secrets import _secret_cache

        _secret_cache.clear()

        mock_fetch.side_effect = exceptions.PermissionDenied("Permission denied")

        with patch.dict(os.environ, {"TEST_SECRET": "sm://test-secret"}, clear=True):
            result = get_env_or_secret("TEST_SECRET", default="fallback")
            assert result == "fallback"

    @patch("shared.secrets._fetch_secret_from_full_path")
    def test_secret_not_found_404(self, mock_fetch):
        """Test handling of secret not found errors."""
        from google.api_core import exceptions

        mock_fetch.side_effect = exceptions.NotFound("Secret not found")

        with patch.dict(
            os.environ,
            {"TEST_SECRET": "projects/123/secrets/missing/versions/latest"},
            clear=True,
        ):
            result = get_env_or_secret("TEST_SECRET", default="default_val")
            assert result == "default_val"

    @patch("shared.secrets._fetch_secret_from_full_path")
    def test_network_timeout(self, mock_fetch):
        """Test handling of network timeouts."""
        from google.api_core import exceptions

        mock_fetch.side_effect = exceptions.DeadlineExceeded("Timeout")

        with patch.dict(os.environ, {"TEST_SECRET": "sm://secret"}, clear=True):
            result = get_env_or_secret("TEST_SECRET", default="timeout_default")
            assert result == "timeout_default"

    def test_empty_secret_value(self):
        """Test handling of empty secret values from Secret Manager."""
        with patch("shared.secrets._fetch_secret_from_full_path") as mock_fetch:
            mock_fetch.return_value = ""

            with patch.dict(
                os.environ, {"TEST_SECRET": "sm://empty-secret"}, clear=True
            ):
                result = get_env_or_secret("TEST_SECRET")
                assert result == ""

    @patch("shared.secrets._fetch_secret_from_full_path")
    def test_api_error_generic_exception(self, mock_fetch):
        """Test handling of generic API exceptions."""
        mock_fetch.side_effect = Exception("API Error")

        with patch.dict(os.environ, {"TEST_SECRET": "sm://secret"}, clear=True):
            result = get_env_or_secret("TEST_SECRET", default="error_default")
            assert result == "error_default"


class TestSmPathParsing:
    """Test cases for sm:// path parsing logic."""

    @patch("shared.secrets._fetch_secret_from_full_path")
    def test_parse_with_project_id(self, mock_fetch):
        """Test parsing sm:// path with project_id/secret_name format."""
        mock_fetch.return_value = "secret_value"

        result = _fetch_secret_from_sm_path("525657242938/my-secret")

        assert result == "secret_value"
        mock_fetch.assert_called_once_with(
            "projects/525657242938/secrets/my-secret/versions/latest"
        )

    @patch("shared.secrets._fetch_secret_from_full_path")
    def test_parse_without_project_uses_env(self, mock_fetch):
        """Test sm:// parsing uses GOOGLE_CLOUD_PROJECT when no project in path."""
        mock_fetch.return_value = "secret_value"

        with patch.dict(
            os.environ, {"GOOGLE_CLOUD_PROJECT": "custom-project"}, clear=True
        ):
            result = _fetch_secret_from_sm_path("my-secret")

            assert result == "secret_value"
            mock_fetch.assert_called_once_with(
                "projects/custom-project/secrets/my-secret/versions/latest"
            )

    @patch("shared.secrets._fetch_secret_from_full_path")
    def test_parse_without_project_uses_default(self, mock_fetch):
        """Test sm:// parsing defaults to ken-e-dev when GOOGLE_CLOUD_PROJECT not set."""
        mock_fetch.return_value = "secret_value"

        with patch.dict(os.environ, {}, clear=True):
            result = _fetch_secret_from_sm_path("my-secret")

            assert result == "secret_value"
            mock_fetch.assert_called_once_with(
                "projects/ken-e-dev/secrets/my-secret/versions/latest"
            )

    @patch("shared.secrets._fetch_secret_from_full_path")
    def test_full_path_construction(self, mock_fetch):
        """Verify correct full path is constructed from sm:// format."""
        mock_fetch.return_value = "value"

        _fetch_secret_from_sm_path("391472102753/neo4j-password")

        expected_path = "projects/391472102753/secrets/neo4j-password/versions/latest"
        mock_fetch.assert_called_once_with(expected_path)


class TestEdgeCases:
    """Test cases for edge cases and malformed inputs."""

    @patch("shared.secrets._fetch_secret_from_full_path")
    def test_invalid_project_id_special_chars(self, mock_fetch):
        """Test handling of project IDs with special characters."""
        # GCP API will reject this, but our code should pass it through
        mock_fetch.side_effect = Exception("Invalid project ID")

        with patch.dict(
            os.environ, {"TEST": "sm://invalid@project/secret"}, clear=True
        ):
            result = get_env_or_secret("TEST", default="fallback")
            assert result == "fallback"

    @patch("shared.secrets._fetch_secret_from_full_path")
    def test_path_with_extra_slashes(self, mock_fetch):
        """Test paths with extra slashes are handled."""
        mock_fetch.side_effect = Exception("Malformed path")

        path = "projects//123//secrets//test//versions//latest"
        with patch.dict(os.environ, {"TEST": path}, clear=True):
            result = get_env_or_secret("TEST", default="fallback")
            assert result == "fallback"

    def test_none_environment_variable(self):
        """Test behavior when environment variable is None."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_env_or_secret("NONEXISTENT_VAR", default="default")
            assert result == "default"

    @patch("shared.secrets._fetch_secret_from_full_path")
    def test_very_large_secret_value(self, mock_fetch):
        """Test handling of large secret values (>10KB)."""
        large_secret = "x" * 15000  # 15KB
        mock_fetch.return_value = large_secret

        with patch.dict(os.environ, {"TEST": "sm://large-secret"}, clear=True):
            result = get_env_or_secret("TEST")
            assert result == large_secret
            assert len(result) == 15000

    def test_whitespace_in_value(self):
        """Test that whitespace in raw values is preserved."""
        with patch.dict(os.environ, {"TEST": "  value with spaces  "}, clear=True):
            result = get_env_or_secret("TEST")
            assert result == "  value with spaces  "


class TestIntegrationScenarios:
    """Integration tests for realistic use cases."""

    @patch("shared.secrets._fetch_secret_from_full_path")
    def test_service_account_json_multiline_key(self, mock_fetch):
        """Test service account JSON with multi-line private key."""
        sa_json = {
            "type": "service_account",
            "project_id": "test-project",
            "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIB...\n-----END PRIVATE KEY-----\n",
            "client_email": "test@test-project.iam.gserviceaccount.com",
        }
        mock_fetch.return_value = json.dumps(sa_json)

        with patch.dict(os.environ, {"CREDS": "sm://service-account"}, clear=True):
            result = get_env_or_secret("CREDS")
            parsed = json.loads(result)
            assert parsed["private_key"].count("\n") == 3

    @patch("shared.secrets._fetch_secret_from_full_path")
    def test_complex_nested_json(self, mock_fetch):
        """Test complex nested JSON structures."""
        complex_json = {
            "level1": {"level2": {"level3": ["item1", "item2", {"level4": "value"}]}}
        }
        mock_fetch.return_value = json.dumps(complex_json)

        with patch.dict(os.environ, {"TEST": "sm://complex"}, clear=True):
            result = get_env_or_secret("TEST")
            parsed = json.loads(result)
            assert parsed["level1"]["level2"]["level3"][2]["level4"] == "value"

    def test_multiple_formats_same_session(self):
        """Test using different secret formats in the same session."""
        with patch("shared.secrets._fetch_secret_from_full_path") as mock_fetch:
            mock_fetch.return_value = "fetched_value"

            with patch.dict(
                os.environ,
                {
                    "RAW": "raw_value",
                    "SM": "sm://secret1",
                    "FULL": "projects/123/secrets/secret2/versions/latest",
                },
                clear=True,
            ):
                raw = get_env_or_secret("RAW")
                sm = get_env_or_secret("SM")
                full = get_env_or_secret("FULL")

                assert raw == "raw_value"
                assert sm == "fetched_value"
                assert full == "fetched_value"
                assert mock_fetch.call_count == 2  # SM and FULL both fetch


class TestCacheBehavior:
    """Test cases for LRU cache behavior."""

    @patch("google.cloud.secretmanager.SecretManagerServiceClient")
    def test_lru_cache_maxsize(self, mock_client_class):
        """Test that cache respects maxsize=32 limit."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_response = Mock()
        mock_response.payload.data = b"value"
        mock_client.access_secret_version.return_value = mock_response

        _fetch_secret_from_full_path.cache_clear()

        # Fetch 33 different secrets (exceeds maxsize=32)
        for i in range(33):
            path = f"projects/123/secrets/secret-{i}/versions/latest"
            _fetch_secret_from_full_path(path)

        # Cache info should show cache is at or near limit
        cache_info = _fetch_secret_from_full_path.cache_info()
        assert cache_info.maxsize == 32
        assert cache_info.misses == 33  # All were cache misses
        assert cache_info.currsize <= 32  # LRU evicted oldest

    def test_cache_key_uniqueness(self):
        """Test that different formats don't cause cache key collisions."""
        with patch("shared.secrets._fetch_secret_from_full_path") as mock_fetch:
            mock_fetch.return_value = "value"

            # Clear module-level cache
            from ..secrets import _secret_cache

            _secret_cache.clear()

            with patch.dict(
                os.environ,
                {
                    "VAR1": "sm://secret1",
                    "VAR2": "projects/123/secrets/secret2/versions/latest",
                },
                clear=True,
            ):
                get_env_or_secret("VAR1")
                get_env_or_secret("VAR2")

                # Both should be cached separately
                assert len(_secret_cache) == 2
                assert "secret1" in _secret_cache
                assert "projects/123/secrets/secret2/versions/latest" in _secret_cache

    def test_cache_persistence(self):
        """Test that cache persists across multiple function calls."""
        with patch("shared.secrets._fetch_secret_from_full_path") as mock_fetch:
            mock_fetch.return_value = "cached"

            # Clear cache
            from ..secrets import _secret_cache

            _secret_cache.clear()

            with patch.dict(os.environ, {"TEST": "sm://secret"}, clear=True):
                # First call
                result1 = get_env_or_secret("TEST")
                assert mock_fetch.call_count == 1

                # Second call - should use cache
                result2 = get_env_or_secret("TEST")
                assert mock_fetch.call_count == 1  # Still 1, used cache
                assert result1 == result2 == "cached"
