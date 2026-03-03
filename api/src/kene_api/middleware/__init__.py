"""Middleware components for the KEN-E API.

This module provides:
- AuthHeaderMiddleware: OAuth header extraction and validation
- RequestIdMiddleware: Correlation ID generation per request
"""

from .auth_header import (
    AuthHeaderMiddleware,
    OAuthCredentials,
    get_auth_middleware,
    get_oauth_credentials,
)
from .request_id import RequestIdMiddleware, get_request_id

__all__ = [
    "AuthHeaderMiddleware",
    "OAuthCredentials",
    "RequestIdMiddleware",
    "get_auth_middleware",
    "get_oauth_credentials",
    "get_request_id",
]
