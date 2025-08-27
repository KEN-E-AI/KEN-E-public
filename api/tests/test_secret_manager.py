"""Unit tests for Secret Manager utilities."""

import json
import os
from unittest.mock import Mock, patch

import pytest
from google.cloud import secretmanager

from src.kene_api.secret_manager import (
    get_env_var_or_secret,
    get_env_var_or_secret_json,
    get_secret,
    get_secret_json,
)


class TestGetSecret:
    """Test cases for get_secret function."""

    @patch('src.kene_api.secret_manager.secretmanager.SecretManagerServiceClient')
    def test_get_secret_success(self, mock_client_class):
        """Test successful secret retrieval."""
        # Arrange
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_response = Mock()
        mock_response.payload.data = b"test_secret_value"
        mock_client.access_secret_version.return_value = mock_response
        
        secret_path = "projects/123/secrets/test-secret/versions/latest"
        
        # Act
        result = get_secret(secret_path)
        
        # Assert
        assert result == "test_secret_value"
        # Check that access_secret_version was called with the correct request
        # Note: We now also pass timeout and retry parameters
        mock_client.access_secret_version.assert_called_once()
        call_args = mock_client.access_secret_version.call_args
        assert call_args.kwargs['request'] == {"name": secret_path}
        assert call_args.kwargs['timeout'] == 10.0
        assert 'retry' in call_args.kwargs

    @patch('src.kene_api.secret_manager.secretmanager.SecretManagerServiceClient')
    def test_get_secret_failure(self, mock_client_class):
        """Test secret retrieval failure."""
        # Arrange
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.access_secret_version.side_effect = Exception("Access denied")
        
        secret_path = "projects/123/secrets/test-secret/versions/latest"
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            get_secret(secret_path)
        
        assert "Failed to retrieve secret from" in str(exc_info.value)
        assert secret_path in str(exc_info.value)

    @patch('src.kene_api.secret_manager.secretmanager.SecretManagerServiceClient')
    def test_get_secret_empty_response(self, mock_client_class):
        """Test secret retrieval with empty response."""
        # Arrange
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_response = Mock()
        mock_response.payload.data = b""
        mock_client.access_secret_version.return_value = mock_response
        
        secret_path = "projects/123/secrets/test-secret/versions/latest"
        
        # Act
        result = get_secret(secret_path)
        
        # Assert
        assert result == ""


class TestGetSecretJson:
    """Test cases for get_secret_json function."""

    @patch('src.kene_api.secret_manager.get_secret')
    def test_get_secret_json_success(self, mock_get_secret):
        """Test successful JSON secret retrieval."""
        # Arrange
        test_data = {"key": "value", "number": 42}
        mock_get_secret.return_value = json.dumps(test_data)
        
        secret_path = "projects/123/secrets/json-secret/versions/latest"
        
        # Act
        result = get_secret_json(secret_path)
        
        # Assert
        assert result == test_data
        mock_get_secret.assert_called_once_with(secret_path)

    @patch('src.kene_api.secret_manager.get_secret')
    def test_get_secret_json_invalid_json(self, mock_get_secret):
        """Test JSON secret retrieval with invalid JSON."""
        # Arrange
        mock_get_secret.return_value = "not valid json"
        
        secret_path = "projects/123/secrets/json-secret/versions/latest"
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            get_secret_json(secret_path)
        
        assert "Failed to parse JSON from secret" in str(exc_info.value)

    @patch('src.kene_api.secret_manager.get_secret')
    def test_get_secret_json_get_secret_failure(self, mock_get_secret):
        """Test JSON secret retrieval when get_secret fails."""
        # Arrange
        mock_get_secret.side_effect = Exception("Secret access failed")
        
        secret_path = "projects/123/secrets/json-secret/versions/latest"
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            get_secret_json(secret_path)
        
        assert "Failed to retrieve JSON secret from" in str(exc_info.value)


