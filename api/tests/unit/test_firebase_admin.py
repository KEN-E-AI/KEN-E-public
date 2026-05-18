"""Unit tests for Firebase Admin SDK integration."""

import os
from unittest import mock

import pytest
from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError

from src.kene_api.auth.firebase_admin import (
    get_firebase_auth,
    get_user,
    initialize_firebase_admin,
    verify_id_token,
)


class TestInitializeFirebaseAdmin:
    """Test Firebase Admin SDK initialization."""

    @pytest.mark.skip(reason="Firebase initialization behavior changed — needs rewrite against current firebase_admin.py — see DM-85")
    def test_initialize_with_application_default_credentials(self):
        """Test initialization with Application Default Credentials."""
        with mock.patch.dict(
            os.environ, {"USE_APPLICATION_DEFAULT_CREDENTIALS": "true"}
        ):
            with mock.patch("firebase_admin.initialize_app") as mock_init:
                with mock.patch("google.auth.default") as mock_default:
                    mock_default.return_value = (mock.Mock(), "test-project")

                    app = initialize_firebase_admin()

                    mock_init.assert_called_once()
                    assert app == mock_init.return_value

    @pytest.mark.skip(reason="Firebase initialization behavior changed — needs rewrite against current firebase_admin.py — see DM-85")
    def test_initialize_with_service_account_file(self):
        """Test initialization with service account key file."""
        with mock.patch.dict(
            os.environ,
            {
                "USE_APPLICATION_DEFAULT_CREDENTIALS": "false",
                "GOOGLE_APPLICATION_CREDENTIALS": "path/to/key.json",
            },
        ):
            with mock.patch("firebase_admin.initialize_app") as mock_init:
                with mock.patch("firebase_admin.credentials.Certificate") as mock_cert:
                    mock_cert.return_value = mock.Mock()

                    app = initialize_firebase_admin()

                    mock_cert.assert_called_once_with("path/to/key.json")
                    mock_init.assert_called_once_with(mock_cert.return_value)
                    assert app == mock_init.return_value

    @pytest.mark.skip(reason="Firebase initialization behavior changed — needs rewrite against current firebase_admin.py — see DM-85")
    def test_initialize_returns_existing_app(self):
        """Test that existing app is returned if already initialized."""
        existing_app = mock.Mock()
        with mock.patch("firebase_admin.get_app", return_value=existing_app):
            app = initialize_firebase_admin()
            assert app == existing_app

    @pytest.mark.skip(reason="Firebase initialization behavior changed — needs rewrite against current firebase_admin.py — see DM-85")
    def test_initialize_handles_errors(self):
        """Test that initialization errors are propagated."""
        with mock.patch("firebase_admin.get_app", side_effect=ValueError):
            with mock.patch(
                "firebase_admin.initialize_app", side_effect=Exception("Init failed")
            ):
                with pytest.raises(Exception) as exc_info:
                    initialize_firebase_admin()
                assert str(exc_info.value) == "Init failed"


class TestGetFirebaseAuth:
    """Test getting Firebase Auth instance."""

    def test_get_firebase_auth_returns_auth_module(self):
        """Test that get_firebase_auth returns the auth module."""
        with mock.patch("src.kene_api.auth.firebase_admin.initialize_firebase_admin"):
            result = get_firebase_auth()
            assert result == auth


class TestVerifyIdToken:
    """Test Firebase ID token verification."""

    def test_verify_valid_token(self):
        """Test successful token verification."""
        mock_decoded = {
            "uid": "test-uid",
            "email": "test@example.com",
            "email_verified": True,
        }

        with mock.patch(
            "firebase_admin.auth.verify_id_token", return_value=mock_decoded
        ):
            result = verify_id_token("valid-token")
            assert result == mock_decoded

    def test_verify_invalid_token(self):
        """Test that invalid tokens raise ValueError."""
        with mock.patch(
            "firebase_admin.auth.verify_id_token",
            side_effect=auth.InvalidIdTokenError("Invalid token"),
        ):
            with pytest.raises(ValueError) as exc_info:
                verify_id_token("invalid-token")
            assert "Invalid token" in str(exc_info.value)

    def test_verify_expired_token(self):
        """Test that expired tokens raise ValueError."""
        with mock.patch(
            "firebase_admin.auth.verify_id_token",
            side_effect=auth.ExpiredIdTokenError("Token expired", "cause"),
        ):
            with pytest.raises(ValueError) as exc_info:
                verify_id_token("expired-token")
            assert "Token expired" in str(exc_info.value)

    def test_verify_token_general_error(self):
        """Test that general Firebase errors are handled."""
        with mock.patch(
            "firebase_admin.auth.verify_id_token",
            side_effect=FirebaseError(code="unknown", message="Firebase error"),
        ):
            with pytest.raises(ValueError) as exc_info:
                verify_id_token("bad-token")
            assert "Firebase error" in str(exc_info.value)


class TestGetUser:
    """Test getting user by UID."""

    def test_get_user_success(self):
        """Test successful user retrieval."""
        mock_user = mock.Mock(spec=auth.UserRecord)
        mock_user.uid = "test-uid"
        mock_user.email = "test@example.com"

        with mock.patch("firebase_admin.auth.get_user", return_value=mock_user):
            result = get_user("test-uid")
            assert result == mock_user
            assert result.uid == "test-uid"
            assert result.email == "test@example.com"

    def test_get_user_not_found(self):
        """Test that user not found raises ValueError."""
        with mock.patch(
            "firebase_admin.auth.get_user",
            side_effect=auth.UserNotFoundError("User not found"),
        ):
            with pytest.raises(ValueError) as exc_info:
                get_user("nonexistent-uid")
            assert "User not found" in str(exc_info.value)

    def test_get_user_general_error(self):
        """Test that general errors are handled."""
        with mock.patch(
            "firebase_admin.auth.get_user", side_effect=Exception("Unexpected error")
        ):
            with pytest.raises(ValueError) as exc_info:
                get_user("test-uid")
            assert "Unexpected error" in str(exc_info.value)
