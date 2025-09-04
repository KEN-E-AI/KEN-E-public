"""OAuth models for secure state management."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class OAuthErrorCode(str, Enum):
    """Standardized OAuth error codes."""

    AUTHORIZATION_DENIED = "authorization_denied"
    TOKEN_EXCHANGE_FAILED = "token_exchange_failed"
    STATE_INVALID = "state_invalid"
    STATE_EXPIRED = "state_expired"
    CONFIGURATION_ERROR = "configuration_error"
    REFRESH_FAILED = "refresh_failed"
    UNKNOWN_ERROR = "unknown_error"


class OAuthState(BaseModel):
    """Model for OAuth state data stored in database."""

    state_token: str = Field(..., description="Unique state token")
    user_id: str = Field(..., description="User ID initiating the OAuth flow")
    account_id: str = Field(..., description="Account ID for the integration")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    expires_at: datetime = Field(..., description="Expiration timestamp")
    integration_type: str = Field(..., description="Type of integration (e.g., google_analytics)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

