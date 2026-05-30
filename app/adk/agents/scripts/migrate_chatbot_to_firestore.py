#!/usr/bin/env python3
"""
Migrate KEN-E chatbot configuration to Firestore.

This script creates the `ken_e_chatbot` configuration document in Firestore,
enabling model selection and runtime configuration updates for the chatbot agent.

.. warning::

   **Re-running this script overwrites** `instruction`, `model`,
   `temperature`, `max_output_tokens`, and `metadata` on the existing
   `ken_e_chatbot` doc with the values in this file. Fields NOT in the
   seed dict (e.g. anything added later via the Admin UI) are preserved
   by ``set(..., merge=True)``. **Treat this file as the source of truth
   for the fields it carries**: if you change those fields via Admin UI,
   reconcile back to this file before re-running, or you'll lose the
   admin edit on the next seed.

Usage:
    python migrate_chatbot_to_firestore.py [--project-id PROJECT_ID] [--dry-run]

Examples:
    # Development environment
    python migrate_chatbot_to_firestore.py --project-id ken-e-dev

    # Staging environment
    python migrate_chatbot_to_firestore.py --project-id ken-e-staging

    # Production environment
    python migrate_chatbot_to_firestore.py --project-id ken-e-production

    # Dry run (no actual changes)
    python migrate_chatbot_to_firestore.py --project-id ken-e-dev --dry-run
"""

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make ``app`` importable when this file is executed as a script (``uv run
# python /path/to/this.py``). Walks up to the repo root, identified by
# the presence of a ``.git`` entry, and prepends it to ``sys.path``.
_repo_root = Path(__file__).resolve().parent
while _repo_root != _repo_root.parent and not (_repo_root / ".git").exists():
    _repo_root = _repo_root.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from app.adk.agents.scripts._seed_helpers import (  # noqa: E402
    AUDIT_FIELDS_RESEARCHER,
    upsert_agent_config,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# KEN-E Chatbot configuration
KEN_E_CHATBOT_CONFIG = {
    "name": "ken_e_chatbot",
    "model": "gemini-2.5-pro",
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

**TASK DELEGATION:**
Before calling `search_company_news` or `query_google_analytics`, generate 2-4 specific acceptance criteria that the specialist's response must satisfy. Pass them as the `acceptance_criteria` parameter.

Good criteria are:
- **Verifiable from the draft text alone** — the reviewer is a structural/format checker, not a fact-checker; it cannot verify claims that require external knowledge
- **Measurable:** "Include a table with columns: campaign name, sessions, engagement rate"
- **Specific:** "Cover the past 30 days of data"
- **Format-bound:** "Output as a numbered list"

Bad criteria (vague or unverifiable):
- "Provide useful information" — vague; no clear pass/fail signal
- "Numbers must be accurate" — requires fact-checking; the reviewer cannot verify factual claims
- "Be comprehensive" — vague; cannot be verified from the response text

For trivially simple lookups, omit the criteria — the dispatch falls back to single-pass.

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
    # AH-40: flat shape — temperature and max_output_tokens live at the top
    # level. Must be run AFTER the flatten_agent_config_storage backfill in
    # any environment that has pre-AH-40 nested docs, or right after PR
    # merge in a clean environment.
    "temperature": 0.7,
    "max_output_tokens": 4096,
    # AH-89: enable Gemini thought emission. budget=2048 is bounded (vs. -1
    # "dynamic" which is uncapped) while giving meaningful reasoning headroom
    # for typical chat queries. Tunable via Firestore admin write without a
    # redeploy — AH-PRD-09 config_cache TTL propagates the change in ≤60 s.
    # Set to None to disable thinking entirely.
    "thinking_budget": 2048,
    # AH-41: the 8 audited fields are written explicitly so behavior is
    # not silently driven by Pydantic schema defaults. The orchestrator
    # is visible in the Workflows > Agents UI (it IS the chat agent) but
    # NOT copyable — users create custom agents via the new-agent flow
    # rather than forking the orchestrator. Hence the
    # ``available_to_copy=False`` override on top of the researcher
    # profile.
    **AUDIT_FIELDS_RESEARCHER,
    "available_to_copy": False,
    "metadata": {
        "version": "v1.3",
        "variant_name": "baseline",
        "experiment_id": "baseline",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": "migration_script",
        "notes": "Initial chatbot configuration migrated from hardcoded ken_e_agent.py. Enables model selection and runtime updates via Admin UI. v1.1: Added Task Delegation section with 2-4 acceptance-criteria generation guidance per AH-6 (AH-PRD-01 §7 AC#8). v1.2 (AH-41): added 8 audited fields explicitly (code_execution_enabled, mcp_servers, skill_ids, sandbox_code_executor_enabled, response_schema, available_to_copy=False, automatically_available, visible_in_frontend). v1.3 (AH-89): added thinking_budget=2048 to enable Gemini thought emission; unblocks CH-60 ThinkingBlock live reasoning.",
    },
}


def upload_config_to_firestore(
    config: dict, doc_id: str, project_id: str, dry_run: bool = False
) -> bool:
    """Thin wrapper around the shared ``upsert_agent_config`` helper.

    Retained as a module-level function so existing callers / tests that
    import this symbol keep working. The implementation lives in
    ``app.adk.agents.scripts._seed_helpers``.
    """
    return upsert_agent_config(config, doc_id, project_id, dry_run=dry_run)


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
