"""Unit tests for api/scripts/flatten_agent_config_storage.py (AH-40).

Pure-logic tests for ``flatten_doc`` (the idempotent transform) and an
integration-style test for ``migrate`` against a fake Firestore that
supports both ``.collection()`` (globals) and ``.collection_group()``
(per-account overlays + custom agents).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from google.cloud.firestore_v1 import DELETE_FIELD

from api.scripts.flatten_agent_config_storage import (
    flatten_doc,
    migrate,
)

# ---------------------------------------------------------------------------
# Fake Firestore stand-in
# ---------------------------------------------------------------------------


class _FakeRef:
    """Stand-in for ``DocumentSnapshot.reference``.

    Holds a ``path`` for the collection-group filter to inspect and an
    ``update`` method that writes back into the originating snapshot's
    data so a second ``migrate`` call (idempotency test) sees the
    updated state.
    """

    def __init__(self, path: str, snapshot: _FakeSnapshot) -> None:
        self.path = path
        self._snapshot = snapshot
        self.update = MagicMock(side_effect=self._apply_update)

    def _apply_update(self, patch: dict[str, Any]) -> None:
        for key, value in patch.items():
            if value is DELETE_FIELD:
                self._snapshot._data.pop(key, None)
            else:
                self._snapshot._data[key] = value


class _FakeSnapshot:
    def __init__(self, doc_id: str, path: str, data: dict[str, Any]) -> None:
        self.id = doc_id
        self._data = data
        self.reference = _FakeRef(path, self)

    def to_dict(self) -> dict[str, Any]:
        return self._data


class _FakeCollection:
    def __init__(self, snapshots: list[_FakeSnapshot]) -> None:
        self._snapshots = snapshots

    def stream(self) -> list[_FakeSnapshot]:
        return list(self._snapshots)


class FakeFlattenDb:
    """Fake Firestore supporting ``.collection()`` + ``.collection_group()``.

    ``globals``: list of (doc_id, data) for ``agent_configs/{id}``.
    ``overlays``: list of (account_id, doc_id, data) for
    ``accounts/{account_id}/agent_configs/{id}``.

    ``collection_group("agent_configs").stream()`` returns *all* docs in
    any subcollection of that name — both globals and overlays — matching
    Firestore semantics. The migrate function de-duplicates globals via
    path-segment count.
    """

    def __init__(
        self,
        globals_: list[tuple[str, dict[str, Any]]] | None = None,
        overlays: list[tuple[str, str, dict[str, Any]]] | None = None,
    ) -> None:
        self.globals: list[_FakeSnapshot] = [
            _FakeSnapshot(doc_id, f"agent_configs/{doc_id}", data)
            for doc_id, data in (globals_ or [])
        ]
        self.overlays: list[_FakeSnapshot] = [
            _FakeSnapshot(
                doc_id,
                f"accounts/{account_id}/agent_configs/{doc_id}",
                data,
            )
            for account_id, doc_id, data in (overlays or [])
        ]

    def collection(self, name: str) -> _FakeCollection:
        assert name == "agent_configs"
        return _FakeCollection(self.globals)

    def collection_group(self, name: str) -> _FakeCollection:
        assert name == "agent_configs"
        return _FakeCollection(self.globals + self.overlays)


# ---------------------------------------------------------------------------
# Tests: flatten_doc pure helper
# ---------------------------------------------------------------------------


class TestFlattenDocHelper:
    def test_doc_without_gen_cfg_returns_empty_update(self) -> None:
        """No ``generate_content_config`` → no-op (idempotent)."""
        update = flatten_doc(
            {"name": "x", "model": "gemini-2.5-pro", "temperature": 0.5}
        )

        assert update == {}

    def test_nested_only_hoists_both_fields_and_deletes_wrapper(self) -> None:
        update = flatten_doc(
            {
                "name": "x",
                "model": "gemini-2.5-pro",
                "generate_content_config": {
                    "temperature": 0.7,
                    "max_output_tokens": 4096,
                },
            }
        )

        assert update == {
            "temperature": 0.7,
            "max_output_tokens": 4096,
            "generate_content_config": DELETE_FIELD,
        }

    def test_nested_only_with_just_temperature(self) -> None:
        update = flatten_doc(
            {
                "model": "gemini-2.5-pro",
                "generate_content_config": {"temperature": 0.3},
            }
        )

        assert update == {
            "temperature": 0.3,
            "generate_content_config": DELETE_FIELD,
        }

    def test_flat_present_does_not_overwrite_from_nested(self) -> None:
        """Overlay-precedence preservation: if the flat field is already set,
        the nested value is ignored (still deletes the wrapper)."""
        update = flatten_doc(
            {
                "model": "gemini-2.5-pro",
                "temperature": 0.9,
                "max_output_tokens": 8192,
                "generate_content_config": {
                    "temperature": 0.1,
                    "max_output_tokens": 500,
                },
            }
        )

        assert update == {"generate_content_config": DELETE_FIELD}

    def test_hybrid_doc_hoists_only_missing_flat_field(self) -> None:
        """Flat ``temperature`` present + only nested ``max_output_tokens``
        → hoist max_output_tokens; leave temperature alone."""
        update = flatten_doc(
            {
                "model": "gemini-2.5-pro",
                "temperature": 0.9,
                "generate_content_config": {"max_output_tokens": 4096},
            }
        )

        assert update == {
            "max_output_tokens": 4096,
            "generate_content_config": DELETE_FIELD,
        }

    def test_non_dict_gen_cfg_just_deletes_wrapper(self) -> None:
        """Corrupt nested value (not a dict): delete the wrapper, hoist nothing."""
        update = flatten_doc(
            {
                "model": "gemini-2.5-pro",
                "generate_content_config": "garbage",
            }
        )

        assert update == {"generate_content_config": DELETE_FIELD}

    def test_empty_gen_cfg_dict_just_deletes_wrapper(self) -> None:
        update = flatten_doc(
            {
                "model": "gemini-2.5-pro",
                "generate_content_config": {},
            }
        )

        # Empty dict is falsy → treated as absent → no-op.
        assert update == {}


# ---------------------------------------------------------------------------
# Tests: migrate end-to-end
# ---------------------------------------------------------------------------


class TestMigrate:
    def test_flattens_global_doc_with_nested_block(self) -> None:
        db = FakeFlattenDb(
            globals_=[
                (
                    "ken_e_chatbot",
                    {
                        "model": "gemini-2.5-pro",
                        "generate_content_config": {
                            "temperature": 0.7,
                            "max_output_tokens": 4096,
                        },
                    },
                )
            ]
        )

        counts = migrate(project_id="test-project", dry_run=False, db=db)

        assert counts["flattened"] == 1
        assert counts["unchanged"] == 0
        # Post-migration the doc has flat fields and no nested wrapper.
        assert db.globals[0].to_dict() == {
            "model": "gemini-2.5-pro",
            "temperature": 0.7,
            "max_output_tokens": 4096,
        }

    def test_flattens_overlay_doc_via_collection_group(self) -> None:
        db = FakeFlattenDb(
            overlays=[
                (
                    "acc_123",
                    "custom_xyz",
                    {
                        "model": "gemini-2.5-flash",
                        "generate_content_config": {"temperature": 0.4},
                    },
                )
            ]
        )

        counts = migrate(project_id="test-project", dry_run=False, db=db)

        assert counts["flattened"] == 1
        assert db.overlays[0].to_dict() == {
            "model": "gemini-2.5-flash",
            "temperature": 0.4,
        }

    def test_walks_globals_and_overlays_mixed(self) -> None:
        db = FakeFlattenDb(
            globals_=[
                (
                    "ken_e_chatbot",
                    {
                        "model": "gemini-2.5-pro",
                        "generate_content_config": {"temperature": 0.7},
                    },
                ),
                (
                    "already_flat",
                    {"model": "gemini-2.5-pro", "temperature": 0.3},
                ),
            ],
            overlays=[
                (
                    "acc_1",
                    "custom_a",
                    {
                        "model": "gemini-2.5-flash",
                        "generate_content_config": {"max_output_tokens": 2048},
                    },
                ),
                (
                    "acc_2",
                    "custom_b",
                    {"model": "gemini-2.5-flash", "temperature": 0.5},
                ),
            ],
        )

        counts = migrate(project_id="test-project", dry_run=False, db=db)

        assert counts["flattened"] == 2  # ken_e_chatbot global + custom_a overlay
        assert counts["unchanged"] == 2  # already_flat global + custom_b overlay
        assert counts["errors"] == 0

    def test_dry_run_does_not_write(self) -> None:
        db = FakeFlattenDb(
            globals_=[
                (
                    "ken_e_chatbot",
                    {
                        "model": "gemini-2.5-pro",
                        "generate_content_config": {"temperature": 0.7},
                    },
                )
            ]
        )

        counts = migrate(project_id="test-project", dry_run=True, db=db)

        assert counts["would_flatten"] == 1
        assert counts["flattened"] == 0
        # Doc unchanged in dry-run.
        assert "generate_content_config" in db.globals[0].to_dict()
        db.globals[0].reference.update.assert_not_called()

    def test_idempotent_second_run_is_no_op(self) -> None:
        """AC-7: running the migration twice produces no errors and no
        field changes on the second run."""
        db = FakeFlattenDb(
            globals_=[
                (
                    "ken_e_chatbot",
                    {
                        "model": "gemini-2.5-pro",
                        "generate_content_config": {
                            "temperature": 0.7,
                            "max_output_tokens": 4096,
                        },
                    },
                )
            ]
        )

        first = migrate(project_id="test-project", dry_run=False, db=db)
        second = migrate(project_id="test-project", dry_run=False, db=db)

        assert first["flattened"] == 1
        assert second["flattened"] == 0
        assert second["unchanged"] == 1
        assert second["errors"] == 0

    def test_globals_not_double_counted_via_collection_group(self) -> None:
        """The collection-group walk also surfaces globals; the path-segment
        filter must skip them to avoid double-processing."""
        db = FakeFlattenDb(
            globals_=[
                (
                    "ken_e_chatbot",
                    {
                        "model": "gemini-2.5-pro",
                        "generate_content_config": {"temperature": 0.7},
                    },
                )
            ]
        )

        counts = migrate(project_id="test-project", dry_run=False, db=db)

        # Only one flatten — the global doc — not counted twice.
        assert counts["flattened"] == 1
        assert counts["unchanged"] == 0
        # And the underlying ref was updated exactly once.
        assert db.globals[0].reference.update.call_count == 1


# ---------------------------------------------------------------------------
# Forward-reference for the FakeSnapshot type in _FakeRef's __init__.
# Python evaluates the annotation lazily because of ``from __future__ import
# annotations``, so this is purely a static-typing nicety.
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
