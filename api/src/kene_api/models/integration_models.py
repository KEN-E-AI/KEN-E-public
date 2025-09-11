"""Models for integration configurations and credentials."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IntegrationType(str, Enum):
    """Supported integration types."""

    GOOGLE_ANALYTICS = "google_analytics"
    META_ADS = "meta_ads"
    GOOGLE_ADS = "google_ads"
    LINKEDIN_ADS = "linkedin_ads"
    TIKTOK_ADS = "tiktok_ads"
    AMAZON_ADS = "amazon_ads"


class IntegrationStatus(str, Enum):
    """Integration configuration status."""

    NOT_CONFIGURED = "not_configured"
    CONFIGURED = "configured"
    ERROR = "error"
    EXPIRED = "expired"


class GoogleAnalyticsCredentials(BaseModel):
    """Google Analytics service account credentials."""

    type: str = Field(..., description="Service account type")
    project_id: str = Field(..., description="GCP project ID")
    private_key_id: str = Field(..., description="Private key ID")
    private_key: str = Field(..., description="Private key")
    client_email: str = Field(..., description="Service account email")
    client_id: str = Field(..., description="Client ID")
    auth_uri: str = Field(..., description="Auth URI")
    token_uri: str = Field(..., description="Token URI")
    auth_provider_x509_cert_url: str = Field(..., description="Auth provider cert URL")
    client_x509_cert_url: str = Field(..., description="Client cert URL")


class IntegrationCredentialsRequest(BaseModel):
    """Request model for storing integration credentials."""

    integration_type: IntegrationType = Field(..., description="Type of integration")
    credentials: dict[str, Any] = Field(
        ..., description="Integration credentials (will be encrypted)"
    )


class IntegrationCredentialsUpdate(BaseModel):
    """Request model for updating integration credentials."""

    credentials: dict[str, Any] = Field(
        ..., description="New integration credentials (will be encrypted)"
    )


class IntegrationTestRequest(BaseModel):
    """Request model for testing integration connection."""

    integration_type: IntegrationType = Field(..., description="Type of integration")
    credentials: dict[str, Any] | None = Field(
        None, description="Optional credentials to test (won't be stored)"
    )


class IntegrationTestResponse(BaseModel):
    """Response model for integration connection test."""

    success: bool = Field(..., description="Whether the test was successful")
    message: str = Field(..., description="Test result message")
    details: dict[str, Any] | None = Field(
        None, description="Additional test details"
    )


class IntegrationStatusResponse(BaseModel):
    """Response model for integration status check."""

    integration_type: IntegrationType = Field(..., description="Type of integration")
    status: IntegrationStatus = Field(..., description="Current status")
    configured_at: datetime | None = Field(
        None, description="When the integration was configured"
    )
    last_tested_at: datetime | None = Field(
        None, description="When the integration was last tested"
    )
    error_message: str | None = Field(None, description="Error message if any")
    user_email: str | None = Field(None, description="Email of connected user")
    property_count: int | None = Field(None, description="Number of Google Analytics properties selected")


class IntegrationConfig(BaseModel):
    """Model for integration configuration stored with account."""

    integration_type: IntegrationType = Field(..., description="Type of integration")
    status: IntegrationStatus = Field(..., description="Current status")
    configured_at: datetime | None = Field(
        None, description="When configured"
    )
    configured_by: str | None = Field(None, description="User who configured it")
