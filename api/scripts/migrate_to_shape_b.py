#!/usr/bin/env python3
"""migrate_to_shape_b.py — config-driven Shape A → Shape B Firestore migration CLI.

Usage
-----
  python api/scripts/migrate_to_shape_b.py --list
  python api/scripts/migrate_to_shape_b.py --resource=<name> --dry-run
  python api/scripts/migrate_to_shape_b.py --resource=<name>
  python api/scripts/migrate_to_shape_b.py --resource=<name> --confirm-delete
  python api/scripts/migrate_to_shape_b.py --all

Exit codes
----------
  0  success
  1  verification failed
  2  usage error (unknown resource, missing env var, unimplemented flag)
  3  runtime error (unexpected exception)

Environment variables
---------------------
  GOOGLE_CLOUD_PROJECT_ID  (required) — GCP project that holds the Firestore database.
  FIRESTORE_DATABASE_ID    (optional, default "(default)") — Firestore database ID.

Shape B convention
------------------
  All account-scoped data lives under accounts/{account_id}/{resource}/...
  See docs/design/components/data-management/README.md §7.1 for the full spec.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path bootstrap — allows running as `python api/scripts/migrate_to_shape_b.py`
# from the repo root without installing the package.
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _migrate_shape_b.resources import RESOURCES  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------
EXIT_SUCCESS = 0
EXIT_VERIFICATION_FAILED = 1
EXIT_USAGE_ERROR = 2
EXIT_RUNTIME_ERROR = 3


# ---------------------------------------------------------------------------
# Startup contract
# ---------------------------------------------------------------------------

def _load_env() -> tuple[str, str]:
    """Read and validate required environment variables.

    Returns
    -------
    tuple[str, str]
        ``(project_id, database_id)``

    Raises
    ------
    SystemExit(2)
        If ``GOOGLE_CLOUD_PROJECT_ID`` is not set.
    """
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "")
    if not project_id:
        print(
            "ERROR: GOOGLE_CLOUD_PROJECT_ID environment variable is not set.\n"
            "Set it before running this script, e.g.:\n"
            "  export GOOGLE_CLOUD_PROJECT_ID=ken-e-dev",
            file=sys.stderr,
        )
        sys.exit(EXIT_USAGE_ERROR)
    database_id = os.environ.get("FIRESTORE_DATABASE_ID", "(default)")
    return project_id, database_id


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def cmd_list() -> int:
    """Print the RESOURCES registry and exit 0."""
    if not RESOURCES:
        print("(no resources registered)")
    else:
        for name in sorted(RESOURCES):
            cfg = RESOURCES[name]
            print(f"{name} -> accounts/{{account_id}}/{cfg.new_subcollection}")
    return EXIT_SUCCESS


def cmd_resource_not_implemented(flag: str, sibling: str) -> int:
    """Stub for flags owned by sibling issues."""
    print(
        f"ERROR: {flag} is not yet implemented in DM-1.\n"
        f"It will be added by {sibling}.",
        file=sys.stderr,
    )
    return EXIT_USAGE_ERROR


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser."""
    parser = argparse.ArgumentParser(
        prog="migrate_to_shape_b",
        description=(
            "Config-driven migration from Firestore Shape A "
            "(top-level per-account collections) to Shape B "
            "(accounts/{account_id}/{resource}/... subcollections)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--list",
        action="store_true",
        help="Print all configured resources and exit 0.",
    )
    group.add_argument(
        "--resource",
        metavar="NAME",
        help=(
            "Migrate a single named resource.  "
            "Combine with --dry-run or --confirm-delete.  "
            "(Implemented by DM-2 / DM-3 / DM-5)"
        ),
    )
    group.add_argument(
        "--all",
        action="store_true",
        help=(
            "Migrate all configured resources in sequence.  "
            "(Implemented by DM-3)"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Print the migration plan without writing anything.  "
            "(Implemented by DM-6)"
        ),
    )
    parser.add_argument(
        "--confirm-delete",
        action="store_true",
        help=(
            "After a successful copy + verify, delete the source collections.  "
            "(Implemented by DM-5)"
        ),
    )
    return parser


def main() -> int:
    """Entry point.  Returns an exit code."""
    parser = build_parser()
    args = parser.parse_args()

    project_id, database_id = _load_env()
    logger.info("project_id=%s database_id=%s", project_id, database_id)

    if args.list:
        return cmd_list()

    if args.resource is not None:
        return cmd_resource_not_implemented("--resource", "DM-2 / DM-3 / DM-5 / DM-6")

    if args.all:
        return cmd_resource_not_implemented("--all", "DM-3")

    # Unreachable (argparse requires exactly one of the mutually-exclusive group)
    return EXIT_USAGE_ERROR  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
