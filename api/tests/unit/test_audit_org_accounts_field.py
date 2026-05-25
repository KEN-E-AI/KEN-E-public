"""Unit tests for api/scripts/audit_org_accounts_field.py — audit-record parser.

Pure-logic tests (no Firestore dependency).  Covers the three production doc
shapes seen in staging during DM-61 check #8:

  Shape 1 — list of string account IDs  (equity-trust: [a000002])
  Shape 2 — list with multiple string IDs (healthway: [a000001, test-account-1])
  Shape 3 — list of account-object dicts  (defensive: if a doc carries full
             account objects rather than bare IDs, the parser must not crash)
"""

import sys
from pathlib import Path

# Ensure the scripts directory is on the path so the import works without
# installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from audit_org_accounts_field import build_org_audit_record


class TestBuildOrgAuditRecord:
    def test_list_with_one_string_id(self) -> None:
        """Shape 1 — list with a single string account ID (equity-trust)."""
        doc = {"name": "equity-trust", "accounts": ["a000002"]}
        record = build_org_audit_record("equity-trust", doc)

        assert record.org_id == "equity-trust"
        assert record.has_accounts_field is True
        assert record.field_type == "list"
        assert record.account_ids == ["a000002"]
        assert record.item_count == 1
        assert record.action == "found"
        assert record.error is None

    def test_list_with_multiple_string_ids(self) -> None:
        """Shape 2 — list with two string IDs (healthway)."""
        doc = {"accounts": ["a000001", "test-account-1"]}
        record = build_org_audit_record("healthway", doc)

        assert record.org_id == "healthway"
        assert record.has_accounts_field is True
        assert record.field_type == "list"
        assert record.account_ids == ["a000001", "test-account-1"]
        assert record.item_count == 2
        assert record.action == "found"

    def test_list_of_account_object_dicts(self) -> None:
        """Shape 3 — list of account-object dicts: parser must not crash.

        The ``account_ids`` list is empty (we can't reliably extract an ID from
        an arbitrary object dict), but ``item_count`` reflects the list length
        and ``field_type`` is "list".
        """
        doc = {
            "accounts": [
                {"account_id": "acc_abc", "name": "Acme"},
                {"account_id": "acc_def", "name": "Widgets"},
            ]
        }
        record = build_org_audit_record("open-lines", doc)

        assert record.org_id == "open-lines"
        assert record.has_accounts_field is True
        assert record.field_type == "list"
        assert record.account_ids == []  # dict items: IDs not extracted
        assert record.item_count == 2
        assert record.action == "found"
        assert record.error is None

    def test_no_accounts_field(self) -> None:
        """Org doc with no accounts field → clean record."""
        doc = {"name": "dev-org", "created_at": "2026-01-01"}
        record = build_org_audit_record("dev-org", doc)

        assert record.has_accounts_field is False
        assert record.field_type is None
        assert record.account_ids == []
        assert record.item_count == 0
        assert record.action == "clean"

    def test_dict_accounts_field(self) -> None:
        """Shape D map shape — dict keyed by account IDs."""
        doc = {"accounts": {"acc_abc": {"funnels": {}}, "acc_def": {}}}
        record = build_org_audit_record("org-with-shape-d-map", doc)

        assert record.has_accounts_field is True
        assert record.field_type == "dict"
        assert set(record.account_ids) == {"acc_abc", "acc_def"}
        assert record.item_count == 2
        assert record.action == "found"


# ---------------------------------------------------------------------------
# Delete-pass safety — only the dead list shape is auto-deletable
# ---------------------------------------------------------------------------


class _FakeDocRef:
    def __init__(self, org_id: str, updates_log: list) -> None:
        self._org_id = org_id
        self._updates_log = updates_log

    def update(self, fields: dict) -> None:
        self._updates_log.append((self._org_id, fields))


class _FakeCollection:
    def __init__(self, docs: dict, updates_log: list) -> None:
        self._docs = docs
        self._updates_log = updates_log

    def stream(self):
        for org_id, data in self._docs.items():
            snap = type(
                "_Snap",
                (),
                {"id": org_id, "to_dict": (lambda self, d=data: d)},
            )()
            yield snap

    def document(self, org_id: str) -> _FakeDocRef:
        return _FakeDocRef(org_id, self._updates_log)


class _FakeClient:
    """Minimal stand-in for google.cloud.firestore.Client used by run_audit."""

    def __init__(self, docs: dict) -> None:
        self._docs = docs
        self.updates_log: list = []

    def collection(self, name: str) -> _FakeCollection:
        assert name == "organizations"
        return _FakeCollection(self._docs, self.updates_log)


class TestDeletePassShapeSafety:
    def test_delete_pass_removes_list_but_refuses_dict(self) -> None:
        """Delete-pass deletes the dead list residue but never a Shape-D dict map.

        A dict-shaped accounts field may be live account data that the split
        migration didn't move off the org doc; the destructive pass must refuse
        it (recorded as an error) rather than wipe it.
        """
        from audit_org_accounts_field import run_audit

        client = _FakeClient(
            {
                "org-list": {"accounts": ["a000002"]},  # dead residue → deletable
                "org-dict": {
                    "accounts": {"acc_abc": {"funnels": {}}}
                },  # live map → refuse
                "org-clean": {"name": "no-accounts-field"},
            }
        )

        summary = run_audit(client, dry_run=False, confirm_delete=True)

        # Only the list org's field was deleted; the dict org was left untouched.
        assert [org for org, _fields in client.updates_log] == ["org-list"]
        assert summary.orgs_deleted == 1
        assert summary.orgs_errors == 1  # the refused dict counts as an error
        assert summary.pass_fail == "FAIL"  # refusal forces a non-zero exit

    def test_dry_run_refuses_dict_without_writing(self) -> None:
        """Even in dry-run, a dict field is refused and no write is attempted."""
        from audit_org_accounts_field import run_audit

        client = _FakeClient(
            {"org-dict": {"accounts": {"acc_abc": {}}}},
        )

        summary = run_audit(client, dry_run=True, confirm_delete=True)

        assert client.updates_log == []  # dry-run never writes
        assert summary.orgs_errors == 1
        assert summary.pass_fail == "FAIL"
