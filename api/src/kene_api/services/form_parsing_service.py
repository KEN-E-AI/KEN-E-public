"""Service for parsing multipart form data into validated models."""

import json
import logging

from ..models.kene_models import AccountRequest

logger = logging.getLogger(__name__)


def parse_json_field(field_value: str | None, field_name: str) -> list[str] | None:
    """
    Parse a JSON string field into a list.

    Args:
        field_value: The JSON string to parse
        field_name: Name of the field for error messages

    Returns:
        Parsed list or None if field_value is None/empty

    Raises:
        ValueError: If JSON parsing fails
    """
    if not field_value:
        return None

    try:
        parsed = json.loads(field_value)
        if not isinstance(parsed, list):
            raise ValueError(f"{field_name} must be a JSON array")
        return parsed
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse {field_name}: {e}")
        raise ValueError(f"Invalid JSON in {field_name}: {e!s}") from e


def parse_account_form_data(
    account_name: str,
    organization_id: str,
    industry: str,
    status: str,
    websites: str,
    timezone: str,
    account_id: str | None = None,
    data_region: str | None = None,
    region: str | None = None,
    marketing_channels: str | None = None,
    product_integrations: str | None = None,
    estimated_annual_ad_budget: int | None = None,
    enabled_strategies: str | None = None,
    override_product_categories: str | None = None,
    dry_run: bool = False,
) -> AccountRequest:
    """
    Parse multipart form data into AccountRequest model.

    This function handles the conversion of form fields (which are all strings)
    into the appropriate types expected by the AccountRequest model.

    Args:
        account_name: Name of the account
        organization_id: ID of the organization
        industry: Industry category
        status: Account status
        websites: JSON string array of websites
        timezone: Timezone for the account
        account_id: Optional pre-generated account ID
        data_region: Optional data region
        region: Optional JSON string array of regions
        marketing_channels: Optional JSON string array of marketing channels
        product_integrations: Optional JSON string array of product integrations
        estimated_annual_ad_budget: Optional annual budget
        enabled_strategies: Optional JSON string array of strategy types to generate
        override_product_categories: Optional JSON string array of product categories

    Returns:
        AccountRequest: Validated account data model

    Raises:
        ValueError: If any JSON parsing fails
    """
    # Parse JSON fields with proper error handling
    websites_list = parse_json_field(websites, "websites")
    if websites_list is None:
        websites_list = []  # Websites is required, default to empty list

    region_list = parse_json_field(region, "region")
    marketing_channels_list = (
        parse_json_field(marketing_channels, "marketing_channels") or []
    )
    product_integrations_list = (
        parse_json_field(product_integrations, "product_integrations") or []
    )
    enabled_strategies_list = parse_json_field(enabled_strategies, "enabled_strategies")
    override_product_categories_list = parse_json_field(
        override_product_categories, "override_product_categories"
    )

    # Create and return the validated model
    return AccountRequest(
        account_id=account_id,
        account_name=account_name,
        organization_id=organization_id,
        industry=industry,
        status=status,
        websites=websites_list,
        timezone=timezone,
        data_region=data_region,
        region=region_list,
        marketing_channels=marketing_channels_list,
        product_integrations=product_integrations_list,
        estimated_annual_ad_budget=estimated_annual_ad_budget,
        enabled_strategies=enabled_strategies_list,
        override_product_categories=override_product_categories_list,
        dry_run=dry_run,
    )
