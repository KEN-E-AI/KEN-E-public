#!/usr/bin/env python3
"""
Migrate KEN-E chatbot configuration to Firestore.

This script creates the `ken_e_chatbot` configuration document in Firestore,
enabling model selection and runtime configuration updates for the chatbot agent.

Usage:
    python migrate_chatbot_to_firestore.py [--project-id PROJECT_ID] [--dry-run]

Examples:
    # Development environment
    python migrate_chatbot_to_firestore.py --project-id ken-e-dev

    # Staging environment
    python migrate_chatbot_to_firestore.py --project-id ken-e-staging

    # Production environment
    python migrate_chatbot_to_firestore.py --project-id ken-e-prod

    # Dry run (no actual changes)
    python migrate_chatbot_to_firestore.py --project-id ken-e-dev --dry-run
"""

import argparse
import logging
from datetime import datetime, timezone

from google.cloud import firestore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# KEN-E Chatbot configuration
KEN_E_CHATBOT_CONFIG = {
    "name": "ken_e_chatbot",
    "model": "gemini-2.0-flash",
    "description": "KEN-E chat agent for company news and Google Analytics queries",
    "instruction": """You are KEN-E, an intelligent AI assistant specializing in business intelligence and analytics.

**CRITICAL: When you call a tool, the tool's response contains the answer. You MUST present that response to the user. Never just acknowledge that you called the tool - always share what the tool returned.**

**CAPABILITY 1 - Company News & Business Intelligence:**
Use `search_company_news` for queries about:
- Company news, announcements, and press releases
- Financial results, earnings reports, quarterly results
- Market movements, stock information, analyst ratings
- Executive changes, corporate actions, M&A activity
- Product launches, business developments, strategy updates
- Any questions about specific companies (Apple, Google, Tesla, etc.)

**CAPABILITY 2 - Google Analytics & Website Data:**
Use `query_google_analytics` for queries about:
- Website or app traffic metrics (users, sessions, pageviews)
- User behavior, engagement metrics, conversion rates
- Traffic sources, acquisition channels, campaign performance
- Real-time analytics data and live user activity
- Custom reports with specific metrics and dimensions
- Any GA4 property data or analysis

**ROUTING INSTRUCTIONS:**
1. Analyze the user's intent using your LLM capabilities
2. Route based on the primary focus of the query:
   - Company/business/market focus → search_company_news
   - Website/traffic/analytics focus → query_google_analytics

3. When routing, ALWAYS pass the COMPLETE user input to the tool

4. Handle ambiguous queries:
   - If unclear, ask for clarification about which capability they need
   - If query could match multiple capabilities, ask which they'd like to explore first

5. Response handling:
   - ALWAYS relay the complete response from the specialized agent to the user
   - The tool response IS your response - present it in full
   - Maintain the formatting from the specialist agent

**IMPORTANT NOTES:**
- You are integrated with the KEN-E app where users are already authenticated
- NEVER ask users for credentials - they're already logged in with Google
- The system automatically uses the logged-in user's Google account for GA queries
- Strategy document generation is handled separately during account creation

**STRATEGY DOCUMENTS NOTE:**
If users ask about creating or generating strategy documents, explain:
"Strategy documents are automatically generated when you create a new account. They include business strategy, competitive analysis, customer journey, marketing strategy, and brand guidelines tailored to your company. These comprehensive documents are created once during account setup to provide a strong foundation for your marketing efforts."

**EXAMPLES OF ROUTING:**
- "What's the latest news about Apple?" → search_company_news
- "Show me website traffic for last week" → query_google_analytics
- "How many users visited my site?" → query_google_analytics
- "Tesla earnings report" → search_company_news
- "Bounce rate by country" → query_google_analytics
- "Microsoft acquisition news" → search_company_news

Remember: You are a router, not a data source. ALWAYS delegate to the appropriate specialized agent using the provided tools.""",
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
        "notes": "Initial chatbot configuration migrated from hardcoded ken_e_agent.py. Enables model selection and runtime updates via Admin UI.",
    },
}


def upload_config_to_firestore(
    config: dict, doc_id: str, project_id: str, dry_run: bool = False
) -> bool:
    """
    Upload a configuration document to Firestore.

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

        # Initialize Firestore client
        db = firestore.Client(project=project_id)

        # Check if config already exists
        doc_ref = db.collection("agent_configs").document(doc_id)
        doc = doc_ref.get()

        if doc.exists:
            logger.warning(
                f"Config '{doc_id}' already exists in Firestore. "
                f"Use --force to overwrite (not implemented for safety)."
            )
            return False

        # Upload config
        doc_ref.set(config)
        logger.info(
            f"✅ Successfully uploaded config '{doc_id}' to Firestore "
            f"(model: {config['model']})"
        )
        return True

    except Exception as e:
        logger.error(f"❌ Failed to upload config '{doc_id}': {e}")
        return False


def main():
    """Main script entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate KEN-E chatbot configuration to Firestore"
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

    logger.info("Starting KEN-E chatbot config migration to Firestore")
    logger.info(f"Project: {args.project_id}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("-" * 60)

    # Upload chatbot config
    success = upload_config_to_firestore(
        config=KEN_E_CHATBOT_CONFIG,
        doc_id="ken_e_chatbot",
        project_id=args.project_id,
        dry_run=args.dry_run,
    )

    logger.info("-" * 60)
    if success:
        logger.info("✅ Migration completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Verify config in Firestore console")
        logger.info("2. Deploy updated chatbot agent code")
        logger.info("3. Test chatbot with new model selection")
        logger.info("4. Update model via Admin UI if needed")
    else:
        logger.error("❌ Migration failed!")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
