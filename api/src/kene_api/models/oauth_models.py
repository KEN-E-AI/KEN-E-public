"""OAuth models for secure state management."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional

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


class GoogleAnalyticsProperty(BaseModel):
    """Model for a Google Analytics property."""
    
    property_id: str = Field(..., description="GA4 property ID (e.g., properties/123456)")
    display_name: str = Field(..., description="Human-readable property name")
    account_id: str = Field(..., description="Parent account ID (e.g., accounts/789012)")
    account_display_name: str = Field(..., description="Human-readable account name")
    time_zone: Optional[str] = Field(None, description="Property timezone")
    industry_category: Optional[str] = Field(None, description="Industry category")
    create_time: Optional[str] = Field(None, description="Property creation timestamp")


class GoogleAnalyticsPropertiesResponse(BaseModel):
    """Response model for listing GA properties."""
    
    properties: List[GoogleAnalyticsProperty] = Field(
        ..., description="List of available GA properties"
    )
    selected_property_ids: List[str] = Field(
        default_factory=list, 
        description="Currently selected property IDs for this account"
    )
    total_count: int = Field(..., description="Total number of properties")


class UpdateSelectedPropertiesRequest(BaseModel):
    """Request model for updating selected GA properties."""
    
    property_ids: List[str] = Field(
        ..., description="List of selected property IDs"
    )
    properties: List[GoogleAnalyticsProperty] = Field(
        ..., description="Full property objects for storing metadata"
    )

