#!/usr/bin/env python3
"""profile_org_doc_sizes.py — READ-ONLY profiler for organizations/{org_id} Firestore doc sizes.

Purpose
-------
Measures current `organizations/{org_id}` document sizes to inform the Shape D Split
storage-strategy decision (DM-PRD-03 §6.AC-1): whether to use Style A (map field) or
Style B (subcollection) for funnel data.

READ-ONLY — this script performs no writes or deletes.  It is safe to run against
production.

AC reference
------------
DM-PRD-03 §6.AC-1: A profiling script measures current org-doc sizes and produces a
`ProfileSummary` JSON with p50 / p95 / p99 byte-size percentiles and threshold-band
counters (500 KiB / 750 KiB) for org-level and per-account-level docs.

Byte-size approximation methodology
------------------------------------
`approx_doc_bytes()` serialises each document to JSON via `json.dumps(d, default=str)`,
then measures the UTF-8 byte length of the resulting string.  This overestimates actual
Firestore storage by roughly 10-20 % because JSON includes explicit field-name quoting
and whitespace-free serialisation, whereas Firestore uses a more compact binary encoding.
The approximation is sufficient for distinguishing documents in the 500 KiB / 750 KiB
threshold bands used by this analysis.

Usage
-----
  python api/scripts/profile_org_doc_sizes.py

Environment variables
---------------------
  GOOGLE_CLOUD_PROJECT_ID  (required) — GCP project that holds the Firestore database.
  FIRESTORE_DATABASE_ID    (optional, default "(default)") — Firestore database ID.

Note on --env flag
------------------
The DM-PRD-03 §5 sketch uses `--env=dev` as an illustrative invocation.  This script
intentionally omits the `--env` flag and uses environment variables instead, consistent
with the pattern in `migrate_to_shape_b.py` and `./scripts/set_environment.sh`.

Output
------
  Per-org tab-separated rows are printed to stdout.
  A `=== JSON SUMMARY ===` delimiter is printed, followed by a `ProfileSummary` JSON
  block.  All log messages go to stderr.

Exit codes
----------
  0  success
  1  no organisations found (soft warning — safe for empty environments)
  2  usage error (missing required environment variable)
  3  runtime error (unexpected exception)
"""

import argparse
import json
import logging
import os
import sys
from collections.abc import Generator
from typing import Any

from pydantic import BaseModel

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
EXIT_NO_ORGS = 1
EXIT_USAGE_ERROR = 2
EXIT_RUNTIME_ERROR = 3

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

BYTE_SIZE_METHODOLOGY = (
    "approx_doc_bytes(): len(json.dumps(doc, default=str).encode('utf-8')). "
    "Overestimates actual Firestore storage by ~10-20% due to JSON field-name "
    "quoting vs raw Firestore encoding. Sufficient for 500/750 KiB "
    "threshold-band decision."
)


class OrgProfile(BaseModel):
    org_id: str
    byte_size: int
    account_count: int
    max_account_byte_size: int
    max_funnel_depth: int


class ProfileSummary(BaseModel):
    total_orgs: int
    total_accounts: int
    total_size_p50: int
    total_size_p95: int
    total_size_p99: int
    per_account_size_p50: int
    per_account_size_p95: int
    per_account_size_p99: int
    orgs_over_500_kib: int
    orgs_over_750_kib: int
    accounts_over_500_kib: int
    accounts_over_750_kib: int
    max_funnel_depth_overall: int
    byte_size_methodology: str
    orgs: list[OrgProfile]


# ---------------------------------------------------------------------------
# Pure-function metric helpers (no Firestore dependency)
# ---------------------------------------------------------------------------

_KIB_500 = 500 * 1024
_KIB_750 = 750 * 1024
_MAX_FUNNEL_DEPTH = 50


def approx_doc_bytes(d: dict[str, Any]) -> int:
    """Return the approximate UTF-8 byte size of a Firestore document.

    Serialises `d` to a compact JSON string (using `default=str` for
    non-serialisable values such as `datetime` or Firestore references) and
    measures the resulting byte length.  Overestimates actual Firestore storage
    by ~10-20 %; sufficient for 500 / 750 KiB threshold-band analysis.
    """
    return len(json.dumps(d, default=str).encode("utf-8"))


def max_funnel_depth(funnels: dict[str, Any]) -> int:
    """Return the maximum nesting depth within a funnels dict.

    Recursively walks the dict tree and returns the greatest depth found.
    Returns 0 for an empty or non-dict argument.
    """

    def _depth(obj: Any, current: int) -> int:
        if not isinstance(obj, dict) or not obj or current >= _MAX_FUNNEL_DEPTH:
            return current
        return max(_depth(v, current + 1) for v in obj.values())

    if not isinstance(funnels, dict) or not funnels:
        return 0
    return _depth(funnels, 0)


def percentile(values: list[int], p: float) -> int:
    """Return the linearly-interpolated p-th percentile of `values`.

    Parameters
    ----------
    values:
        List of integer measurements.  Need not be sorted.
    p:
        Fraction in [0, 1] (e.g. 0.95 for the 95th percentile).

    Returns
    -------
    int
        Interpolated percentile value, or 0 if `values` is empty.
    """
    if not values:
        return 0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    idx = p * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return int(sorted_vals[lo] + frac * (sorted_vals[hi] - sorted_vals[lo]))