class TestGetEnvVarOrSecret:
    """Test cases for get_env_var_or_secret function."""

    def test_get_env_var_or_secret_with_regular_value(self):
        """Test with regular environment variable value."""
        # Arrange
        env_var = "TEST_VAR"
        regular_value = "regular_value"
        
        with patch.dict(os.environ, {env_var: regular_value}):
            # Act
            result = get_env_var_or_secret(env_var)
            
            # Assert
            assert result == regular_value

    @patch('src.kene_api.secret_manager.get_secret')
    def test_get_env_var_or_secret_with_secret_path(self, mock_get_secret):
        """Test with Secret Manager path in environment variable."""
        # Arrange
        env_var = "TEST_SECRET_VAR"
        secret_path = "projects/123/secrets/test-secret/versions/latest"
        secret_value = "actual_secret_value"
        mock_get_secret.return_value = secret_value
        
        with patch.dict(os.environ, {env_var: secret_path}):
            # Act
            result = get_env_var_or_secret(env_var)
            
            # Assert
            assert result == secret_value
            mock_get_secret.assert_called_once_with(secret_path)

    @patch('src.kene_api.secret_manager.get_secret')
    def test_get_env_var_or_secret_secret_failure_raises(self, mock_get_secret):
        """Test raises SecretManagerError when Secret Manager fails."""
        # Arrange
        from src.kene_api.exceptions import SecretManagerError
        
        env_var = "TEST_SECRET_VAR"
        secret_path = "projects/123/secrets/test-secret/versions/latest"
        mock_get_secret.side_effect = Exception("Secret access failed")
        
        with patch.dict(os.environ, {env_var: secret_path}):
            # Act & Assert
            with pytest.raises(SecretManagerError) as exc_info:
                get_env_var_or_secret(env_var)
            
            assert "Secret Manager access failed" in str(exc_info.value)
            assert exc_info.value.env_var == env_var
            assert exc_info.value.secret_path == secret_path
    
    @patch('src.kene_api.secret_manager.get_secret')
    def test_get_env_var_or_secret_with_allow_failure(self, mock_get_secret):
        """Test returns empty string when allow_failure=True and Secret Manager fails."""
        # Arrange
        env_var = "TEST_SECRET_VAR"
        secret_path = "projects/123/secrets/test-secret/versions/latest"
        mock_get_secret.side_effect = Exception("Secret access failed")
        
        with patch.dict(os.environ, {env_var: secret_path}):
            # Act
            result = get_env_var_or_secret(env_var, allow_failure=True)
            
            # Assert
            assert result == ""  # Returns empty string with allow_failure=True

    def test_get_env_var_or_secret_missing_env_var(self):
        """Test with missing environment variable."""
        # Arrange
        env_var = "NONEXISTENT_VAR"
        default_value = "default_value"
        
        # Ensure env var doesn't exist
        if env_var in os.environ:
            del os.environ[env_var]
        
        # Act
        result = get_env_var_or_secret(env_var, default_value)
        
        # Assert
        assert result == default_value

    def test_get_env_var_or_secret_empty_env_var(self):
        """Test with empty environment variable."""
        # Arrange
        env_var = "EMPTY_VAR"
        default_value = "default_value"
        
        with patch.dict(os.environ, {env_var: ""}):
            # Act
            result = get_env_var_or_secret(env_var, default_value)
            
            # Assert
            assert result == ""  # Empty string is returned, not default

    @patch('src.kene_api.secret_manager.get_secret')
    def test_get_env_var_or_secret_partial_secret_path(self, mock_get_secret):
        """Test with partial Secret Manager path (should not trigger secret resolution)."""
        # Arrange
        env_var = "TEST_VAR"
        partial_path = "projects/123/secrets/"  # Missing versions part
        
        with patch.dict(os.environ, {env_var: partial_path}):
            # Act
            result = get_env_var_or_secret(env_var)
            
            # Assert
            assert result == partial_path
            mock_get_secret.assert_not_called()


