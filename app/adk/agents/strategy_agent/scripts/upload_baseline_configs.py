#!/usr/bin/env python3
"""Upload baseline / audit-field seeds for strategy agent_configs to Firestore.

Covers the eight strategy-agent globals under ``agent_configs/``:

* ``business_researcher`` / ``business_formatter`` — full baselines retained
  from the original v1.0 seed (model, instruction, temperature, etc.) so a
  fresh environment can bootstrap from this script. Flat AH-40 shape.
* ``competitive_researcher`` / ``competitive_formatter`` /
  ``marketing_researcher`` / ``marketing_formatter`` /
  ``brand_researcher`` / ``brand_formatter`` — these were populated
  out-of-band and live in Firestore with bespoke, hand-tuned instructions.
  This script seeds only the **8 audited fields** (AH-41) for those agents
  and relies on ``set(..., merge=True)`` to leave existing content intact.
  Restoring those agents from scratch needs a separate seed flow (not
  blocking AH-41 — see AC-2).

AH-41 audit fields:

* ``code_execution_enabled``
* ``mcp_servers``
* ``skill_ids``
* ``sandbox_code_executor_enabled``
* ``response_schema``
* ``available_to_copy``  (formatters: False — internal pipeline stage)
* ``automatically_available``
* ``visible_in_frontend`` (formatters: False — internal pipeline stage)

Idempotency: ``set(..., merge=True)`` — re-running produces zero field
changes once the audited fields are present.

Usage::

    cd api

    # Dry run
    uv run python ../app/adk/agents/strategy_agent/scripts/upload_baseline_configs.py \\
        --project-id ken-e-dev --dry-run

    # Live seed all 8 strategy agents
    uv run python ../app/adk/agents/strategy_agent/scripts/upload_baseline_configs.py \\
        --project-id ken-e-dev

    # Subset (e.g., only brand)
    uv run python ../app/adk/agents/strategy_agent/scripts/upload_baseline_configs.py \\
        --project-id ken-e-dev --agents brand_researcher,brand_formatter
"""

import argparse
import logging
from datetime import datetime, timezone
from typing import Any

from google.cloud import firestore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AH-41 audit-field profiles
# ---------------------------------------------------------------------------
#
# Researcher and formatter profiles are identical EXCEPT for the two
# user-facing flags: formatters are internal review-loop stages, so they
# are hidden from the Workflows > Agents UI (``visible_in_frontend=False``)
# and not forkable (``available_to_copy=False``).

AUDIT_FIELDS_RESEARCHER: dict[str, Any] = {
    "code_execution_enabled": False,
    "mcp_servers": [],
    "skill_ids": [],
    "sandbox_code_executor_enabled": False,
    "response_schema": None,
    "available_to_copy": True,
    "automatically_available": True,
    "visible_in_frontend": True,
}

AUDIT_FIELDS_FORMATTER: dict[str, Any] = {
    "code_execution_enabled": False,
    "mcp_servers": [],
    "skill_ids": [],
    "sandbox_code_executor_enabled": False,
    "response_schema": None,
    "available_to_copy": False,
    "automatically_available": True,
    "visible_in_frontend": False,
}


# ---------------------------------------------------------------------------
# Business researcher + formatter — full baseline (retained from v1.0 seed)
# ---------------------------------------------------------------------------

BUSINESS_RESEARCHER_CONFIG: dict[str, Any] = {
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
    # AH-40: flat shape — was previously nested under generate_content_config.
    "temperature": 0.3,
    "max_output_tokens": 2500,
    # AH-41: explicit audit fields (researcher profile).
    **AUDIT_FIELDS_RESEARCHER,
}

BUSINESS_FORMATTER_CONFIG: dict[str, Any] = {
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
    # AH-40: flat shape — was previously nested under generate_content_config.
    "temperature": 0.1,
    "max_output_tokens": 2500,
    # AH-41: explicit audit fields (formatter profile).
    **AUDIT_FIELDS_FORMATTER,
}


def _build_metadata(notes: str, version: str = "v1.1") -> dict[str, Any]:
    """Build a metadata block for a full baseline seed.

    Only used for the business pair. The other six strategy agents preserve
    whatever metadata is currently on their live docs (merge=True does not
    touch fields we do not write).
    """
    now = datetime.now(timezone.utc).isoformat()
    return {
        "version": version,
        "variant_name": "baseline",
        "experiment_id": "baseline",
        "created_at": now,
        "updated_at": now,
        "updated_by": "initial_setup_script",
        "notes": notes,
    }


