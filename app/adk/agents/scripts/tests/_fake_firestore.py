"""Minimal in-memory Firestore stand-in for seed-script unit tests (AH-41).

Supports the subset of the firestore.Client API the seed scripts call:

* ``db.collection(name).document(id).get()`` → snapshot with ``.exists`` /
  ``.to_dict()``.
* ``db.collection(name).document(id).set(data, merge=True)`` → shallow
  field-level merge into the stored doc.

Mirrors Firestore's ``merge=True`` semantics: only top-level keys in
``data`` are written; existing keys not in ``data`` are preserved.
``merge=False`` (default ``set``) would overwrite the doc — not used by
the AH-41 scripts and not implemented here.
"""

from __future__ import annotations

from typing import Any


class _Snapshot:
    def __init__(self, exists: bool, data: dict[str, Any]) -> None:
        self.exists = exists
        self._data = data

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)


class _DocRef:
    def __init__(self, store: dict[str, dict[str, Any]], doc_id: str) -> None:
        self._store = store
        self._doc_id = doc_id

    def get(self) -> _Snapshot:
        exists = self._doc_id in self._store
        return _Snapshot(exists, self._store.get(self._doc_id, {}))

    def set(self, data: dict[str, Any], merge: bool = False) -> None:
        if not merge:
            raise NotImplementedError(
                "FakeFirestoreClient only models set(..., merge=True); "
                "AH-41 seed scripts must use merge=True."
            )
        existing = self._store.setdefault(self._doc_id, {})
        for key, value in data.items():
            existing[key] = value


class _Collection:
    def __init__(self, store: dict[str, dict[str, Any]]) -> None:
        self._store = store

    def document(self, doc_id: str) -> _DocRef:
        return _DocRef(self._store, doc_id)


class FakeFirestoreClient:
    """In-memory Firestore client backing seed-script idempotency tests.

    ``stores`` is a ``{collection_name: {doc_id: data}}`` dict; the test
    can pre-seed docs by populating it before calling the script under
    test.
    """

    def __init__(self, stores: dict[str, dict[str, dict[str, Any]]] | None = None) -> None:
        self._stores: dict[str, dict[str, dict[str, Any]]] = stores or {}

    def collection(self, name: str) -> _Collection:
        return _Collection(self._stores.setdefault(name, {}))

    def get_doc(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        """Test helper: return the stored doc dict, or None if absent."""
        coll = self._stores.get(collection, {})
        return dict(coll[doc_id]) if doc_id in coll else None
