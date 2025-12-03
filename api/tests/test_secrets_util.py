"""Unit tests for Secret Manager utilities."""

import os
from unittest.mock import patch

from src.kene_api.utils.secrets import get_env_or_secret


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

    @patch("src.kene_api.utils.secrets._fetch_secret_from_full_path")
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

    @patch("src.kene_api.utils.secrets._fetch_secret_from_full_path")
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

    @patch("src.kene_api.utils.secrets._fetch_secret_from_full_path")
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

    @patch("src.kene_api.utils.secrets._fetch_secret_from_full_path")
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

    @patch("src.kene_api.utils.secrets._fetch_secret_from_full_path")
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

    @patch("src.kene_api.utils.secrets._fetch_secret_from_full_path")
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
