#!/usr/bin/env python3
"""
Migrate Synthesizer agent configuration to Firestore (AH-127 / AH-PRD-14 §2 / §5).

Seeds the default fan-in executor that the AH-PRD-05 supervisor-orchestration
coordinator will delegate to after fanning out independent per-task specialists.
The coordinator writes upstream ``result_key`` values into
``session.state["synthesis_input"]`` before delegating; this agent's instruction
contains a single ``{synthesis_input?}`` placeholder that ADK (string-instruction
path) or AH-PRD-05's callable closure substitutes at LLM-call time.

This script writes one Firestore document:

    ``agent_configs/synthesizer``

The doc carries the standard ``AgentConfig`` field set for an *internal
pipeline-stage* agent (``AUDIT_FIELDS_FORMATTER`` profile + ``ken_e_sub_agent=False``).
``include_contents='none'`` is intentionally **not** stored on the seed doc — wiring
it onto the constructed ``LlmAgent`` is AH-PRD-05's responsibility (Decision D1).

.. warning::

   **Re-running this script overwrites** the fields it manages (``set(..., merge=True)``
   semantics — only keys present in the seed dict are written; anything else on the
   existing doc is preserved).  **Treat this file as the source of truth for the
   fields it carries**: if you change ``instruction`` via the Admin UI, reconcile back
   here before re-running, or you will lose the admin edit on the next seed.

Usage:
    python migrate_synthesizer_to_firestore.py [--project-id PROJECT_ID] [--dry-run]

Examples:
    # Development environment (satisfies AH-PRD-14 §7 AC-5)
    python migrate_synthesizer_to_firestore.py --project-id ken-e-dev

    # Staging environment (run after AH-PRD-05 ships the coordinator)
    python migrate_synthesizer_to_firestore.py --project-id ken-e-staging

    # Dry run (no actual changes)
    python migrate_synthesizer_to_firestore.py --project-id ken-e-dev --dry-run
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
    upsert_agent_config,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Synthesizer instruction
# ---------------------------------------------------------------------------

SYNTHESIZER_INSTRUCTION = """\
You are an internal result synthesizer. Your role is to combine completed research
from upstream specialists into a single coherent, user-facing response.

**CRITICAL — Input framing:**
The content below under ``{synthesis_input?}`` is **completed research** from upstream
task specialists, NOT a template to be filled in. Do NOT echo placeholder syntax
(such as curly braces) back to the user. The placeholders have already been replaced
with real data before you see this prompt.

**Your task:**
1. Read the upstream specialist results provided in the synthesis input below.
2. Synthesise them into a single, well-structured response that directly answers the
   user's original request.
3. Attribute findings to the relevant specialist where it adds clarity.
4. Do NOT invent figures, add unsupported claims, or pad the response.

**Synthesis input (upstream specialist results):**
{synthesis_input?}

**Format guidance:**
- Use Markdown headings to separate distinct topics when the synthesis spans multiple
  domains (e.g. Google Analytics results, Meta Ads results).
- Keep the response concise — a tight synthesis is more useful than a long recap.
- If the synthesis input is empty or absent, respond with a brief note that no
  upstream results were available for this turn.
"""


# ---------------------------------------------------------------------------
# Agent config document
# ---------------------------------------------------------------------------

SYNTHESIZER_CONFIG: dict[str, Any] = {
    # AH-84: human-readable identity (not surfaced in Available Specialists block
    # because ken_e_sub_agent=False, but present for admin UI / audit trail).
    "name": "Synth",
    "title": "Result Synthesizer",

    # Synthesis is mostly templating + light summarisation — flash-tier is
    # sufficient (matches the GA specialist's model after the AH-149 bump).
    "model": "gemini-2.5-flash",
    "instruction": SYNTHESIZER_INSTRUCTION,
    "temperature": 0.3,
    "max_output_tokens": 4096,

    "description": (
        "Internal fan-in executor for the AH-PRD-05 supervisor-orchestration model. "
        "Receives completed per-task specialist results via session.state['synthesis_input'] "
        "and combines them into a single coherent user-facing response. Not delegatable "
        "from the root agent (ken_e_sub_agent=False); reached exclusively by the "
        "coordinator via transfer_to_agent('synthesizer')."
    ),

    # No tools — pure LLM templating step.
    "tool_ids": [],

    # No review loop — synthesis over already-approved per-task drafts; a second
    # review layer adds LLM cost without a corresponding quality gain.
    "default_acceptance_criteria": None,
    "reviewer_model": None,

    # AH-82: delegation gate — MUST be False for internal pipeline-stage agents.
    # The coordinator (AH-PRD-05) reaches the synthesizer via transfer_to_agent
    # directly; the root LLM must never see it in the Available Specialists block.
    "ken_e_sub_agent": False,

    # AH-41: AUDIT_FIELDS_FORMATTER profile — internal pipeline stage:
    #   available_to_copy=False, automatically_available=True, visible_in_frontend=False
    #   code_execution_enabled=False, mcp_servers=[], skill_ids=[],
    #   sandbox_code_executor_enabled=False, response_schema=None
    **AUDIT_FIELDS_FORMATTER,

    "metadata": {
        "version": "v1.0",
        "variant_name": "baseline",
        "experiment_id": "baseline",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": "migration_script",
        "notes": (
            "AH-127 / AH-PRD-14 §2 / §5: initial synthesizer seed. "
            "Default fan-in executor for AH-PRD-05 supervisor-orchestration coordinator. "
            "Coordinator writes upstream result_key values to session.state['synthesis_input']; "
            "this agent's {synthesis_input?} placeholder is substituted at LLM-call time. "
            "include_contents='none' wiring is AH-PRD-05's responsibility (Decision D1). "
            "Staging/production runs await AH-PRD-05 coordinator shipment."
        ),
    },
}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Main script entry point.

    Returns:
        0 on success, 1 on failure.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Seed agent_configs/synthesizer in Firestore. "
            "Default fan-in executor for the AH-PRD-05 supervisor-orchestration model. "
            "Idempotent (set(..., merge=True) semantics)."
        )
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
        help="Dry run mode — show what would be done without making changes",
    )

    args = parser.parse_args()

    logger.info("Starting synthesizer agent config seed")
    logger.info("Project: %s", args.project_id)
    logger.info("Dry run: %s", args.dry_run)
    logger.info("-" * 60)

    success = upsert_agent_config(
        config=SYNTHESIZER_CONFIG,
        doc_id="synthesizer",
        project_id=args.project_id,
        dry_run=args.dry_run,
    )

    logger.info("-" * 60)
    if success:
        logger.info("Seed completed successfully!")
        logger.info("")
        logger.info("Next steps:")
        logger.info(
            "1. Verify agent_configs/synthesizer in the Firestore console"
        )
        logger.info(
            "2. On the next chat turn the runtime resolver picks up the new config"
            " via config_cache (<=60 s TTL) — no redeploy required"
        )
        logger.info(
            "3. The synthesizer has no consumer until AH-PRD-05 ships the coordinator"
            " — seeding higher environments early is harmless but not required"
        )
    else:
        logger.error("Seed failed!")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
