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
  Restoring those agents from scratch needs a separate seed flow.

The 8 audited fields and their researcher / formatter profiles live in
``app.adk.agents.scripts._seed_helpers``; this script imports them so the
matrix has a single source of truth.

.. warning::

   **Re-running this script overwrites the business-pair full baselines
   (`model`, `instruction`, `temperature`, `max_output_tokens`,
   `metadata`)** with the values in this file. Fields NOT in the seed
   dict are preserved by ``set(..., merge=True)``. The 6
   audit-fields-only entries (competitive / marketing / brand
   researchers and formatters) only write the 8 audit fields and leave
   existing live instruction / model / temperature alone.

   The shared helper logs a warning when a clean-env run would create a
   sparse audit-fields-only doc, since such a doc will not boot a real
   agent without further seeding.

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
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Make ``app`` importable when this file is executed as a script.
_repo_root = Path(__file__).resolve().parent
while _repo_root != _repo_root.parent and not (_repo_root / ".git").exists():
    _repo_root = _repo_root.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from app.adk.agents.scripts._seed_helpers import (  # noqa: E402
    AUDIT_FIELDS_FORMATTER,
    AUDIT_FIELDS_RESEARCHER,
    upsert_agent_config,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
    """Thin wrapper around the shared ``upsert_agent_config`` helper."""
    return upsert_agent_config(config, doc_id, project_id, dry_run=dry_run)


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
