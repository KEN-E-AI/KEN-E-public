"""Integration tests: Firestore security rules for CH-PRD-01 collections (CH-9 AC-3).

Covers PRD §7 acceptance criteria AC-3 — six assertions, two ALLOW / four DENY:

  (a) user reads own session  → ALLOWED
  (b) user reads other's session  → PERMISSION_DENIED
  (c) client writes to chat_sessions  → PERMISSION_DENIED (allow write: if false)
  (d) client writes to artifacts subcollection  → PERMISSION_DENIED (allow write: if false)
  (e) user reads own chat_category  → ALLOWED
  (f) user reads another user's chat_category  → PERMISSION_DENIED

chat_sessions and its artifacts subcollection are server-write-only: all writes
go through server-side services using the Admin SDK, which bypasses rules.

Auth simulation: The Firestore emulator parses JWT claims without verifying the
signature. We craft minimal RS256-header JWTs with the desired uid claim.
Seeding and cleanup use `Authorization: Bearer owner` which the emulator
treats as admin (bypasses rules).

Enable with:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/chat/test_firestore_security_rules.py -v
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import requests

# ---------------------------------------------------------------------------
# Skip gate — identical pattern to other emulator tests in this package.
# ---------------------------------------------------------------------------

EMULATOR_HOST = os.getenv("FIRESTORE_EMULATOR_HOST", "")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "test-project")

pytestmark = pytest.mark.skipif(
    not EMULATOR_HOST,
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID=test-project) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)

# Path to deployment/firestore.rules — the file terraform (firestore_rules.tf)
# deploys as the live ruleset; the emulator test loads the same file.
# api/tests/integration/chat/ → api/tests/integration/ → api/tests/ → api/ → repo root
RULES_FILE = Path(__file__).parents[4] / "deployment" / "firestore.rules"

# ---------------------------------------------------------------------------
# REST helpers — thin wrappers around the Firestore emulator HTTP API.
# ---------------------------------------------------------------------------


def _base() -> str:
    host = EMULATOR_HOST if EMULATOR_HOST.startswith("http") else f"http://{EMULATOR_HOST}"
    return f"{host}/v1/projects/{PROJECT_ID}/databases/(default)/documents"


def _fake_jwt(uid: str, extra_claims: dict[str, Any] | None = None) -> str:
    """Craft an unsigned JWT the Firestore emulator accepts for rules evaluation.

    The emulator decodes the payload to populate request.auth without verifying
    the RS256 signature.  This mirrors the approach used by @firebase/rules-unit-testing.
    """
    hdr = base64.urlsafe_b64encode(
        json.dumps({"alg": "RS256", "kid": "fake"}).encode()
    ).rstrip(b"=").decode()

    claims: dict[str, Any] = {
        "iss": f"https://securetoken.google.com/{PROJECT_ID}",
        "aud": PROJECT_ID,
        "sub": uid,
        "uid": uid,
        **(extra_claims or {}),
    }
    pld = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(b"fake-sig").rstrip(b"=").decode()
    return f"{hdr}.{pld}.{sig}"


def _get(path: str, uid: str, extra_claims: dict[str, Any] | None = None) -> requests.Response:
    return requests.get(
        f"{_base()}/{path}",
        headers={"Authorization": f"Bearer {_fake_jwt(uid, extra_claims)}"},
        timeout=10,
    )


def _patch(
    path: str,
    uid: str,
    fields: dict[str, str],
    extra_claims: dict[str, Any] | None = None,
) -> requests.Response:
    body = {"fields": {k: {"stringValue": v} for k, v in fields.items()}}
    return requests.patch(
        f"{_base()}/{path}",
        headers={
            "Authorization": f"Bearer {_fake_jwt(uid, extra_claims)}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=10,
    )


def _admin_patch(path: str, fields: dict[str, str]) -> None:
    """Write a document bypassing rules (Bearer owner = emulator admin)."""
    body = {"fields": {k: {"stringValue": v} for k, v in fields.items()}}
    resp = requests.patch(
        f"{_base()}/{path}",
        headers={"Authorization": "Bearer owner", "Content-Type": "application/json"},
        json=body,
        timeout=10,
    )
    resp.raise_for_status()


def _admin_delete(path: str) -> None:
    resp = requests.delete(
        f"{_base()}/{path}",
        headers={"Authorization": "Bearer owner"},
        timeout=10,
    )
    if resp.status_code not in (200, 404):
        resp.raise_for_status()


def _upload_rules() -> None:
    """Push firestore.rules to the emulator for the current test run."""
    host = EMULATOR_HOST if EMULATOR_HOST.startswith("http") else f"http://{EMULATOR_HOST}"
    content = RULES_FILE.read_text()
    resp = requests.put(
        f"{host}/emulator/v1/projects/{PROJECT_ID}:securityRules",
        json={"rules": {"files": [{"name": "firestore.rules", "content": content}]}},
        timeout=10,
    )
    resp.raise_for_status()


# ---------------------------------------------------------------------------
# Module-scoped fixture: upload rules + seed + teardown.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ctx() -> Generator[dict[str, str], None, None]:
    """Upload rules, seed documents, yield context ids, delete on exit."""
    _upload_rules()

    rid = uuid.uuid4().hex[:8]
    acc = f"acc_{rid}"
    ua = f"ua_{rid}"  # user A
    ub = f"ub_{rid}"  # user B
    sess_a = f"sess_a_{rid}"  # session owned by user A
    sess_b = f"sess_b_{rid}"  # session owned by user B
    cat_a = f"cat_a_{rid}"  # category belonging to user A

    _admin_patch(
        f"accounts/{acc}/chat_sessions/{sess_a}",
        {"user_id": ua, "account_id": acc},
    )
    _admin_patch(
        f"accounts/{acc}/chat_sessions/{sess_b}",
        {"user_id": ub, "account_id": acc},
    )
    _admin_patch(
        f"users/{ua}/chat_categories/{cat_a}",
        {"name": "Research", "user_id": ua},
    )

    yield {
        "acc": acc,
        "ua": ua,
        "ub": ub,
        "sess_a": sess_a,
        "sess_b": sess_b,
        "cat_a": cat_a,
        "rid": rid,
    }

    _admin_delete(f"accounts/{acc}/chat_sessions/{sess_a}")
    _admin_delete(f"accounts/{acc}/chat_sessions/{sess_b}")
    _admin_delete(f"users/{ua}/chat_categories/{cat_a}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestChatSessionRules:
    def test_read_own_session_allowed(self, ctx: dict[str, str]) -> None:
        resp = _get(
            f"accounts/{ctx['acc']}/chat_sessions/{ctx['sess_a']}",
            uid=ctx["ua"],
            extra_claims={"account_id": ctx["acc"]},
        )
        assert resp.status_code == 200, f"Expected 200 (own session read), got {resp.status_code}: {resp.text}"

    def test_read_other_session_denied(self, ctx: dict[str, str]) -> None:
        resp = _get(
            f"accounts/{ctx['acc']}/chat_sessions/{ctx['sess_b']}",
            uid=ctx["ua"],
            extra_claims={"account_id": ctx["acc"]},
        )
        assert resp.status_code == 403, f"Expected 403 (other's session), got {resp.status_code}: {resp.text}"

    def test_client_write_session_denied(self, ctx: dict[str, str]) -> None:
        """chat_sessions is server-write-only (allow write: if false).

        ChatSessionSideTableService is the single write path; it uses the
        Admin SDK, which bypasses rules. A direct client write — even by the
        owning user writing their own row — must be denied.
        """
        resp = _patch(
            f"accounts/{ctx['acc']}/chat_sessions/new_{ctx['rid']}",
            uid=ctx["ua"],
            fields={"user_id": ctx["ua"], "account_id": ctx["acc"]},
            extra_claims={"account_id": ctx["acc"]},
        )
        assert resp.status_code == 403, (
            f"Expected 403 (chat_sessions allow write: if false), got {resp.status_code}: {resp.text}"
        )

    def test_client_write_artifacts_denied(self, ctx: dict[str, str]) -> None:
        resp = _patch(
            f"accounts/{ctx['acc']}/chat_sessions/{ctx['sess_a']}/artifacts/art_{ctx['rid']}",
            uid=ctx["ua"],
            fields={"filename": "test.pdf"},
            extra_claims={"account_id": ctx["acc"]},
        )
        assert resp.status_code == 403, (
            f"Expected 403 (artifacts allow write: if false), got {resp.status_code}: {resp.text}"
        )


class TestChatCategoryRules:
    def test_read_own_category_allowed(self, ctx: dict[str, str]) -> None:
        resp = _get(
            f"users/{ctx['ua']}/chat_categories/{ctx['cat_a']}",
            uid=ctx["ua"],
        )
        assert resp.status_code == 200, f"Expected 200 (own category read), got {resp.status_code}: {resp.text}"

    def test_read_other_category_denied(self, ctx: dict[str, str]) -> None:
        resp = _get(
            f"users/{ctx['ub']}/chat_categories/any_{ctx['rid']}",
            uid=ctx["ua"],
        )
        assert resp.status_code == 403, (
            f"Expected 403 (other user's category), got {resp.status_code}: {resp.text}"
        )
