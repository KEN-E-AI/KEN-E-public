"""Pure-logic unit tests for ``_create_account_from_record``.

The super-admin ``GET /api/v1/accounts/`` path runs ``MATCH (acc:Account) RETURN
acc`` over *every* node and maps each through this helper with no per-node
isolation. A node missing the model-required strings (``account_name`` /
``organization_id`` / ``industry`` / ``status`` / ``timezone``) must NOT raise —
otherwise one malformed node 500s the entire account list. (Regression sibling of
the org-list fix: the chat load-test seed's ``acc_load_test`` node set only
``account_id``/``account_name``; see ``api/scripts/seed_chat_load_test_data.py``.)

These exercise the helper directly with plain dicts, so no emulator/DB is needed.
"""

from __future__ import annotations

from src.kene_api.routers.accounts import _create_account_from_record


def test_well_formed_record_maps_through() -> None:
    acc = _create_account_from_record(
        {
            "account_id": "acc-1",
            "account_name": "Acme",
            "organization_id": "org-1",
            "industry": "Retail",
            "status": "Active",
            "websites": ["https://acme.example"],
            "timezone": "UTC",
        }
    )

    assert (
        acc.account_id,
        acc.account_name,
        acc.organization_id,
        acc.industry,
        acc.status,
        acc.websites,
        acc.timezone,
    ) == ("acc-1", "Acme", "org-1", "Retail", "Active", ["https://acme.example"], "UTC")


def test_malformed_node_missing_required_strings_coerces_to_empty() -> None:
    """A node with only account_id/account_name (the load-test fixture shape)
    must not raise — organization_id/industry/status/timezone coerce to ""."""
    acc = _create_account_from_record(
        {"account_id": "acc_load_test", "account_name": "Load Test Account"}
    )

    assert (
        acc.account_id,
        acc.account_name,
        acc.organization_id,
        acc.industry,
        acc.status,
        acc.websites,
        acc.timezone,
    ) == ("acc_load_test", "Load Test Account", "", "", "", [], "")


def test_explicit_null_required_strings_coerce_to_empty() -> None:
    """Neo4j can return explicit None for an unset string property."""
    acc = _create_account_from_record(
        {
            "account_id": "acc-x",
            "account_name": None,
            "organization_id": None,
            "industry": None,
            "status": None,
            "timezone": None,
        }
    )

    assert (
        acc.account_name,
        acc.organization_id,
        acc.industry,
        acc.status,
        acc.timezone,
    ) == ("", "", "", "", "")
