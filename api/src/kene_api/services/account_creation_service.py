"""
Service functions for account creation operations.
Following BP-C4: Extracted for testability and reusability.
"""

import logging
from typing import Any

from fastapi import UploadFile

from ..services.storage_service import StorageService

logger = logging.getLogger(__name__)


async def upload_strategy_documents(
    files: list[UploadFile] | None,
    account_id: str,
    data_region: str,
    storage_service: StorageService,
) -> list[str]:
    """
    Upload strategy documents to GCS and return their URLs.

    Extracted from the account creation endpoint for better testability (T-4).
    This function can be easily unit tested with a mocked StorageService.

    Args:
        files: List of files to upload (can be None or empty)
        account_id: Account ID for organizing uploads
        data_region: Data region for bucket selection
        storage_service: Injected storage service for testability

    Returns:
        List of successfully uploaded document URLs (empty if no uploads or all failed)

    Examples:
        >>> urls = await upload_strategy_documents(
        ...     files=[file1, file2],
        ...     account_id="acc_123",
        ...     data_region="US",
        ...     storage_service=mock_storage
        ... )
        >>> assert len(urls) <= len(files)  # Some uploads may fail
    """
    if not files:
        logger.info(f"No files to upload for account {account_id}")
        return []

    try:
        logger.info(
            f"Uploading {len(files)} business strategy documents for account {account_id}"
        )

        # Use storage service to upload files
        uploaded_files = await storage_service.upload_business_documents(
            account_id, data_region, files
        )

        # Extract successful upload URLs
        uploaded_urls = [
            f["gcs_url"]
            for f in uploaded_files
            if "gcs_url" in f and not f.get("error")
        ]

        logger.info(
            f"Successfully uploaded {len(uploaded_urls)}/{len(files)} documents "
            f"for account {account_id}"
        )

        # Log each URL for debugging
        for url in uploaded_urls:
            logger.debug(f"Uploaded document URL: {url}")

        return uploaded_urls

    except Exception as e:
        logger.error(
            f"Failed to upload documents for account {account_id}: {e}", exc_info=True
        )
        return []


def prepare_strategy_generation_params(
    account_id: str,
    account_name: str,
    websites: list[str],
    industry: str,
    region: list[str] | None,
    user_id: str,
    estimated_annual_ad_budget: int | None,
    uploaded_document_urls: list[str] | None = None,
) -> dict[str, Any]:
    """
    Prepare parameters for strategy generation task.

    Pure function for preparing strategy generation parameters.
    Extracted for testability and clarity.

    Args:
        account_id: Account identifier
        account_name: Company name
        websites: List of company websites
        industry: Industry category
        region: Customer regions
        user_id: User who created the account
        estimated_annual_ad_budget: Annual ad budget
        uploaded_document_urls: Optional URLs of uploaded documents

    Returns:
        Dictionary of parameters ready for strategy generation

    Examples:
        >>> params = prepare_strategy_generation_params(
        ...     account_id="acc_123",
        ...     account_name="Test Corp",
        ...     websites=["https://test.com"],
        ...     industry="Technology",
        ...     region=["US", "EU"],
        ...     user_id="user_456",
        ...     estimated_annual_ad_budget=100000
        ... )
        >>> assert params["customer_regions"] == ["US", "EU"]
    """
    return {
        "account_id": account_id,
        "company_name": account_name,
        "websites": websites,
        "industry": industry,
        "customer_regions": region or [],
        "user_id": user_id,
        "annual_ad_budget": estimated_annual_ad_budget,
        "uploaded_document_urls": uploaded_document_urls or [],
        "user_context": None,  # Background tasks don't have user context
    }
