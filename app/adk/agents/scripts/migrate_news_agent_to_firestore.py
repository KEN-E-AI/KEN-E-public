#!/usr/bin/env python3
"""
Migrate Company News agent configuration to Firestore.

This script creates the `company_news_agent` configuration document in Firestore,
enabling model selection and runtime configuration updates for the News agent.

Usage:
    python migrate_news_agent_to_firestore.py [--project-id PROJECT_ID] [--dry-run]

Examples:
    # Development environment
    python migrate_news_agent_to_firestore.py --project-id ken-e-dev

    # Staging environment
    python migrate_news_agent_to_firestore.py --project-id ken-e-staging

    # Production environment
    python migrate_news_agent_to_firestore.py --project-id ken-e-prod

    # Dry run (no actual changes)
    python migrate_news_agent_to_firestore.py --project-id ken-e-dev --dry-run
"""

import argparse
import logging
from datetime import datetime, timezone

from google.cloud import firestore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


NEWS_AGENT_CONFIG = {
    "name": "company_news_agent",
    "model": "gemini-2.5-pro",
    "description": "Company news assistant with curated news database access",
    "instruction": """You are a company news assistant with access to curated news databases.

**CRITICAL GROUNDING RULES:**
- You can ONLY provide information found through your Vertex AI Search tool
- You must ALWAYS use the search tool before responding to company queries
- NEVER use general knowledge or training data about companies
- NEVER make up information not explicitly found in search results

**SEARCH STRATEGY:**
- When searching for a company, use specific queries like "[Company] earnings", "[Company] news", "[Company] financial results"
- Avoid broad queries that might return tangential mentions
- Focus on finding articles where the company is the primary subject

**CRITICAL: DISTINGUISH BETWEEN COMPANY NEWS vs ANALYST COMMENTARY**
NOT VALID - Analyst commentary FROM a company ABOUT other topics:
  - "JP Morgan analyst says Tesla will rise" - This is JP Morgan commenting on Tesla, NOT news about JP Morgan
  - "According to JP Morgan, 77% beat earnings" - This is JP Morgan's analysis of the market, NOT news about JP Morgan
  - "JP Morgan notes that tariffs..." - This is JP Morgan's opinion on tariffs, NOT news about JP Morgan

VALID - Actual news ABOUT the company itself:
  - "JP Morgan reports quarterly earnings"
  - "JP Morgan announces new CEO"
  - "JP Morgan faces regulatory investigation"

**SEARCH RELEVANCE REQUIREMENTS:**
- ONLY count results about the company's own business, operations, financial performance, leadership, or corporate actions
- REJECT ALL results where the company is just providing analysis, commentary, or opinions about other topics
- If search only returns analyst commentary/opinions FROM the company, treat as "no relevant results"

**CONTENT-BASED VALIDATION:**
- Examine the title, source, and content of each search result carefully
- Look for document structure and context clues that indicate the primary subject
- Pay attention to whether the company name appears in headlines vs just in passing mentions
- Consider the source URL and document organization

**RESPONSE FORMAT:**
1. Search using your tool
2. For each result, analyze the title, content structure, and context
3. Ask: "Is this article primarily ABOUT the requested company's business activities?"
4. If the company only appears as a source of commentary about other topics, REJECT that result
5. Only use results where the company is clearly the main business subject
6. If no validated results: "I don't have any news about [Company] in my curated database"

**KEY VALIDATION:** Before sharing any information, verify that the search results are discussing the company's own business activities, not the company providing analysis about other entities.""",
    # AH-40: flat shape — temperature and max_output_tokens live at the top
    # level. Must be run AFTER the flatten_agent_config_storage backfill in
    # any environment that has pre-AH-40 nested docs, or right after PR
    # merge in a clean environment.
    "temperature": 0.7,
    "max_output_tokens": 4096,
    # AH-41: the 8 audited fields are now written explicitly so behavior is
    # not silently driven by Pydantic schema defaults. See the decision
    # matrix in the AH-41 PR description.
    #
    # company_news_agent uses the Vertex AI Search tool (declared in agent
    # code, not Firestore) rather than an MCP toolset, so mcp_servers is
    # an empty list. All other fields take defaults.
    "code_execution_enabled": False,
    "mcp_servers": [],
    "skill_ids": [],
    "sandbox_code_executor_enabled": False,
    "response_schema": None,
    "available_to_copy": True,
    "automatically_available": True,
    "visible_in_frontend": True,
    "metadata": {
        "version": "v1.1",
        "variant_name": "baseline",
        "experiment_id": "baseline",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": "migration_script",
        "notes": "Initial News agent configuration migrated from hardcoded company_news_chatbot/agent.py. v1.1 (AH-41): added 8 audited fields explicitly.",
    },
}


def upload_config_to_firestore(
    config: dict, doc_id: str, project_id: str, dry_run: bool = False
) -> bool:
    """Idempotently upload a configuration document to Firestore (AH-41).

    Uses ``set(config, merge=True)`` so re-running the script writes only
    the keys present in ``config`` and preserves anything else on the
    existing doc.

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
            logger.info(f"[DRY RUN] Would upsert config '{doc_id}' to Firestore:")
            logger.info(f"  Model: {config['model']}")
            logger.info(f"  Description: {config['description']}")
            logger.info(f"  Project: {project_id}")
            return True

        db = firestore.Client(project=project_id)
        doc_ref = db.collection("agent_configs").document(doc_id)
        existed = doc_ref.get().exists

        doc_ref.set(config, merge=True)
        action = "Updated" if existed else "Created"
        logger.info(
            f"{action} config '{doc_id}' in Firestore "
            f"(model: {config['model']})"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to upsert config '{doc_id}': {e}")
        return False


def main():
    """Main script entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate Company News agent configuration to Firestore"
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

    logger.info("Starting Company News agent config migration to Firestore")
    logger.info(f"Project: {args.project_id}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("-" * 60)

    success = upload_config_to_firestore(
        config=NEWS_AGENT_CONFIG,
        doc_id="company_news_agent",
        project_id=args.project_id,
        dry_run=args.dry_run,
    )

    logger.info("-" * 60)
    if success:
        logger.info("Migration completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Verify config in Firestore console")
        logger.info("2. Deploy updated News agent code")
        logger.info("3. Test News agent with new config loading")
        logger.info("4. Update model/instruction via Admin UI if needed")
    else:
        logger.error("Migration failed!")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