BUSINESS_RESEARCHER_CONFIG["metadata"] = _build_metadata(
    "Baseline configuration extracted from business_agents.py. Researcher "
    "agent with google_search tool, no output_schema. v1.1 (AH-40 + AH-41): "
    "flat temperature/max_output_tokens; explicit audit fields."
)
BUSINESS_FORMATTER_CONFIG["metadata"] = _build_metadata(
    "Baseline configuration extracted from business_agents.py. Formatter "
    "agent with StructuredBusinessStrategy output_schema, no tools. Uses "
    "gemini-2.5-pro for better schema handling. v1.1 (AH-40 + AH-41): flat "
    "temperature/max_output_tokens; explicit audit fields (hidden + "
    "non-copyable per formatter profile)."
)


# ---------------------------------------------------------------------------
# Seed registry — what gets written for each doc_id
# ---------------------------------------------------------------------------

SEEDS: dict[str, dict[str, Any]] = {
    "business_researcher": BUSINESS_RESEARCHER_CONFIG,
    "business_formatter": BUSINESS_FORMATTER_CONFIG,
    # The six below are AH-41 audit-field-only seeds. Live content
    # (instruction/model/temperature/etc.) is preserved by set(merge=True).
    "competitive_researcher": dict(AUDIT_FIELDS_RESEARCHER),
    "competitive_formatter": dict(AUDIT_FIELDS_FORMATTER),
    "marketing_researcher": dict(AUDIT_FIELDS_RESEARCHER),
    "marketing_formatter": dict(AUDIT_FIELDS_FORMATTER),
    "brand_researcher": dict(AUDIT_FIELDS_RESEARCHER),
    "brand_formatter": dict(AUDIT_FIELDS_FORMATTER),
}


def upload_config_to_firestore(
    config: dict[str, Any],
    doc_id: str,
    project_id: str,
    dry_run: bool = False,
) -> bool:
    """Idempotently upsert a configuration document.

    Uses ``set(config, merge=True)`` so re-running the script writes only
    the keys present in ``config`` and preserves anything else on the
    existing doc (e.g. live instructions on the six audit-field-only
    entries above).
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would upsert '{doc_id}':")
        logger.info(f"  fields: {sorted(config.keys())}")
        return True

    try:
        db = firestore.Client(project=project_id)
        doc_ref = db.collection("agent_configs").document(doc_id)
        existed = doc_ref.get().exists

        doc_ref.set(config, merge=True)
        action = "Updated" if existed else "Created"
        logger.info(f"✅ {action} config '{doc_id}'")
        return True

    except Exception as exc:
        logger.error(f"❌ Failed to upsert config '{doc_id}': {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Upload baseline / audit-field seeds for strategy agent_configs "
            "(AH-41)."
        )
    )
    parser.add_argument(
        "--project-id",
        default="ken-e-dev",
        help="GCP project ID (default: ken-e-dev)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be uploaded without writing.",
    )
    parser.add_argument(
        "--agents",
        default="",
        help=(
            "Comma-separated subset of agent doc_ids to seed. Defaults to "
            "all 8 strategy agents."
        ),
    )
    args = parser.parse_args()

    if args.agents:
        requested = [a.strip() for a in args.agents.split(",") if a.strip()]
        unknown = [a for a in requested if a not in SEEDS]
        if unknown:
            logger.error(f"Unknown agent IDs: {unknown}. Known: {sorted(SEEDS)}")
            return 1
        seed_ids = requested
    else:
        seed_ids = list(SEEDS)

    logger.info("=" * 70)
    logger.info("AH-41 strategy agent_configs seed")
    logger.info(f"Project ID: {args.project_id}")
    logger.info(f"Dry run:    {args.dry_run}")
    logger.info(f"Agents:     {seed_ids}")
    logger.info("=" * 70)

    failed: list[str] = []
    for doc_id in seed_ids:
        ok = upload_config_to_firestore(
            SEEDS[doc_id], doc_id, args.project_id, args.dry_run
        )
        if not ok:
            failed.append(doc_id)

    logger.info("=" * 70)
    if failed:
        logger.error(f"⚠️  Failed: {failed}")
        return 1
    logger.info("✅ Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