# ---------------------------------------------------------------------------
# Firestore wiring
# ---------------------------------------------------------------------------


def _iter_org_docs(client: Any) -> Generator[tuple[str, dict[str, Any]], None, None]:
    """Stream the `organizations` collection, yielding (org_id, doc_dict) tuples.

    Parameters
    ----------
    client:
        An initialised `google.cloud.firestore.Client` instance.

    Yields
    ------
    tuple[str, dict]
        ``(org_id, document_data)`` for every document in the collection.
    """
    for snapshot in client.collection("organizations").stream():
        yield snapshot.id, snapshot.to_dict() or {}


# ---------------------------------------------------------------------------
# Startup helpers
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
# Main
# ---------------------------------------------------------------------------

_HEADER = "org_id\tbyte_size\taccount_count\tmax_account_byte_size\tmax_funnel_depth"


def main() -> int:
    """Entry point.  Returns an exit code."""
    parser = argparse.ArgumentParser(
        prog="profile_org_doc_sizes",
        description=(
            "READ-ONLY profiler for organizations/{org_id} Firestore doc sizes. "
            "Prints per-org tab-separated rows to stdout, followed by a JSON summary. "
            "No writes or deletes are performed."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.parse_args()

    project_id, database_id = _load_env()
    logger.info("project_id=%s database_id=%s", project_id, database_id)

    try:
        from google.cloud import firestore  # type: ignore[import]

        client = firestore.Client(project=project_id, database=database_id)
    except Exception as exc:
        print(f"ERROR: Failed to initialise Firestore client: {exc}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR

    profiles: list[OrgProfile] = []
    all_account_byte_sizes: list[int] = []

    print(_HEADER)

    try:
        for org_id, doc_dict in _iter_org_docs(client):
            try:
                byte_size = approx_doc_bytes(doc_dict)
                accounts_map: dict[str, Any] = doc_dict.get("accounts", {})
                if not isinstance(accounts_map, dict):
                    accounts_map = {}

                account_count = len(accounts_map)

                per_acc_sizes: list[int] = []
                org_max_funnel_depth = 0

                for _account_id, acc_data in accounts_map.items():
                    if not isinstance(acc_data, dict):
                        acc_data = {}
                    acc_size = approx_doc_bytes(acc_data)
                    per_acc_sizes.append(acc_size)
                    all_account_byte_sizes.append(acc_size)

                    funnels = acc_data.get("funnels", {})
                    if not isinstance(funnels, dict):
                        funnels = {}
                    depth = max_funnel_depth(funnels)
                    if depth > org_max_funnel_depth:
                        org_max_funnel_depth = depth

                max_account_byte_size = max(per_acc_sizes) if per_acc_sizes else 0

                print(
                    f"{org_id}\t{byte_size}\t{account_count}\t"
                    f"{max_account_byte_size}\t{org_max_funnel_depth}"
                )

                profiles.append(
                    OrgProfile(
                        org_id=org_id,
                        byte_size=byte_size,
                        account_count=account_count,
                        max_account_byte_size=max_account_byte_size,
                        max_funnel_depth=org_max_funnel_depth,
                    )
                )
            except Exception as exc:
                logger.warning("Skipping org %s due to processing error: %s", org_id, exc)
    except Exception as exc:
        logger.exception("Unexpected error while streaming org documents: %s", exc)
        return EXIT_RUNTIME_ERROR

    if not profiles:
        print(
            "WARNING: No organisations found in the 'organizations' collection.",
            file=sys.stderr,
        )
        return EXIT_NO_ORGS

    org_byte_sizes = [p.byte_size for p in profiles]

    summary = ProfileSummary(
        total_orgs=len(profiles),
        total_accounts=sum(p.account_count for p in profiles),
        total_size_p50=percentile(org_byte_sizes, 0.50),
        total_size_p95=percentile(org_byte_sizes, 0.95),
        total_size_p99=percentile(org_byte_sizes, 0.99),
        per_account_size_p50=percentile(all_account_byte_sizes, 0.50),
        per_account_size_p95=percentile(all_account_byte_sizes, 0.95),
        per_account_size_p99=percentile(all_account_byte_sizes, 0.99),
        orgs_over_500_kib=sum(1 for s in org_byte_sizes if s > _KIB_500),
        orgs_over_750_kib=sum(1 for s in org_byte_sizes if s > _KIB_750),
        accounts_over_500_kib=sum(1 for s in all_account_byte_sizes if s > _KIB_500),
        accounts_over_750_kib=sum(1 for s in all_account_byte_sizes if s > _KIB_750),
        max_funnel_depth_overall=max((p.max_funnel_depth for p in profiles), default=0),
        byte_size_methodology=BYTE_SIZE_METHODOLOGY,
        orgs=profiles,
    )

    print("\n=== JSON SUMMARY ===\n")
    print(summary.model_dump_json(indent=2))

    return EXIT_SUCCESS


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logger.exception("Unexpected top-level error")
        sys.exit(EXIT_RUNTIME_ERROR)
