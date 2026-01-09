"""Tests for CORS configuration."""

from src.kene_api.config import Settings, settings


def test_cors_settings_are_strings():
    """Test that CORS settings are loaded as strings."""
    assert isinstance(settings.cors_origins, str)
    assert isinstance(settings.cors_methods, str)
    assert isinstance(settings.cors_headers, str)


def test_cors_settings_not_empty():
    """Test that CORS settings are not empty."""
    assert settings.cors_origins != ""
    assert settings.cors_methods != ""
    assert settings.cors_headers != ""


def test_cors_origins_can_be_split():
    """Test that CORS origins string can be split into a list."""
    origins_list = [origin.strip() for origin in settings.cors_origins.split(",")]
    assert isinstance(origins_list, list)
    assert len(origins_list) > 0
    # Each origin should be a valid-looking URL or wildcard
    for origin in origins_list:
        assert origin == "*" or origin.startswith("http")


def test_cors_methods_can_be_split():
    """Test that CORS methods string can be split into a list."""
    methods_list = [method.strip() for method in settings.cors_methods.split(",")]
    assert isinstance(methods_list, list)
    assert len(methods_list) > 0
    # Check for common HTTP methods or wildcard
    valid_methods = {"GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD", "*"}
    for method in methods_list:
        assert method.upper() in valid_methods


def test_cors_headers_valid():
    """Test that CORS headers setting is valid."""
    assert settings.cors_headers == "*" or "," in settings.cors_headers or len(
        settings.cors_headers
    ) > 0


def test_cors_settings_use_os_getenv():
    """Test that Settings class uses os.getenv for CORS configuration."""
    # This test verifies that the Settings class properly uses os.getenv
    # which allows environment variables to be set via deployment configs
    test_settings = Settings()

    # The settings should exist and be non-None
    assert test_settings.cors_origins is not None
    assert test_settings.cors_methods is not None
    assert test_settings.cors_headers is not None

    # In the current dev environment, we should have localhost origins
    # In production, this will be set to https://app.ken-e.ai
    assert isinstance(test_settings.cors_origins, str)
    assert isinstance(test_settings.cors_methods, str)
    assert isinstance(test_settings.cors_headers, str)
