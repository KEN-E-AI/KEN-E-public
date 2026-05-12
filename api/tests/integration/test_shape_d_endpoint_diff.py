"""Integration test: KPI/funnel endpoint responses are unchanged by the Shape D split migration.

Closes DM-PRD-03 §6 AC-6:
  KPI and funnel endpoints return the same data before and after the migration
  for a seeded account (captured before/after JSON, diffed).

The test seeds a realistic Shape D fixture (org doc with nested accounts map) PLUS
the equivalent Shape B data (accounts/{aid} docs) — modelling the production state at
the time DM-44's destructive cutover fires: DM-41 has already written accounts/{aid};
DM-44 (``--confirm-delete-field``) has not yet removed the org doc's accounts map.
Because DM-42 moved every firestore.py KPI/funnel read path to ``accounts/{aid}``,
the pre-migration snapshot is non-empty only when the accounts/{aid} docs exist.

The destructive step (``org_ref.update({"accounts": DELETE_FIELD})``) is performed
inline.  When DM-44 ships, swap the inline call for the script's flag invocation
(one-line change, no test-logic change needed).

Run against the Firestore emulator:
    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/test_shape_d_endpoint_diff.py -v
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Skip gate
# ---------------------------------------------------------------------------
FIRESTORE_EMULATOR_HOST = os.getenv("FIRESTORE_EMULATOR_HOST")

pytestmark = pytest.mark.skipif(
    not FIRESTORE_EMULATOR_HOST,
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)

# ---------------------------------------------------------------------------
# Path bootstrap — lets us import migrate_shape_d_split from api/scripts/
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if SCRIPTS_DIR.is_dir() and str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
KPI_NAMES = ["income_kpi", "marketing_cost_kpi", "net_income_kpi"]
BIG_BET_NAMES = ["big_bet_1", "big_bet_2"]
ORG_FUNNEL_STEPS = [1, 2, 3]
BIG_BET_STEPS = [1, 2, 3]
CHANNEL_NAMES = ["channel_a", "channel_b"]
TACTIC_NAMES = ["tactic_1", "tactic_2"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _firestore_client() -> Any:
    """Build a synchronous Firestore client pointing at the emulator."""
    from google.cloud import firestore  # type: ignore[import]

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return firestore.Client(project=project)


def _delete_doc(client: Any, collection: str, doc_id: str) -> None:
    try:
        client.collection(collection).document(doc_id).delete()
    except Exception:
        pass


def _get_doc(client: Any, collection: str, doc_id: str) -> dict[str, Any] | None:
    snap = client.collection(collection).document(doc_id).get()
    return snap.to_dict() if snap.exists else None


# ---------------------------------------------------------------------------
# Seed payload builder
# ---------------------------------------------------------------------------


def _build_funnel_step(
    step_num: int,
    funnel_type: str,
    big_bet_name: str | None = None,
) -> dict[str, Any]:
    """Build a realistic funnel step payload with channels and tactics."""
    label = f"{funnel_type}_{big_bet_name or 'org'}_step{step_num}"
    channels: dict[str, Any] = {}
    for ch in CHANNEL_NAMES:
        tactics: dict[str, Any] = {}
        for tac in TACTIC_NAMES:
            tactics[tac] = {
                "effectiveness_kpi": f"m_eff_{label}_{ch}_{tac}",
                "efficiency_kpi": f"m_eff_{label}_{ch}_{tac}",
                "evaluation_metrics": [f"m_eval_{label}_{ch}_{tac}"],
            }
        channels[ch] = {
            "effectiveness_kpi": f"m_ch_eff_{label}_{ch}",
            "efficiency_kpi": f"m_ch_effi_{label}_{ch}",
            "evaluation_metrics": [f"m_ch_eval_{label}_{ch}"],
            "tactics": tactics,
        }
    return {
        "funnel_step_name": f"step_{step_num}",
        "effectiveness_kpi": f"m_step_eff_{label}",
        "efficiency_kpi": f"m_step_effi_{label}",
        "objective": f"Objective for {label}",
        "channels": channels,
    }


def _build_account_payload(account_id: str, org_id: str) -> dict[str, Any]:
    """Build a full Shape B payload for a single account.

    Matches the Style A format written by migrate_shape_d_split.py:
    funnels and account_settings are direct map fields on the account doc.
    """
    # Org funnel
    org_steps: dict[str, Any] = {
        str(n): _build_funnel_step(n, "organization") for n in ORG_FUNNEL_STEPS
    }
    # Big bets
    big_bets: dict[str, Any] = {}
    for bb in BIG_BET_NAMES:
        big_bets[bb] = {
            str(n): _build_funnel_step(n, "big_bet", bb) for n in BIG_BET_STEPS
        }

    return {
        "account_settings": {
            "overview_kpis": {
                "income_kpi": f"m_income_{account_id}",
                "marketing_cost_kpi": f"m_cost_{account_id}",
                "net_income_kpi": f"m_net_{account_id}",
            }
        },
        "funnels": {
            "organization": org_steps,
            "big_bets": big_bets,
        },
        "organization_id": org_id,
        "shape_d_migrated_at": datetime.now(tz=timezone.utc).isoformat(),
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


def _seed_shape_d_and_b(
    client: Any,
    org_id: str,
    account_ids: list[str],
) -> dict[str, dict[str, Any]]:
    """Seed both the Shape D org doc and Shape B accounts/{aid} docs.

    Returns a mapping of account_id → the per-account payload (without the
    migration timestamps) for use in structural assertions.
    """
    account_payloads: dict[str, dict[str, Any]] = {}
    org_accounts_map: dict[str, Any] = {}

    for aid in account_ids:
        payload = _build_account_payload(aid, org_id)
        account_payloads[aid] = payload

        # Shape D: nested in the org doc's accounts map (only the per-account fields)
        org_accounts_map[aid] = {
            "account_settings": payload["account_settings"],
            "funnels": payload["funnels"],
        }

        # Shape B: write the account doc directly (what the API reads from)
        client.collection("accounts").document(aid).set(payload)

    # Seed the Shape D org doc
    client.collection("organizations").document(org_id).set(
        {
            "name": "Test Org for AC-6",
            "agency": "Test Agency",
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "accounts": org_accounts_map,
        }
    )

    return account_payloads


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def run_id() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture()
def emulator_client() -> Any:
    return _firestore_client()


@pytest.fixture(autouse=True)
def cleanup(emulator_client: Any, run_id: str) -> Generator[None, None, None]:
    """Delete all test-owned org + account docs after each test."""
    yield
    _delete_doc(emulator_client, "organizations", f"org_ac6_{run_id}")
    for aid in [f"acc_alpha_{run_id}", f"acc_beta_{run_id}"]:
        _delete_doc(emulator_client, "accounts", aid)


# ---------------------------------------------------------------------------
# Snapshot helper
# ---------------------------------------------------------------------------


def _capture_snapshot(
    test_client: TestClient,
    account_ids: list[str],
    big_bet_names: list[str],
    org_funnel_steps: list[int],
    big_bet_steps: list[int],
    channel_names: list[str],
) -> dict[str, Any]:
    """Call every KPI/funnel/channel/tactic GET endpoint and record responses.

    Returns a dict keyed by a stable endpoint-descriptor string, value is the
    JSON-decoded response body. Non-200 responses are recorded as
    {"_status": <code>} so failures are visible in the diff.
    """
    snapshot: dict[str, Any] = {}

    for aid in account_ids:
        prefix = "/api/v1/firestore"

        # --- KPI endpoints ---
        resp = test_client.get(f"{prefix}/kpi-settings/{aid}")
        snapshot[f"GET kpi-settings/{aid}"] = (
            resp.json() if resp.status_code == 200 else {"_status": resp.status_code}
        )

        for kpi in KPI_NAMES:
            resp = test_client.get(f"{prefix}/kpi-settings/{aid}/{kpi}")
            snapshot[f"GET kpi-settings/{aid}/{kpi}"] = (
                resp.json()
                if resp.status_code == 200
                else {"_status": resp.status_code}
            )

        # --- Organization funnel step list ---
        resp = test_client.get(f"{prefix}/funnel-steps/{aid}/organization")
        snapshot[f"GET funnel-steps/{aid}/organization"] = (
            resp.json() if resp.status_code == 200 else {"_status": resp.status_code}
        )

        # --- Organization funnel individual steps ---
        for step in org_funnel_steps:
            resp = test_client.get(f"{prefix}/funnel-steps/{aid}/organization/{step}")
            snapshot[f"GET funnel-steps/{aid}/organization/{step}"] = (
                resp.json()
                if resp.status_code == 200
                else {"_status": resp.status_code}
            )

        # --- Big-bet funnel step lists (one per big bet) ---
        for bb in big_bet_names:
            resp = test_client.get(
                f"{prefix}/funnel-steps/{aid}/big_bet",
                params={"big_bet_name": bb},
            )
            snapshot[f"GET funnel-steps/{aid}/big_bet?big_bet_name={bb}"] = (
                resp.json()
                if resp.status_code == 200
                else {"_status": resp.status_code}
            )

        # --- Big-bet funnel individual steps ---
        for bb in big_bet_names:
            for step in big_bet_steps:
                resp = test_client.get(
                    f"{prefix}/funnel-steps/{aid}/big_bet/{step}",
                    params={"big_bet_name": bb},
                )
                snapshot[f"GET funnel-steps/{aid}/big_bet/{step}?big_bet_name={bb}"] = (
                    resp.json()
                    if resp.status_code == 200
                    else {"_status": resp.status_code}
                )

        # --- Channel lists: org funnel steps ---
        for step in org_funnel_steps:
            resp = test_client.get(
                f"{prefix}/channels",
                params={
                    "account_id": aid,
                    "funnel_type": "organization",
                    "funnel_step_num": step,
                },
            )
            snapshot[f"GET channels/{aid}/organization/{step}"] = (
                resp.json()
                if resp.status_code == 200
                else {"_status": resp.status_code}
            )

        # --- Tactic lists: org funnel steps x channels ---
        for step in org_funnel_steps:
            for ch in channel_names:
                resp = test_client.get(
                    f"{prefix}/tactics",
                    params={
                        "account_id": aid,
                        "funnel_type": "organization",
                        "funnel_step_num": step,
                        "channel_name": ch,
                    },
                )
                snapshot[f"GET tactics/{aid}/organization/{step}/{ch}"] = (
                    resp.json()
                    if resp.status_code == 200
                    else {"_status": resp.status_code}
                )

    return snapshot


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_endpoint_responses_unchanged_by_migration(
    emulator_client: Any, run_id: str
) -> None:
    """AC-6: KPI/funnel endpoints return the same data before and after the Shape D split.

    Steps:
    1. Seed Shape D org doc (nested accounts map) and Shape B accounts/{aid} docs.
    2. Capture pre-migration endpoint snapshot.
    3. Run run_migration(emulator_client, dry_run=False) — should skip both accounts
       because the Shape B docs already match the Shape D payload.
    4. Delete the org doc's 'accounts' map field (inline destructive step, simulating
       DM-44's --confirm-delete-field).
    5. Capture post-migration endpoint snapshot.
    6. Assert pre == post (full JSON equality).
    7. Assert PRD §7 structural invariants.
    """
    from google.cloud import firestore as fs  # type: ignore[import]
    from migrate_shape_d_split import run_migration
    from src.kene_api.firestore import FirestoreService, get_firestore_service
    from src.kene_api.main import app

    org_id = f"org_ac6_{run_id}"
    aid_alpha = f"acc_alpha_{run_id}"
    aid_beta = f"acc_beta_{run_id}"
    account_ids = [aid_alpha, aid_beta]

    # 1. Seed both shapes
    account_payloads = _seed_shape_d_and_b(emulator_client, org_id, account_ids)

    # Build an emulator-backed FirestoreService
    emulator_service = FirestoreService()
    emulator_service._db = emulator_client
    emulator_service._initialized = True

    _prior_override = app.dependency_overrides.get(get_firestore_service)
    app.dependency_overrides[get_firestore_service] = lambda: emulator_service
    test_client = TestClient(app)
    try:
        # 2. Pre-migration snapshot
        pre = _capture_snapshot(
            test_client,
            account_ids,
            BIG_BET_NAMES,
            ORG_FUNNEL_STEPS,
            BIG_BET_STEPS,
            CHANNEL_NAMES,
        )

        # Sanity: snapshot must be non-empty and every response must be 200
        assert len(pre) >= 30, (
            f"Expected ≥ 30 endpoint entries in snapshot, got {len(pre)}"
        )
        non_200 = {
            k: v for k, v in pre.items() if isinstance(v, dict) and "_status" in v
        }
        assert not non_200, f"Non-200 responses in pre-migration snapshot: {non_200}"

        # 3. Run migration — both accounts should be SKIPPED (Shape B already populated)
        summary = run_migration(emulator_client, dry_run=False)
        assert summary.errors == 0, f"Migration errors: {summary.errors}"
        assert summary.skipped == 2, (
            f"Expected 2 skipped (Shape B already present); got copied={summary.copied} "
            f"skipped={summary.skipped}"
        )
        assert summary.copied == 0, f"Expected 0 copied; got {summary.copied}"

        # 4. Inline destructive step: remove the org doc's 'accounts' field
        # (simulates DM-44's --confirm-delete-field; swap for the flag once DM-44 ships)
        org_ref = emulator_client.collection("organizations").document(org_id)
        org_ref.update({"accounts": fs.DELETE_FIELD})

        # 5. Post-migration snapshot
        post = _capture_snapshot(
            test_client,
            account_ids,
            BIG_BET_NAMES,
            ORG_FUNNEL_STEPS,
            BIG_BET_STEPS,
            CHANNEL_NAMES,
        )

        # 6. AC-6 assertion: endpoint responses must be identical before and after
        if pre != post:
            pre_json = json.dumps(pre, sort_keys=True, indent=2, default=str)
            post_json = json.dumps(post, sort_keys=True, indent=2, default=str)
            diverging = [k for k in pre if pre.get(k) != post.get(k)]
            raise AssertionError(
                f"pre != post: {len(diverging)} endpoint(s) differ: {diverging}\n"
                f"--- pre ---\n{pre_json}\n--- post ---\n{post_json}"
            )

        # 7. PRD §7 structural assertions
        org_doc_after = _get_doc(emulator_client, "organizations", org_id)
        assert org_doc_after is not None, (
            "organizations/{org_id} doc missing after migration"
        )
        assert "accounts" not in org_doc_after, (
            f"organizations/{org_id} still has 'accounts' field after destructive step: "
            f"{list(org_doc_after.keys())}"
        )

        for aid in account_ids:
            acc_doc = _get_doc(emulator_client, "accounts", aid)
            assert acc_doc is not None, f"accounts/{aid} doc missing"

            # organization_id back-reference
            assert acc_doc.get("organization_id") == org_id, (
                f"accounts/{aid}.organization_id mismatch: {acc_doc.get('organization_id')!r}"
            )

            # funnels and account_settings match the seeded payload
            # (exclude migration timestamps that were set at seed time)
            expected_payload = account_payloads[aid]
            assert acc_doc.get("funnels") == expected_payload["funnels"], (
                f"accounts/{aid}.funnels mismatch"
            )
            assert (
                acc_doc.get("account_settings") == expected_payload["account_settings"]
            ), f"accounts/{aid}.account_settings mismatch"

            # shape_d_migrated_at is present and parses as ISO-8601
            migrated_at = acc_doc.get("shape_d_migrated_at")
            assert migrated_at is not None, (
                f"accounts/{aid} missing shape_d_migrated_at"
            )
            datetime.fromisoformat(migrated_at)  # raises if not valid ISO-8601

    finally:
        if _prior_override is None:
            app.dependency_overrides.pop(get_firestore_service, None)
        else:
            app.dependency_overrides[get_firestore_service] = _prior_override


@pytest.mark.integration
def test_dry_run_destructive_step_is_a_noop(emulator_client: Any, run_id: str) -> None:
    """dry_run=True leaves both shapes intact: org doc keeps 'accounts' field,
    accounts/{aid} docs are unchanged.
    """
    from migrate_shape_d_split import run_migration

    org_id = f"org_ac6_{run_id}"
    aid_alpha = f"acc_alpha_{run_id}"
    aid_beta = f"acc_beta_{run_id}"
    account_ids = [aid_alpha, aid_beta]

    _seed_shape_d_and_b(emulator_client, org_id, account_ids)

    # Capture Shape B state before dry-run
    alpha_before = _get_doc(emulator_client, "accounts", aid_alpha)
    beta_before = _get_doc(emulator_client, "accounts", aid_beta)

    summary = run_migration(emulator_client, dry_run=True)

    # Dry-run: no writes occur. The idempotency gate checks equality of
    # organization_id + account_settings + funnels against the destination doc —
    # since both are already present and identical, both accounts are SKIPPED.
    assert summary.errors == 0, f"Unexpected errors in dry-run: {summary.errors}"
    assert summary.skipped == 2, (
        f"Expected 2 skipped; got copied={summary.copied} skipped={summary.skipped}"
    )
    assert summary.copied == 0, f"Expected 0 copied; got {summary.copied}"

    # Org doc still has 'accounts' field (no destructive step ran)
    org_doc_after = _get_doc(emulator_client, "organizations", org_id)
    assert org_doc_after is not None
    assert "accounts" in org_doc_after, (
        "org doc's 'accounts' field was removed during dry-run — should be a no-op"
    )

    # accounts/{aid} docs are unchanged
    alpha_after = _get_doc(emulator_client, "accounts", aid_alpha)
    beta_after = _get_doc(emulator_client, "accounts", aid_beta)

    assert alpha_after == alpha_before, (
        f"accounts/{aid_alpha} was modified during dry-run"
    )
    assert beta_after == beta_before, f"accounts/{aid_beta} was modified during dry-run"
