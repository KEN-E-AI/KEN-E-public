"""Middleware components for the KEN-E API.

This module provides:
- AuthHeaderMiddleware: OAuth header extraction and validation
"""

from .auth_header import (
    AuthHeaderMiddleware,
    OAuthCredentials,
    get_auth_middleware,
    get_oauth_credentials,
)

__all__ = [
    "AuthHeaderMiddleware",
    "OAuthCredentials",
    "get_auth_middleware",
    "get_oauth_credentials",
]