class TestGetEnvVarOrSecretJson:
    """Test cases for get_env_var_or_secret_json function."""

    @patch('src.kene_api.secret_manager.get_secret_json')
    def test_get_env_var_or_secret_json_with_secret_path(self, mock_get_secret_json):
        """Test JSON secret retrieval with Secret Manager path."""
        # Arrange
        env_var = "TEST_JSON_SECRET"
        secret_path = "projects/123/secrets/json-secret/versions/latest"
        secret_data = {"service_account": "data"}
        mock_get_secret_json.return_value = secret_data
        
        with patch.dict(os.environ, {env_var: secret_path}):
            # Act
            result = get_env_var_or_secret_json(env_var)
            
            # Assert
            assert result == secret_data
            mock_get_secret_json.assert_called_once_with(secret_path)

    def test_get_env_var_or_secret_json_missing_env_var(self):
        """Test with missing environment variable."""
        # Arrange
        env_var = "NONEXISTENT_JSON_VAR"
        
        # Ensure env var doesn't exist
        if env_var in os.environ:
            del os.environ[env_var]
        
        # Act
        result = get_env_var_or_secret_json(env_var)
        
        # Assert
        assert result is None

    def test_get_env_var_or_secret_json_regular_value(self):
        """Test with regular (non-secret) environment variable."""
        # Arrange
        env_var = "TEST_JSON_VAR"
        regular_value = "not_a_secret_path"
        
        with patch.dict(os.environ, {env_var: regular_value}):
            # Act
            result = get_env_var_or_secret_json(env_var)
            
            # Assert
            assert result is None

    @patch('src.kene_api.secret_manager.get_secret_json')
    def test_get_env_var_or_secret_json_secret_failure(self, mock_get_secret_json):
        """Test fallback when JSON secret retrieval fails."""
        # Arrange
        env_var = "TEST_JSON_SECRET"
        secret_path = "projects/123/secrets/json-secret/versions/latest"
        mock_get_secret_json.side_effect = Exception("JSON secret access failed")
        
        with patch.dict(os.environ, {env_var: secret_path}):
            # Act
            result = get_env_var_or_secret_json(env_var)
            
            # Assert
            assert result is None


class TestSecretManagerIntegration:
    """Integration test scenarios for Secret Manager utilities."""

    @patch('src.kene_api.secret_manager.secretmanager.SecretManagerServiceClient')
    def test_realistic_service_account_scenario(self, mock_client_class):
        """Test realistic service account JSON retrieval scenario."""
        # Arrange
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        service_account_data = {
            "type": "service_account",
            "project_id": "test-project",
            "private_key_id": "key123",
            "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvg...==\n-----END PRIVATE KEY-----\n",
            "client_email": "test@test-project.iam.gserviceaccount.com",
            "client_id": "123456789",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
        
        mock_response = Mock()
        mock_response.payload.data = json.dumps(service_account_data).encode('utf-8')
        mock_client.access_secret_version.return_value = mock_response
        
        env_var = "GOOGLE_APPLICATION_CREDENTIALS"
        secret_path = "projects/123/secrets/service-account-json/versions/latest"
        
        with patch.dict(os.environ, {env_var: secret_path}):
            # Act
            result = get_env_var_or_secret_json(env_var)
            
            # Assert
            assert result == service_account_data
            assert result["type"] == "service_account"
            assert result["project_id"] == "test-project"

    @patch('src.kene_api.secret_manager.secretmanager.SecretManagerServiceClient')
    def test_realistic_api_key_scenario(self, mock_client_class):
        """Test realistic API key retrieval scenario."""
        # Arrange
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        api_key = "AIzaSyDXBX12345678901234567890123456789"
        mock_response = Mock()
        mock_response.payload.data = api_key.encode('utf-8')
        mock_client.access_secret_version.return_value = mock_response
        
        env_vars = [
            "SENDGRID_API_KEY", 
            "RECAPTCHA_SECRET_KEY",
            "NEO4J_PASSWORD"
        ]
        
        for env_var in env_vars:
            secret_path = f"projects/123/secrets/{env_var.lower().replace('_', '-')}/versions/latest"
            
            with patch.dict(os.environ, {env_var: secret_path}):
                # Act - Use allow_failure=True for backward compatibility in tests
                result = get_env_var_or_secret(env_var, allow_failure=True)
                
                # Assert
                assert result == api_key
                assert len(result) > 20  # Reasonable API key length