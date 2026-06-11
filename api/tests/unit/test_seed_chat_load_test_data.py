"""Unit tests for the chat-sidebar load-test seed's Neo4j owning-org helpers.

The seed creates the Neo4j ``(:Account)-[:BELONGS_TO]->(:Organization)`` edge
that ``require_account_access_for`` (IN-2) resolves; without it the sidebar load
test 404s every request. These tests pin two things that manual/dry-run checks
missed when the script was first written:

- The dry-run path logs and returns WITHOUT importing ``neo4j`` — documenting the
  dry-run/real-run divergence (dry-run can't prove the real import resolves, so
  the real ``uv run`` env must be checked separately; see deployment/cd/staging.yaml).
- ``_neo4j_connection_params`` fails loudly on a missing URI or an unresolved
  (empty) password rather than attempting a doomed connection.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# The seed lives in api/scripts/, not an importable package — add it to the path.
_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import seed_chat_load_test_data as seed  # noqa: E402


def test_dry_run_does_not_import_neo4j(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dry-run must log-and-return before the (real-run-only) neo4j import.

    Poison ``import neo4j`` so any attempt raises; the dry-run early-out must
    return cleanly regardless.
    """
    monkeypatch.setitem(sys.modules, "neo4j", None)
    # Must not raise — dry-run returns before `from neo4j import GraphDatabase`.
    assert seed._seed_neo4j_owning_org(dry_run=True) is None


def test_connection_params_raises_on_missing_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NEO4J_URI", raising=False)
    with pytest.raises(RuntimeError, match="NEO4J_URI is not set"):
        seed._neo4j_connection_params()


def test_connection_params_raises_on_empty_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A set URI but unresolved password fails loudly (secretAccessor-gap guard)."""
    monkeypatch.setenv("NEO4J_URI", "neo4j+s://example.test")
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="NEO4J_PASSWORD did not resolve"):
        seed._neo4j_connection_params()


def test_connection_params_returns_resolved_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEO4J_URI", "neo4j+s://example.test")
    monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "raw-secret-value")
    monkeypatch.setenv("NEO4J_DATABASE", "neo4j")
    assert seed._neo4j_connection_params() == (
        "neo4j+s://example.test",
        "neo4j",
        "raw-secret-value",
        "neo4j",
    )


def test_cleanup_is_noop_without_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cleanup with no NEO4J_URI is a safe no-op returning (0, 0)."""
    monkeypatch.delenv("NEO4J_URI", raising=False)
    assert seed._cleanup_neo4j_owning_org() == (0, 0)
