#!/usr/bin/env python3
"""
Migrate Google Analytics agent configuration to Firestore.

This script creates the `google_analytics_agent` configuration document in Firestore,
enabling model selection and runtime configuration updates for the GA agent.

Usage:
    python migrate_ga_agent_to_firestore.py [--project-id PROJECT_ID] [--dry-run]

Examples:
    # Development environment
    python migrate_ga_agent_to_firestore.py --project-id ken-e-dev

    # Staging environment
    python migrate_ga_agent_to_firestore.py --project-id ken-e-staging

    # Production environment
    python migrate_ga_agent_to_firestore.py --project-id ken-e-prod

    # Dry run (no actual changes)
    python migrate_ga_agent_to_firestore.py --project-id ken-e-dev --dry-run
"""

import argparse
import logging
from datetime import datetime, timezone

from google.cloud import firestore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


GA_AGENT_CONFIG = {
    "name": "google_analytics_agent",
    "model": "gemini-2.0-flash",
    "description": "Google Analytics assistant for website and app data analysis",
    "instruction": """You are a Google Analytics assistant that helps users analyze their website and app data.

**Your Capabilities:**
1. List Google Analytics accounts and properties
2. Get detailed property information
3. Run custom analytics reports with dimensions, metrics, and filters
4. Access real-time user data (last 30 minutes)

**Authentication:**
OAuth credentials are handled automatically via headers. You do NOT need to pass tenant_id or tenant_credentials parameters - they are injected automatically.

**Available Tools (discovered dynamically from GA MCP server):**
- get_account_summaries_mt - List all GA accounts and properties
- run_report_mt - Run analytics reports with date ranges, metrics, dimensions, and filters
- run_realtime_report_mt - Get live data from last 30 minutes
- get_property_details_mt - Get GA4 property configuration details

**Tool Usage:**

1. **get_account_summaries_mt** - List all GA accounts
   - No required parameters (credentials are automatic)
   - Use when: User asks to see their GA accounts or properties

2. **get_property_details_mt** - Get property configuration
   - Required: property_id
   - Use when: User asks about a specific property's settings

3. **run_report_mt** - Run analytics reports
   - Required: property_id, date_ranges
   - Optional: metrics, dimensions, filters, sorting, limit
   - Common metrics: activeUsers, sessions, screenPageViews, bounceRate
   - Common dimensions: country, city, deviceCategory, pagePath

4. **run_realtime_report_mt** - Get live data
   - Required: property_id
   - Optional: metrics, dimensions
   - Shows data from last 30 minutes

**Best Practices:**
- If the user's property ID is available in the conversation context, use it directly
- Suggest relevant metrics/dimensions based on the question
- Format data clearly in tables when possible
- Provide insights along with raw data
- For date ranges, use formats like "7daysAgo", "yesterday", "today"
- If no property_id is available, first call get_account_summaries_mt to list properties

**Important:**
- NEVER ask for credentials or tokens - they are handled automatically
- If a property_id is provided in the context, use it without asking again""",
    "generate_content_config": {
        "temperature": 0.7,
        "max_output_tokens": 4096,
    },
    "metadata": {
        "version": "v1.0",
        "variant_name": "baseline",
        "experiment_id": "baseline",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": "migration_script",
        "notes": "Initial GA agent configuration migrated from hardcoded google_analytics_agent_v4.py.",
    },
}


def upload_config_to_firestore(
    config: dict, doc_id: str, project_id: str, dry_run: bool = False
) -> bool:
    """Upload a configuration document to Firestore.

    Args:
        config: Configuration dictionary
        doc_id: Document ID in agent_configs collection
        project_id: GCP project ID
        dry_run: If True, only log what would be done without making changes

    Returns:
        True if successful, False otherwise
    """
    try:
        if dry_run:
            logger.info(f"[DRY RUN] Would upload config '{doc_id}' to Firestore:")
            logger.info(f"  Model: {config['model']}")
            logger.info(f"  Description: {config['description']}")
            logger.info(f"  Project: {project_id}")
            return True

        db = firestore.Client(project=project_id)

        doc_ref = db.collection("agent_configs").document(doc_id)
        doc = doc_ref.get()

        if doc.exists:
            logger.warning(
                f"Config '{doc_id}' already exists in Firestore. "
                f"Use --force to overwrite (not implemented for safety)."
            )
            return False

        doc_ref.set(config)
        logger.info(
            f"Successfully uploaded config '{doc_id}' to Firestore "
            f"(model: {config['model']})"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to upload config '{doc_id}': {e}")
        return False


def main():
    """Main script entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate Google Analytics agent configuration to Firestore"
    )
    parser.add_argument(
        "--project-id",
        type=str,
        default="ken-e-dev",
        help="GCP project ID (default: ken-e-dev)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - show what would be done without making changes",
    )

    args = parser.parse_args()

    logger.info("Starting Google Analytics agent config migration to Firestore")
    logger.info(f"Project: {args.project_id}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("-" * 60)

    success = upload_config_to_firestore(
        config=GA_AGENT_CONFIG,
        doc_id="google_analytics_agent",
        project_id=args.project_id,
        dry_run=args.dry_run,
    )

    logger.info("-" * 60)
    if success:
        logger.info("Migration completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Verify config in Firestore console")
        logger.info("2. Deploy updated GA agent code")
        logger.info("3. Test GA agent with new config loading")
        logger.info("4. Update model/instruction via Admin UI if needed")
    else:
        logger.error("Migration failed!")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
