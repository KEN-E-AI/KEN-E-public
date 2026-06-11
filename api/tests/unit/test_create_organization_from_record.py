"""Pure-logic unit tests for ``_create_organization_from_record``.

The super-admin ``GET /api/v1/organizations/`` path fetches *every*
``:Organization`` node and maps each through this helper. A single node missing
the model-required strings (``organization_name`` / ``plan`` / ``website``) must
NOT raise — otherwise one malformed node 500s the entire org list and breaks the
org selector for super-admins. (Regression: the chat load-test seed created an
``org_load_test`` node with only ``name``/``organization_id`` set, see
``api/scripts/seed_chat_load_test_data.py``.)

These exercise the helper directly with plain dicts, so no emulator/DB is needed.
"""

from __future__ import annotations

from src.kene_api.routers.organizations import _create_organization_from_record


def test_well_formed_record_maps_through() -> None:
    org = _create_organization_from_record(
        {
            "organization_id": "org-1",
            "organization_name": "Company A",
            "plan": "Professional",
            "website": "https://companya.com",
            "company_size": "medium",
            "agency": False,
            "child_organizations": ["org-2"],
        }
    )

    assert (
        org.organization_id,
        org.organization_name,
        org.plan,
        org.website,
        org.agency,
        org.child_organizations,
    ) == (
        "org-1",
        "Company A",
        "Professional",
        "https://companya.com",
        False,
        ["org-2"],
    )


def test_malformed_node_missing_required_strings_coerces_to_empty() -> None:
    """A node with only organization_id (the load-test fixture shape) must not raise."""
    org = _create_organization_from_record({"organization_id": "org_load_test"})

    assert (org.organization_id, org.organization_name, org.plan, org.website) == (
        "org_load_test",
        "",
        "",
        "",
    )


def test_explicit_null_required_strings_coerce_to_empty() -> None:
    """Neo4j can return explicit None for an unset string property."""
    org = _create_organization_from_record(
        {
            "organization_id": "org-x",
            "organization_name": None,
            "plan": None,
            "website": None,
            "agency": True,
        }
    )

    assert (org.organization_name, org.plan, org.website, org.agency) == (
        "",
        "",
        "",
        True,
    )
