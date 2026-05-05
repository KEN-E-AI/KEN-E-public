#!/usr/bin/env python3
"""
Upload baseline agent configurations to Firestore.

This script extracts the current hardcoded configurations from business_agents.py
and uploads them to Firestore as baseline configurations. Run this once to
initialize the Firestore agent_configs collection.

Usage:
    python upload_baseline_configs.py [--project-id PROJECT_ID] [--dry-run]
"""

import argparse
import logging
from datetime import datetime, timezone

from google.cloud import firestore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Baseline configurations extracted from business_agents.py
BUSINESS_RESEARCHER_CONFIG = {
    "name": "business_researcher",
    "model": "gemini-2.5-pro",
    "description": "Researches business strategy information",
    "instruction": """You are a business strategy researcher.

For the company mentioned by the user, research and provide a comprehensive report covering:

1. Company Overview - History, mission, vision, current status
2. Business Value Propositions - Core value the company delivers to customers overall
3. Products and Services - Product categories and specific products with their value propositions
4. SWOT Analysis - For each strength, identify opportunities it creates. For each weakness, identify risks it exposes.
5. Strategic Goals - Top strategic objectives the company should focus on

Use the google_search agent to find current information about the company.
Provide detailed, factual research findings.
Be specific and include examples of how strengths create opportunities and weaknesses create risks.""",
    "generate_content_config": {
        "temperature": 0.3,
        "max_output_tokens": 2500,
    },
    "metadata": {
        "version": "v1.0",
        "variant_name": "baseline",
        "experiment_id": "baseline",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": "initial_setup_script",
        "notes": "Baseline configuration extracted from business_agents.py. Researcher agent with google_search tool, no output_schema.",
    },
}

BUSINESS_FORMATTER_CONFIG = {
    "name": "business_formatter",
    "model": "gemini-2.5-pro",
    "description": "Formats business research into structured strategy",
    "instruction": """You are a business strategy formatter.

Take the research report provided by the user and format it into a structured business strategy.

For the structured output:

1. Extract 1-5 business-level value propositions that describe the overall company value
2. Extract 1-5 main product categories with 1-5 specific products each
3. For SWOT Analysis:
   - Identify 1-5 core strengths, and for EACH strength list 1-5 opportunities it creates
   - Identify 1-5 key weaknesses, and for EACH weakness list 1-5 risks it exposes
4. Identify 1-5 strategic goals

Create IDs using lowercase-hyphenated format (e.g., 'strength-brand-recognition').
Be specific and actionable in all descriptions.
Ensure all required fields are populated.""",
    "generate_content_config": {
        "temperature": 0.1,
        "max_output_tokens": 2500,
    },
    "metadata": {
        "version": "v1.0",
        "variant_name": "baseline",
        "experiment_id": "baseline",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": "initial_setup_script",
        "notes": "Baseline configuration extracted from business_agents.py. Formatter agent with StructuredBusinessStrategy output_schema, no tools. Uses gemini-2.5-pro for better schema handling.",
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
        dry_run: If True, only print what would be uploaded

    Returns:
        True if successful, False otherwise
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would upload config for '{doc_id}':")
        logger.info(f"  Model: {config.get('model')}")
        logger.info(f"  Version: {config.get('metadata', {}).get('version')}")
        logger.info(f"  Instruction length: {len(config.get('instruction', ''))} chars")
        return True

    try:
        db = firestore.Client(project=project_id)
        doc_ref = db.collection("agent_configs").document(doc_id)

        # Check if document already exists
        existing_doc = doc_ref.get()
        if existing_doc.exists:
            logger.warning(
                f"Document '{doc_id}' already exists in Firestore. "
                "Use --force to overwrite (not implemented for safety)."
            )
            logger.info(
                "Skipping upload. To update, edit directly in Firestore Console."
            )
            return False

        # Upload to Firestore
        doc_ref.set(config)

        logger.info(f"✅ Successfully uploaded config for '{doc_id}'")
        logger.info(f"   Model: {config.get('model')}")
        logger.info(f"   Version: {config.get('metadata', {}).get('version')}")
        logger.info(f"   Variant: {config.get('metadata', {}).get('variant_name')}")

        return True

    except Exception as e:
        logger.error(f"❌ Failed to upload config for '{doc_id}': {e}")
        return False


def main():
    """Main function to upload baseline configurations."""
    parser = argparse.ArgumentParser(
        description="Upload baseline agent configurations to Firestore"
    )
    parser.add_argument(
        "--project-id",
        default="ken-e-dev",
        help="GCP project ID (default: ken-e-dev)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run - show what would be uploaded without uploading",
    )
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("Uploading Baseline Agent Configurations to Firestore")
    logger.info(f"Project ID: {args.project_id}")
    logger.info(f"Dry Run: {args.dry_run}")
    logger.info("=" * 70)

    # Upload researcher config
    logger.info("\n1. Uploading business_researcher config...")
    researcher_success = upload_config_to_firestore(
        BUSINESS_RESEARCHER_CONFIG,
        "business_researcher",
        args.project_id,
        args.dry_run,
    )

    # Upload formatter config
    logger.info("\n2. Uploading business_formatter config...")
    formatter_success = upload_config_to_firestore(
        BUSINESS_FORMATTER_CONFIG,
        "business_formatter",
        args.project_id,
        args.dry_run,
    )

    # Summary
    logger.info("\n" + "=" * 70)
    if args.dry_run:
        logger.info("DRY RUN COMPLETE - No changes made")
    else:
        if researcher_success and formatter_success:
            logger.info("✅ All configurations uploaded successfully!")
            logger.info("\nNext steps:")
            logger.info("1. Verify configs in Firestore Console:")
            logger.info(
                f"   https://console.firebase.google.com/project/{args.project_id}/firestore"
            )
            logger.info("2. Update business_agents.py to use Firestore configs")
            logger.info("3. Test agent creation with new config loader")
        else:
            logger.warning("⚠️  Some configurations failed to upload")
            logger.info("Check logs above for details")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
