"""Integration tests for the Skills REST API (SK-15, SK-16).

Covers POST, GET list, PUT (SK-15) and POST /validate (SK-16) under
``/api/v1/accounts/{account_id}/skills``.

Uses in-memory fakes for Firestore and GCS, mirroring the pattern from
``test_agent_configs_api.py`` (project-established sibling).

Emulator-backed tests (``@pytest.mark.requires_firestore_emulator``) are
deferred to a separate module — the fake's ``@firestore.transactional``
decorator faithfully simulates the transaction retry-on-conflict path, which
is sufficient for AC-1, AC-5, AC-9, AC-10 coverage at the unit level.

AC coverage (SK-PRD-01 §7):
  AC-1  POST returns 201 with Skill body; Firestore doc at
        ``accounts/A/skills/{skill_id}``; GCS at correct prefix.
  AC-5  PUT increments current_version; new GCS prefix; old version present.
  AC-9  POST same name same account → 409; same name different account → 201.
  AC-10 POST /validate returns 200 + {valid, errors}; writes no state.
  + 422 with field pointers on validation failure
  + 403 for non-member user
  + 401 for unauthenticated request

Note: AC-13 (account-deletion sweep) is owned by SK-18.
      AC-14 (lint + tests pass) is enforced by CI.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth.models import UserContext
from src.kene_api.auth.user_context import get_current_user_context
from src.kene_api.dependencies import get_firestore
from src.kene_api.main import app
from src.kene_api.services.skill_storage import (
    SkillStorageService,
    get_skill_storage_service,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACCOUNT_ID = "acc_skills_test"
OTHER_ACCOUNT_ID = "acc_skills_other"
BASE_URL = f"/api/v1/accounts/{ACCOUNT_ID}/skills"
OTHER_BASE_URL = f"/api/v1/accounts/{OTHER_ACCOUNT_ID}/skills"

_VALID_SKILL_MD = b"""---
name: seo-checklist
description: SEO optimisation checklist for blog posts.
---

## Checklist
- Title tag optimised
- Meta description present
"""

_VALID_SKILL_MD_V2 = b"""---
name: seo-checklist
description: Updated SEO checklist.
---

## Checklist v2
- Title tag
- Meta description
- Open Graph tags
"""

_VALID_SKILL_MD_B = b"""---
name: blog-outliner
description: Draft blog outline generator.
---

## Outline
- Introduction
- Body
- Conclusion
"""

# ---------------------------------------------------------------------------
# Fake Firestore
# ---------------------------------------------------------------------------


class _FakeDocRef:
    """Simulates ``google.cloud.firestore.DocumentReference``."""

    def __init__(self, store: dict, path: str) -> None:
        self._store = store
        self._path = path

    def get(self, transaction: Any = None) -> _FakeDocSnapshot:
        data = self._store.get(self._path)
        return _FakeDocSnapshot(self._path, data)

    def set(self, data: dict) -> None:
        self._store[self._path] = dict(data)

    def update(self, updates: dict) -> None:
        if self._path not in self._store:
            self._store[self._path] = {}
        self._store[self._path].update(updates)

    def create(self, data: dict) -> None:
        if self._path in self._store:
            raise Exception(f"Document already exists: {self._path}")
        self._store[self._path] = dict(data)

    def collection(self, name: str) -> _FakeCollectionRef:
        return _FakeCollectionRef(self._store, f"{self._path}/{name}")

    @property
    def id(self) -> str:
        return self._path.rsplit("/", 1)[-1]


class _FakeDocSnapshot:
    """Simulates ``google.cloud.firestore.DocumentSnapshot``."""

    def __init__(self, path: str, data: dict | None) -> None:
        self._path = path
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    @property
    def id(self) -> str:
        return self._path.rsplit("/", 1)[-1]

    def to_dict(self) -> dict:
        return dict(self._data) if self._data else {}


class _FakeCollectionRef:
    """Simulates ``google.cloud.firestore.CollectionReference``."""

    def __init__(self, store: dict, path: str) -> None:
        self._store = store
        self._path = path

    def document(self, doc_id: str) -> _FakeDocRef:
        return _FakeDocRef(self._store, f"{self._path}/{doc_id}")

    def where(self, field: str, op: str, value: Any) -> _FakeQuery:
        return _FakeQuery(self._store, self._path, filters=[(field, op, value)])

    def order_by(self, field: str, direction: Any = None) -> _FakeQuery:
        return _FakeQuery(self._store, self._path).order_by(field, direction)

    def stream(self) -> list[_FakeDocSnapshot]:
        prefix = self._path + "/"
        results = []
        for path, data in self._store.items():
            if not path.startswith(prefix):
                continue
            remainder = path[len(prefix) :]
            if remainder and "/" not in remainder:
                results.append(_FakeDocSnapshot(path, data))
        return results


class _FakeQuery:
    """Minimal query chain — supports where/order_by/limit/start_after/stream."""

    def __init__(
        self,
        store: dict,
        collection_path: str,
        filters: list[tuple] | None = None,
        _order_fields: list[tuple[str, Any]] | None = None,
        _limit_val: int | None = None,
        _start_after_doc: dict | None = None,
    ) -> None:
        self._store = store
        self._collection_path = collection_path
        self._filters = filters or []
        self._order_fields = _order_fields or []
        self._limit_val = _limit_val
        self._start_after_doc = _start_after_doc

    def where(self, field: str, op: str, value: Any) -> _FakeQuery:
        return _FakeQuery(
            self._store,
            self._collection_path,
            [*self._filters, (field, op, value)],
            self._order_fields,
            self._limit_val,
            self._start_after_doc,
        )

    def order_by(self, field: str, direction: Any = None) -> _FakeQuery:
        return _FakeQuery(
            self._store,
            self._collection_path,
            self._filters,
            [*self._order_fields, (field, direction)],
            self._limit_val,
            self._start_after_doc,
        )

    def limit(self, n: int) -> _FakeQuery:
        return _FakeQuery(
            self._store,
            self._collection_path,
            self._filters,
            self._order_fields,
            n,
            self._start_after_doc,
        )

    def start_after(self, first_val, *field_values) -> _FakeQuery:
        # Accepts either a dict or positional field values (updated_at, skill_id).
        if isinstance(first_val, dict):
            doc = first_val
        else:
            doc = {
                "updated_at": first_val,
                "skill_id": field_values[0] if field_values else "",
            }
        return _FakeQuery(
            self._store,
            self._collection_path,
            self._filters,
            self._order_fields,
            self._limit_val,
            doc,
        )

    def stream(self) -> list[_FakeDocSnapshot]:
        prefix = self._collection_path + "/"
        docs: list[_FakeDocSnapshot] = []
        for path, data in self._store.items():
            if not path.startswith(prefix):
                continue
            remainder = path[len(prefix) :]
            if remainder and "/" not in remainder:
                docs.append(_FakeDocSnapshot(path, data))

        # Apply filters.
        for field, op, value in self._filters:
            if op == "==":
                docs = [d for d in docs if d.to_dict().get(field) == value]
            elif op == "in":
                docs = [d for d in docs if d.to_dict().get(field) in value]

        # Apply start_after.
        if self._start_after_doc:
            after_skill_id = self._start_after_doc.get("skill_id", "")
            for i, d in enumerate(docs):
                if d.to_dict().get("skill_id") == after_skill_id:
                    docs = docs[i + 1 :]
                    break

        # Apply limit.
        if self._limit_val is not None:
            docs = docs[: self._limit_val]

        return docs


class _FakeFirestoreTransaction:
    """Simulates a Firestore transaction context for @firestore.transactional."""

    def __init__(self, store: dict) -> None:
        self._store = store
        self._ops: list[tuple] = []

    def create(self, ref: _FakeDocRef, data: dict) -> None:
        self._ops.append(("create", ref, dict(data)))

    def update(self, ref: _FakeDocRef, data: dict) -> None:
        self._ops.append(("update", ref, dict(data)))

    def commit(self) -> None:
        for op, ref, data in self._ops:
            if op == "create":
                path = ref._path
                if path in self._store:
                    raise Exception(f"Already exists: {path}")
                self._store[path] = data
            elif op == "update":
                path = ref._path
                if path not in self._store:
                    self._store[path] = {}
                self._store[path].update(data)
        self._ops.clear()


class _FakeFirestoreClient:
    """In-memory Firestore fake.

    Implements ``collection()``, ``document()``, ``transaction()``, and the
    ``@firestore.transactional`` decorator.
    """

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}

    def collection(self, name: str) -> _FakeCollectionRef:
        return _FakeCollectionRef(self._store, name)

    def transaction(self) -> _FakeFirestoreTransaction:
        return _FakeFirestoreTransaction(self._store)

    def get_doc(self, path: str) -> dict | None:
        return self._store.get(path)

    def list_docs_under(self, prefix: str) -> list[tuple[str, dict]]:
        result = []
        for path, data in self._store.items():
            if path.startswith(prefix):
                result.append((path, data))
        return result


# ---------------------------------------------------------------------------
# Fake GCS (reuse the pattern from test_skill_storage.py)
# ---------------------------------------------------------------------------


class _FakeBlob:
    def __init__(self, name: str) -> None:
        self.name = name
        self.cache_control: str | None = None
        self._data: bytes | None = None

    def upload_from_string(self, data: bytes, content_type: str = "") -> None:
        self._data = data

    def download_as_bytes(self) -> bytes:
        if self._data is None:
            raise Exception(f"Blob {self.name!r} not found")
        return self._data

    def exists(self) -> bool:
        return self._data is not None

    def rewrite(self, destination: _FakeBlob, *, token: Any = None) -> tuple:
        """Server-side copy simulation. Returns (None, 0, 0) — done in one pass."""
        destination._data = self._data
        destination.cache_control = self.cache_control
        return (None, 0, 0)

    def delete(self) -> None:
        self._data = None


class _FakeBucket:
    def __init__(self) -> None:
        self._store: dict[str, _FakeBlob] = {}

    def blob(self, name: str) -> _FakeBlob:
        if name not in self._store:
            self._store[name] = _FakeBlob(name)
        return self._store[name]

    def has_blob(self, name: str) -> bool:
        b = self._store.get(name)
        return b is not None and b._data is not None


class _FakeGcsClient:
    def __init__(self) -> None:
        self._buckets: dict[str, _FakeBucket] = {}

    def bucket(self, name: str) -> _FakeBucket:
        if name not in self._buckets:
            self._buckets[name] = _FakeBucket()
        return self._buckets[name]

    def list_blobs(self, bucket_or_name: Any, prefix: str = "") -> list[_FakeBlob]:
        if isinstance(bucket_or_name, _FakeBucket):
            bkt = bucket_or_name
        else:
            bkt = self.bucket(bucket_or_name)
        return [
            b
            for name, b in bkt._store.items()
            if name.startswith(prefix) and b._data is not None
        ]


def _make_storage_service() -> tuple[SkillStorageService, _FakeGcsClient]:
    svc = SkillStorageService(project_id="test-project", environment="test")
    fake_gcs = _FakeGcsClient()
    svc.client = fake_gcs
    return svc, fake_gcs


# ---------------------------------------------------------------------------
# User context factories
# ---------------------------------------------------------------------------


def _member_user(account_id: str = ACCOUNT_ID) -> UserContext:
    return UserContext(
        user_id="user-uid-123",
        email="author@example.com",
        organization_permissions={},
        account_permissions={account_id: "admin"},
    )


def _no_access_user() -> UserContext:
    return UserContext(
        user_id="stranger-uid",
        email="stranger@example.com",
        organization_permissions={},
        account_permissions={},
    )


def _multipart_form(
    name: str,
    skill_md_content: bytes,
    extra_files: list[tuple[str, bytes, str]] | None = None,
) -> dict:
    """Build the multipart form data dict for TestClient."""
    files_list: list = [
        ("skill_md", ("SKILL.md", io.BytesIO(skill_md_content), "text/markdown"))
    ]
    for rel_path, content, mime in extra_files or []:
        files_list.append(("files", (rel_path, io.BytesIO(content), mime)))
    return {"files": files_list, "data": {"name": name}}


# ---------------------------------------------------------------------------
# Base test class
# ---------------------------------------------------------------------------


class _SkillsRouterBase:
    """Base class: dependency overrides + reset."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        app.dependency_overrides.clear()
        # Patch @firestore.transactional before each test.
        import google.cloud.firestore as fs_module

        original_transactional = fs_module.transactional
        fs_module.transactional = _fake_transactional_decorator
        yield
        app.dependency_overrides.clear()
        fs_module.transactional = original_transactional

    @pytest.fixture
    def fake_db(self) -> _FakeFirestoreClient:
        db = _FakeFirestoreClient()
        app.dependency_overrides[get_firestore] = lambda: db
        return db

    @pytest.fixture
    def fake_storage(self) -> tuple[SkillStorageService, _FakeGcsClient]:
        svc, gcs = _make_storage_service()
        app.dependency_overrides[get_skill_storage_service] = lambda: svc
        return svc, gcs

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app, raise_server_exceptions=False)

    def _install_user(self, user: UserContext) -> None:
        async def _get():
            return user

        app.dependency_overrides[get_current_user_context] = _get


def _fake_transactional_decorator(fn):
    """Stand-in for @firestore.transactional: invoke fn(transaction, ...) then commit."""

    def _wrapped(transaction, *args, **kwargs):
        result = fn(transaction, *args, **kwargs)
        transaction.commit()
        return result

    return _wrapped


# ---------------------------------------------------------------------------
# Auth tests (no Firestore/GCS state needed)
# ---------------------------------------------------------------------------


class TestSkillsRouterAuth(_SkillsRouterBase):
    """Authorization boundary tests."""

    def test_unauthenticated_returns_401(self, client, fake_db, fake_storage):
        resp = client.get(BASE_URL + "/")
        assert resp.status_code == 401

    def test_non_member_get_list_returns_403(self, client, fake_db, fake_storage):
        self._install_user(_no_access_user())
        resp = client.get(BASE_URL + "/")
        assert resp.status_code == 403

    def test_non_member_post_returns_403(self, client, fake_db, fake_storage):
        self._install_user(_no_access_user())
        resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert resp.status_code == 403

    def test_non_member_put_returns_403(self, client, fake_db, fake_storage):
        self._install_user(_no_access_user())
        resp = client.put(
            BASE_URL + "/someSkillId",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert resp.status_code == 403

    def test_member_of_other_account_cannot_access(self, client, fake_db, fake_storage):
        """Member of account B cannot access account A's skills endpoint."""
        other_user = UserContext(
            user_id="other-uid",
            email="other@example.com",
            organization_permissions={},
            account_permissions={OTHER_ACCOUNT_ID: "admin"},
        )
        self._install_user(other_user)
        resp = client.get(BASE_URL + "/")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST: create skill (AC-1)
# ---------------------------------------------------------------------------


class TestPostCreateSkill(_SkillsRouterBase):
    """AC-1: POST returns 201; Firestore doc + GCS bundle created."""

    def test_post_creates_skill_returns_201_with_skill_body(
        self, client, fake_db, fake_storage
    ):
        _svc, gcs = fake_storage
        self._install_user(_member_user())

        resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "seo-checklist"
        assert body["current_version"] == 1
        assert body["status"] == "draft"
        assert body["has_scripts"] is False
        skill_id = body["skill_id"]
        assert len(skill_id) == 32  # uuid4().hex

        # Firestore doc exists at the correct path.
        doc_path = f"accounts/{ACCOUNT_ID}/skills/{skill_id}"
        doc = fake_db.get_doc(doc_path)
        assert doc is not None
        assert doc["name"] == "seo-checklist"
        assert doc["current_version"] == 1

        # GCS bundle at correct prefix.
        primary_bkt = gcs.bucket("kene-skills-test")
        assert primary_bkt.has_blob(f"accounts/{ACCOUNT_ID}/{skill_id}/1/SKILL.md")

    def test_post_with_reference_file_sets_correct_metadata(
        self, client, fake_db, fake_storage
    ):
        self._install_user(_member_user())
        resp = client.post(
            BASE_URL + "/",
            files=[
                (
                    "skill_md",
                    ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"),
                ),
                (
                    "files",
                    ("references/guide.md", io.BytesIO(b"# Guide"), "text/markdown"),
                ),
            ],
            data={"name": "seo-checklist"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["has_scripts"] is False

    def test_post_with_scripts_file_sets_has_scripts_true(
        self, client, fake_db, fake_storage
    ):
        self._install_user(_member_user())
        resp = client.post(
            BASE_URL + "/",
            files=[
                (
                    "skill_md",
                    ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"),
                ),
                (
                    "files",
                    ("scripts/run.py", io.BytesIO(b"print('hello')"), "text/x-python"),
                ),
            ],
            data={"name": "seo-checklist"},
        )
        assert resp.status_code == 201
        assert resp.json()["has_scripts"] is True

    def test_post_invalid_skill_md_returns_422_with_field_pointer(
        self, client, fake_db, fake_storage
    ):
        self._install_user(_member_user())
        bad_md = b"No frontmatter."
        resp = client.post(
            BASE_URL + "/",
            files=[("skill_md", ("SKILL.md", io.BytesIO(bad_md), "text/markdown"))],
            data={"name": "bad-skill"},
        )
        assert resp.status_code == 422
        detail = resp.json().get("detail", [])
        fields = [d["field"] for d in detail] if isinstance(detail, list) else []
        assert any("skill_md" in f for f in fields)

    def test_post_invalid_name_case_returns_422(self, client, fake_db, fake_storage):
        self._install_user(_member_user())
        bad_md = b"---\nname: UpperCase\ndescription: test\n---\nbody"
        resp = client.post(
            BASE_URL + "/",
            files=[("skill_md", ("SKILL.md", io.BytesIO(bad_md), "text/markdown"))],
            data={"name": "UpperCase"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST: name uniqueness (AC-9)
# ---------------------------------------------------------------------------


class TestPostNameUniqueness(_SkillsRouterBase):
    """AC-9: duplicate name in same account → 409; different account → 201."""

    def _create_skill(
        self, client, name: str = "seo-checklist", account_id: str = ACCOUNT_ID
    ):
        user = _member_user(account_id)
        self._install_user(user)
        url = f"/api/v1/accounts/{account_id}/skills/"
        return client.post(
            url,
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": name},
        )

    def test_duplicate_name_same_account_returns_409(
        self, client, fake_db, fake_storage
    ):
        resp1 = self._create_skill(client, name="seo-checklist")
        assert resp1.status_code == 201

        resp2 = self._create_skill(client, name="seo-checklist")
        assert resp2.status_code == 409
        detail = resp2.json()["detail"]
        assert detail["code"] == "skill_name_conflict"
        assert detail["name"] == "seo-checklist"

    def test_same_name_different_accounts_both_succeed(
        self, client, fake_db, fake_storage
    ):
        # Account A
        resp_a = self._create_skill(client, name="seo-checklist", account_id=ACCOUNT_ID)
        assert resp_a.status_code == 201

        # Account B — add B to dependency override for get_firestore
        # (the same fake_db serves both; uniqueness is per-account)
        other_user = _member_user(OTHER_ACCOUNT_ID)
        self._install_user(other_user)
        resp_b = client.post(
            OTHER_BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert resp_b.status_code == 201


# ---------------------------------------------------------------------------
# POST → GET list round-trip (AC-1)
# ---------------------------------------------------------------------------


class TestPostThenGetList(_SkillsRouterBase):
    """POST a skill then GET list to confirm it appears."""

    def test_post_then_get_list_shows_skill(self, client, fake_db, fake_storage):
        self._install_user(_member_user())

        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201

        get_resp = client.get(BASE_URL + "/")
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert "items" in body
        names = [item["name"] for item in body["items"]]
        assert "seo-checklist" in names

    def test_empty_list_returns_empty_items(self, client, fake_db, fake_storage):
        self._install_user(_member_user())
        resp = client.get(BASE_URL + "/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["next_cursor"] is None

    def test_include_archived_false_excludes_archived(
        self, client, fake_db, fake_storage
    ):
        # Manually seed an archived skill doc.
        skill_id = "archived_skill_id_001"
        fake_db._store[f"accounts/{ACCOUNT_ID}/skills/{skill_id}"] = {
            "skill_id": skill_id,
            "owner": {"account_id": ACCOUNT_ID, "shared_with_accounts": []},
            "name": "old-skill",
            "description": "An archived skill.",
            "current_version": 1,
            "visibility": "private",
            "status": "archived",
            "has_scripts": False,
            "created_at": "2026-01-01T00:00:00+00:00",
            "created_by": "user-1",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "updated_by": "user-1",
        }
        self._install_user(_member_user())
        resp = client.get(BASE_URL + "/")
        assert resp.status_code == 200
        names = [i["name"] for i in resp.json()["items"]]
        assert "old-skill" not in names

    def test_include_archived_true_includes_archived(
        self, client, fake_db, fake_storage
    ):
        skill_id = "archived_skill_id_002"
        fake_db._store[f"accounts/{ACCOUNT_ID}/skills/{skill_id}"] = {
            "skill_id": skill_id,
            "owner": {"account_id": ACCOUNT_ID, "shared_with_accounts": []},
            "name": "old-skill",
            "description": "An archived skill.",
            "current_version": 1,
            "visibility": "private",
            "status": "archived",
            "has_scripts": False,
            "created_at": "2026-01-01T00:00:00+00:00",
            "created_by": "user-1",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "updated_by": "user-1",
        }
        self._install_user(_member_user())
        resp = client.get(BASE_URL + "/?include_archived=true")
        assert resp.status_code == 200
        names = [i["name"] for i in resp.json()["items"]]
        assert "old-skill" in names

    def test_page_size_over_100_returns_422(self, client, fake_db, fake_storage):
        self._install_user(_member_user())
        resp = client.get(BASE_URL + "/?page_size=101")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PUT: versioned update (AC-5)
# ---------------------------------------------------------------------------


class TestPutVersionedUpdate(_SkillsRouterBase):
    """AC-5: PUT increments current_version; new GCS prefix; old preserved."""

    def test_put_increments_current_version(self, client, fake_db, fake_storage):
        _svc, gcs = fake_storage
        self._install_user(_member_user())

        # Create v1.
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        # Create v2 via PUT.
        put_resp = client.put(
            BASE_URL + f"/{skill_id}",
            files=[
                (
                    "skill_md",
                    ("SKILL.md", io.BytesIO(_VALID_SKILL_MD_V2), "text/markdown"),
                )
            ],
            data={"name": "seo-checklist"},
        )
        assert put_resp.status_code == 200
        body = put_resp.json()
        assert body["current_version"] == 2

        # Firestore doc reflects v2.
        doc_path = f"accounts/{ACCOUNT_ID}/skills/{skill_id}"
        doc = fake_db.get_doc(doc_path)
        assert doc["current_version"] == 2

        # New GCS prefix for v2 exists.
        primary_bkt = gcs.bucket("kene-skills-test")
        assert primary_bkt.has_blob(f"accounts/{ACCOUNT_ID}/{skill_id}/2/SKILL.md")

        # Old v1 prefix still exists.
        assert primary_bkt.has_blob(f"accounts/{ACCOUNT_ID}/{skill_id}/1/SKILL.md")

    def test_put_on_nonexistent_skill_returns_404(self, client, fake_db, fake_storage):
        self._install_user(_member_user())
        resp = client.put(
            BASE_URL + "/nonexistent_skill_id",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert resp.status_code == 404

    def test_put_rename_conflict_returns_409(self, client, fake_db, fake_storage):
        """PUT that renames a skill to an already-taken name returns 409."""
        self._install_user(_member_user())

        # Create skill A.
        resp_a = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert resp_a.status_code == 201

        # Create skill B.
        skill_b_md = (
            b"---\nname: blog-outliner\ndescription: Blog outline generator.\n---\nBody"
        )
        resp_b = client.post(
            BASE_URL + "/",
            files=[("skill_md", ("SKILL.md", io.BytesIO(skill_b_md), "text/markdown"))],
            data={"name": "blog-outliner"},
        )
        assert resp_b.status_code == 201
        skill_b_id = resp_b.json()["skill_id"]

        # Try to rename B to A's name.
        rename_md = b"---\nname: seo-checklist\ndescription: Renamed.\n---\nBody"
        put_resp = client.put(
            BASE_URL + f"/{skill_b_id}",
            files=[("skill_md", ("SKILL.md", io.BytesIO(rename_md), "text/markdown"))],
            data={"name": "seo-checklist"},
        )
        assert put_resp.status_code == 409

    def test_put_validation_failure_returns_422(self, client, fake_db, fake_storage):
        self._install_user(_member_user())
        # Create v1 first.
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        # PUT with bad SKILL.md.
        resp = client.put(
            BASE_URL + f"/{skill_id}",
            files=[
                (
                    "skill_md",
                    ("SKILL.md", io.BytesIO(b"no frontmatter"), "text/markdown"),
                )
            ],
            data={"name": "seo-checklist"},
        )
        assert resp.status_code == 422

    def test_put_with_commit_message(self, client, fake_db, fake_storage):
        self._install_user(_member_user())
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        # PUT with commit_message.
        put_resp = client.put(
            BASE_URL + f"/{skill_id}",
            files=[
                (
                    "skill_md",
                    ("SKILL.md", io.BytesIO(_VALID_SKILL_MD_V2), "text/markdown"),
                )
            ],
            data={"name": "seo-checklist", "commit_message": "Add Open Graph tags"},
        )
        assert put_resp.status_code == 200
        # Verify the version subdoc has the commit_message.
        version_path = f"accounts/{ACCOUNT_ID}/skills/{skill_id}/versions/2"
        version_doc = fake_db.get_doc(version_path)
        assert version_doc is not None
        assert version_doc["commit_message"] == "Add Open Graph tags"

    def test_put_name_mismatch_form_vs_frontmatter_returns_422(
        self, client, fake_db, fake_storage
    ):
        self._install_user(_member_user())
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        put_resp = client.put(
            BASE_URL + f"/{skill_id}",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "different-name"},  # mismatch
        )
        assert put_resp.status_code == 422
        detail = put_resp.json().get("detail", [])
        codes = [d["code"] for d in detail] if isinstance(detail, list) else []
        assert "name_mismatch" in codes


# ---------------------------------------------------------------------------
# POST /validate: dry-run validation (AC-10, SK-16)
# ---------------------------------------------------------------------------


def _make_skill_md(
    name: str = "my-skill",
    description: str = "A test skill.",
) -> bytes:
    """Return a valid minimal SKILL.md as bytes."""
    import yaml

    frontmatter = yaml.dump(
        {"name": name, "description": description}, default_flow_style=False
    )
    return f"---\n{frontmatter}---\n\nSkill body.\n".encode()


class TestValidateEndpoint:
    """AC-10: validate endpoint returns 200 + {valid, errors}; writes no state."""

    @pytest.fixture(autouse=True)
    def _install_auth(self):
        """Install a default authenticated user; override per-test as needed."""
        user = UserContext(
            user_id="test-uid",
            email="tester@example.com",
            organization_permissions={"org_abc": "admin"},
            account_permissions={ACCOUNT_ID: "admin"},
        )
        app.dependency_overrides[get_current_user_context] = lambda: user
        mock_fs = MagicMock()
        app.dependency_overrides[get_firestore] = lambda: mock_fs
        yield mock_fs
        app.dependency_overrides.clear()

    def test_valid_bundle_returns_valid_true(self) -> None:
        """AC-10: syntactically correct SKILL.md returns valid=True with empty errors."""
        client = TestClient(app, raise_server_exceptions=True)
        response = client.post(
            f"{BASE_URL}/validate",
            files={"skill_md": ("SKILL.md", _make_skill_md(), "text/markdown")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body == {"valid": True, "errors": []}

    def test_invalid_frontmatter_returns_valid_false(self) -> None:
        """AC-10: SKILL.md whose name fails kebab-case regex yields valid=False."""
        # "PDF-Processing" contains uppercase — fails SKILL_NAME_PATTERN
        bad_skill_md = _make_skill_md(name="PDF-Processing")
        client = TestClient(app, raise_server_exceptions=True)
        response = client.post(
            f"{BASE_URL}/validate",
            files={"skill_md": ("SKILL.md", bad_skill_md, "text/markdown")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["valid"] is False
        assert len(body["errors"]) >= 1
        first_error = body["errors"][0]
        assert first_error["code"] == "name_regex"
        assert "frontmatter.name" in first_error["field"]

    def test_validate_writes_no_firestore_state(self, _install_auth: MagicMock) -> None:
        """AC-10: neither valid nor invalid POST to /validate may touch Firestore."""
        mock_firestore = _install_auth
        client = TestClient(app, raise_server_exceptions=True)

        # Valid bundle POST
        client.post(
            f"{BASE_URL}/validate",
            files={"skill_md": ("SKILL.md", _make_skill_md(), "text/markdown")},
        )

        # Invalid bundle POST
        client.post(
            f"{BASE_URL}/validate",
            files={
                "skill_md": (
                    "SKILL.md",
                    _make_skill_md(name="Bad-Name"),
                    "text/markdown",
                )
            },
        )

        assert mock_firestore.collection.call_count == 0

    def test_validate_requires_auth(self) -> None:
        """AC-10: without an authenticated user context the endpoint returns 401."""
        app.dependency_overrides.clear()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            f"{BASE_URL}/validate",
            files={"skill_md": ("SKILL.md", _make_skill_md(), "text/markdown")},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /{skill_id}: metadata detail (SK-19, AC-7)
# ---------------------------------------------------------------------------


def _seed_skill_doc(
    fake_db: _FakeFirestoreClient,
    skill_id: str,
    *,
    account_id: str = ACCOUNT_ID,
    name: str = "seo-checklist",
    status: str = "draft",
    current_version: int = 1,
    has_scripts: bool = False,
) -> str:
    """Seed a minimal Skill Firestore doc and return the skill_id."""
    fake_db._store[f"accounts/{account_id}/skills/{skill_id}"] = {
        "skill_id": skill_id,
        "owner": {"account_id": account_id, "shared_with_accounts": []},
        "name": name,
        "description": "Test skill.",
        "current_version": current_version,
        "visibility": "private",
        "status": status,
        "has_scripts": has_scripts,
        "created_at": "2026-01-01T00:00:00+00:00",
        "created_by": "user-uid-123",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "updated_by": "user-uid-123",
    }
    return skill_id


class TestGetSkillDetail(_SkillsRouterBase):
    """GET /{skill_id} returns Skill metadata; 404 for archived by default (SK-19)."""

    def test_get_draft_returns_200(self, client, fake_db, fake_storage):
        self._install_user(_member_user())
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        resp = client.get(BASE_URL + f"/{skill_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["skill_id"] == skill_id
        assert body["name"] == "seo-checklist"
        assert body["status"] == "draft"
        assert body["current_version"] == 1

    def test_get_archived_default_returns_404(self, client, fake_db, fake_storage):
        skill_id = _seed_skill_doc(fake_db, "skill-arch-001", status="archived")
        self._install_user(_member_user())
        resp = client.get(BASE_URL + f"/{skill_id}")
        assert resp.status_code == 404

    def test_get_archived_with_flag_returns_200(self, client, fake_db, fake_storage):
        skill_id = _seed_skill_doc(fake_db, "skill-arch-002", status="archived")
        self._install_user(_member_user())
        resp = client.get(BASE_URL + f"/{skill_id}?include_archived=true")
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    def test_get_nonexistent_returns_404(self, client, fake_db, fake_storage):
        self._install_user(_member_user())
        resp = client.get(BASE_URL + "/no-such-skill-id")
        assert resp.status_code == 404

    def test_get_cross_account_returns_404(self, client, fake_db, fake_storage):
        """Skill at ACCOUNT_ID is not visible via OTHER_ACCOUNT_ID path."""
        self._install_user(_member_user())
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        self._install_user(_member_user(OTHER_ACCOUNT_ID))
        resp = client.get(OTHER_BASE_URL + f"/{skill_id}")
        assert resp.status_code == 404

    def test_get_non_member_returns_403(self, client, fake_db, fake_storage):
        self._install_user(_no_access_user())
        resp = client.get(BASE_URL + "/any-skill-id")
        assert resp.status_code == 403

    def test_get_unauthenticated_returns_401(self, client, fake_db, fake_storage):
        resp = client.get(BASE_URL + "/any-skill-id")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /{skill_id}/content (SK-19, AC-4, AC-5)
# ---------------------------------------------------------------------------


class TestGetSkillContent(_SkillsRouterBase):
    """GET /{skill_id}/content returns SKILL.md bytes with text/markdown (SK-19)."""

    def test_get_content_returns_skill_md_bytes(self, client, fake_db, fake_storage):
        self._install_user(_member_user())
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        resp = client.get(BASE_URL + f"/{skill_id}/content")
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers["content-type"]
        assert resp.content == _VALID_SKILL_MD

    def test_get_content_version_pinning(self, client, fake_db, fake_storage):
        """`?version=1` returns the v1 bytes even after a v2 PUT."""
        self._install_user(_member_user())
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        put_resp = client.put(
            BASE_URL + f"/{skill_id}",
            files=[
                (
                    "skill_md",
                    ("SKILL.md", io.BytesIO(_VALID_SKILL_MD_V2), "text/markdown"),
                )
            ],
            data={"name": "seo-checklist"},
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["current_version"] == 2

        resp = client.get(BASE_URL + f"/{skill_id}/content?version=1")
        assert resp.status_code == 200
        assert resp.content == _VALID_SKILL_MD

    def test_get_content_missing_version_returns_404(
        self, client, fake_db, fake_storage
    ):
        self._install_user(_member_user())
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        resp = client.get(BASE_URL + f"/{skill_id}/content?version=99")
        assert resp.status_code == 404

    def test_get_content_archived_default_returns_404(
        self, client, fake_db, fake_storage
    ):
        skill_id = _seed_skill_doc(fake_db, "skill-content-arch-001", status="archived")
        self._install_user(_member_user())
        resp = client.get(BASE_URL + f"/{skill_id}/content")
        assert resp.status_code == 404

    def test_get_content_cross_account_returns_404(self, client, fake_db, fake_storage):
        """Skill content cannot be fetched via a different account's path."""
        self._install_user(_member_user())
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        self._install_user(_member_user(OTHER_ACCOUNT_ID))
        resp = client.get(OTHER_BASE_URL + f"/{skill_id}/content")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /{skill_id}/resources/{rel_path} (SK-19, AC-4)
# ---------------------------------------------------------------------------


class TestGetSkillResources(_SkillsRouterBase):
    """GET /resources/{rel_path}: content-type dispatch and path-traversal rejection (SK-19)."""

    def test_get_resource_md_returns_text_markdown(self, client, fake_db, fake_storage):
        self._install_user(_member_user())
        ref_content = b"# Guide content"
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                (
                    "skill_md",
                    ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"),
                ),
                (
                    "files",
                    ("references/guide.md", io.BytesIO(ref_content), "text/markdown"),
                ),
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        resp = client.get(BASE_URL + f"/{skill_id}/resources/references/guide.md")
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers["content-type"]
        assert resp.content == ref_content

    def test_get_resource_non_md_returns_text_plain(
        self, client, fake_db, fake_storage
    ):
        self._install_user(_member_user())
        script_content = b"print('hello')"
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                (
                    "skill_md",
                    ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"),
                ),
                (
                    "files",
                    ("scripts/run.py", io.BytesIO(script_content), "text/x-python"),
                ),
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        resp = client.get(BASE_URL + f"/{skill_id}/resources/scripts/run.py")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        assert resp.content == script_content

    def test_get_resource_version_pinning(self, client, fake_db, fake_storage):
        """`?version=1` returns the v1 resource bytes even after a PUT (v2)."""
        self._install_user(_member_user())
        ref_v1 = b"# v1 guide"
        ref_v2 = b"# v2 guide"
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                (
                    "skill_md",
                    ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"),
                ),
                ("files", ("references/guide.md", io.BytesIO(ref_v1), "text/markdown")),
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        put_resp = client.put(
            BASE_URL + f"/{skill_id}",
            files=[
                (
                    "skill_md",
                    ("SKILL.md", io.BytesIO(_VALID_SKILL_MD_V2), "text/markdown"),
                ),
                ("files", ("references/guide.md", io.BytesIO(ref_v2), "text/markdown")),
            ],
            data={"name": "seo-checklist"},
        )
        assert put_resp.status_code == 200

        resp = client.get(
            BASE_URL + f"/{skill_id}/resources/references/guide.md?version=1"
        )
        assert resp.status_code == 200
        assert resp.content == ref_v1

    def test_get_resource_traversal_percent_encoded_returns_400(
        self, client, fake_db, fake_storage
    ):
        """AC-4: triple-encoded `%` in the URL survives two decode passes and reaches
        safe_rel_path as `%`, which rejects it with 400.

        Starlette TestClient applies `unquote` once when building `scope["path"]`,
        then `PathConvertor.convert` applies `unquote` again when extracting the
        route parameter.  Two decode passes means:
          %2525 → (pass 1) %25 → (pass 2) %
        so `rel_path` contains a bare `%` and safe_rel_path returns None → 400.
        """
        self._install_user(_member_user())
        resp = client.get(BASE_URL + "/any-skill-id/resources/references%2525guide.md")
        assert resp.status_code == 400

    def test_get_resource_not_in_manifest_returns_404(
        self, client, fake_db, fake_storage
    ):
        """Requesting a path that was never uploaded returns 404."""
        self._install_user(_member_user())
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        resp = client.get(BASE_URL + f"/{skill_id}/resources/references/nonexistent.md")
        assert resp.status_code == 404

    def test_get_resource_archived_default_returns_404(
        self, client, fake_db, fake_storage
    ):
        skill_id = _seed_skill_doc(fake_db, "skill-res-arch-001", status="archived")
        self._install_user(_member_user())
        resp = client.get(BASE_URL + f"/{skill_id}/resources/references/guide.md")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /{skill_id}: soft-archive (SK-19, AC-6)
# ---------------------------------------------------------------------------


class TestDeleteSkill(_SkillsRouterBase):
    """DELETE sets status=archived, moves GCS to trash, returns 204 (SK-19, AC-6)."""

    def test_delete_returns_204(self, client, fake_db, fake_storage):
        self._install_user(_member_user())
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        resp = client.delete(BASE_URL + f"/{skill_id}")
        assert resp.status_code == 204

    def test_delete_sets_archived_status_in_firestore(
        self, client, fake_db, fake_storage
    ):
        self._install_user(_member_user())
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        client.delete(BASE_URL + f"/{skill_id}")

        doc = fake_db.get_doc(f"accounts/{ACCOUNT_ID}/skills/{skill_id}")
        assert doc is not None
        assert doc["status"] == "archived"

    def test_delete_moves_gcs_prefix_to_trash(self, client, fake_db, fake_storage):
        _svc, gcs = fake_storage
        self._install_user(_member_user())
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]
        primary_key = f"accounts/{ACCOUNT_ID}/{skill_id}/1/SKILL.md"

        primary_bkt = gcs.bucket("kene-skills-test")
        assert primary_bkt.has_blob(primary_key)

        client.delete(BASE_URL + f"/{skill_id}")

        assert not primary_bkt.has_blob(primary_key)
        trash_bkt = gcs.bucket("kene-skills-test-trash")
        assert trash_bkt.has_blob(primary_key)

    def test_delete_removes_skill_from_default_list(
        self, client, fake_db, fake_storage
    ):
        self._install_user(_member_user())
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        client.delete(BASE_URL + f"/{skill_id}")

        list_resp = client.get(BASE_URL + "/")
        names = [i["name"] for i in list_resp.json()["items"]]
        assert "seo-checklist" not in names

    def test_delete_then_get_detail_returns_404_by_default(
        self, client, fake_db, fake_storage
    ):
        self._install_user(_member_user())
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        client.delete(BASE_URL + f"/{skill_id}")

        resp = client.get(BASE_URL + f"/{skill_id}")
        assert resp.status_code == 404

    def test_delete_then_get_detail_with_include_archived_returns_200(
        self, client, fake_db, fake_storage
    ):
        self._install_user(_member_user())
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        client.delete(BASE_URL + f"/{skill_id}")

        resp = client.get(BASE_URL + f"/{skill_id}?include_archived=true")
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    def test_delete_twice_returns_404(self, client, fake_db, fake_storage):
        """D-1: second DELETE on an already-archived skill returns 404."""
        self._install_user(_member_user())
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        resp1 = client.delete(BASE_URL + f"/{skill_id}")
        assert resp1.status_code == 204

        resp2 = client.delete(BASE_URL + f"/{skill_id}")
        assert resp2.status_code == 404

    def test_delete_cross_account_returns_404(self, client, fake_db, fake_storage):
        """Skill at ACCOUNT_ID cannot be deleted via OTHER_ACCOUNT_ID path."""
        self._install_user(_member_user())
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]

        self._install_user(_member_user(OTHER_ACCOUNT_ID))
        resp = client.delete(OTHER_BASE_URL + f"/{skill_id}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Full CRUD round-trip (SK-19)
# ---------------------------------------------------------------------------


class TestCrudRoundTrip(_SkillsRouterBase):
    """POST → GET list → GET detail → PUT v2 → GET content v1 → DELETE → verify."""

    def test_full_crud_round_trip(self, client, fake_db, fake_storage):
        self._install_user(_member_user())

        # 1. POST — create v1
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        skill_id = post_resp.json()["skill_id"]
        assert post_resp.json()["current_version"] == 1

        # 2. GET list — skill appears
        list_resp = client.get(BASE_URL + "/")
        assert list_resp.status_code == 200
        assert "seo-checklist" in [i["name"] for i in list_resp.json()["items"]]

        # 3. GET detail — correct metadata
        detail_resp = client.get(BASE_URL + f"/{skill_id}")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["current_version"] == 1

        # 4. PUT — create v2
        put_resp = client.put(
            BASE_URL + f"/{skill_id}",
            files=[
                (
                    "skill_md",
                    ("SKILL.md", io.BytesIO(_VALID_SKILL_MD_V2), "text/markdown"),
                )
            ],
            data={"name": "seo-checklist"},
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["current_version"] == 2

        # 5. GET content ?version=1 — returns v1 bytes
        content_resp = client.get(BASE_URL + f"/{skill_id}/content?version=1")
        assert content_resp.status_code == 200
        assert content_resp.content == _VALID_SKILL_MD

        # 6. DELETE — soft-archive
        del_resp = client.delete(BASE_URL + f"/{skill_id}")
        assert del_resp.status_code == 204

        # 7. GET list — excluded from default listing
        list_resp2 = client.get(BASE_URL + "/")
        assert "seo-checklist" not in [i["name"] for i in list_resp2.json()["items"]]

        # 8. GET list ?include_archived=true — appears
        list_resp3 = client.get(BASE_URL + "/?include_archived=true")
        assert "seo-checklist" in [i["name"] for i in list_resp3.json()["items"]]

        # 9. GET detail default — 404
        assert client.get(BASE_URL + f"/{skill_id}").status_code == 404

        # 10. GET detail ?include_archived=true — 200 with status=archived
        final_resp = client.get(BASE_URL + f"/{skill_id}?include_archived=true")
        assert final_resp.status_code == 200
        assert final_resp.json()["status"] == "archived"


# ---------------------------------------------------------------------------
# AC-6 lifecycle visibility: Terraform config (SK-19)
# ---------------------------------------------------------------------------


class TestLifecycleVisibility:
    """AC-6: the skills-trash bucket must have a 30-day Delete lifecycle rule in Terraform."""

    def test_trash_bucket_has_30_day_delete_lifecycle_rule(self):
        tf_path = (
            Path(__file__).parents[3]
            / "deployment"
            / "terraform"
            / "gcs_skills_bucket.tf"
        )
        assert tf_path.exists(), f"Terraform config not found: {tf_path}"
        contents = tf_path.read_text()
        assert "age = 30" in contents, (
            "Expected 30-day lifecycle rule in gcs_skills_bucket.tf"
        )
        assert 'type = "Delete"' in contents, (
            "Expected Delete action type in gcs_skills_bucket.tf"
        )


# ---------------------------------------------------------------------------
# AC-7 has_scripts round-trip (SK-19)
# ---------------------------------------------------------------------------


class TestHasScriptsRoundTrip(_SkillsRouterBase):
    """AC-7: POST with scripts/ file → GET detail returns has_scripts=True."""

    def test_has_scripts_round_trip(self, client, fake_db, fake_storage):
        self._install_user(_member_user())
        post_resp = client.post(
            BASE_URL + "/",
            files=[
                (
                    "skill_md",
                    ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"),
                ),
                (
                    "files",
                    (
                        "scripts/extract.py",
                        io.BytesIO(b"# extraction script"),
                        "text/x-python",
                    ),
                ),
            ],
            data={"name": "seo-checklist"},
        )
        assert post_resp.status_code == 201
        assert post_resp.json()["has_scripts"] is True
        skill_id = post_resp.json()["skill_id"]

        detail_resp = client.get(BASE_URL + f"/{skill_id}")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["has_scripts"] is True


# ---------------------------------------------------------------------------
# AC-12: Weave tracing span attributes (SK-21)
# ---------------------------------------------------------------------------


class _SpanRecorder:
    """Captures calls to _maybe_weave_attrs.

    Used by TestSkillsTracing to assert span attribute correctness without
    requiring a live Weave connection.
    """

    def __init__(self) -> None:
        self.attrs_calls: list[dict] = []

    @contextlib.contextmanager
    def capture_weave_attrs(self, attrs: dict):  # type: ignore[override]
        self.attrs_calls.append(dict(attrs))
        yield

    def all_attrs(self) -> dict:
        merged: dict = {}
        for d in self.attrs_calls:
            merged.update(d)
        return merged


class TestSkillsTracing(_SkillsRouterBase):
    """AC-12: POST create emits api.skills.create span with expected attributes."""

    @pytest.fixture
    def span_recorder(self):
        import src.kene_api.routers.skills as skills_mod

        recorder = _SpanRecorder()
        with patch.object(
            skills_mod, "_maybe_weave_attrs", recorder.capture_weave_attrs
        ):
            yield recorder

    def test_post_create_emits_span_with_account_and_bundle_attrs(
        self, client, fake_db, fake_storage, span_recorder
    ):
        """Minimal POST (SKILL.md only) → account_id set, bundle_bytes > 0, file_count == 0."""
        self._install_user(_member_user())
        resp = client.post(
            BASE_URL + "/",
            files=[
                ("skill_md", ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"))
            ],
            data={"name": "seo-checklist"},
        )
        assert resp.status_code == 201

        attrs = span_recorder.all_attrs()
        assert attrs.get("account_id") == ACCOUNT_ID
        assert isinstance(attrs.get("bundle_bytes"), int)
        assert attrs["bundle_bytes"] > 0
        assert attrs.get("file_count") == 0
        assert "skill_id" in attrs

    def test_post_create_with_extra_files_records_correct_file_count(
        self, client, fake_db, fake_storage, span_recorder
    ):
        """POST with two extra files → file_count == 2."""
        self._install_user(_member_user())
        resp = client.post(
            BASE_URL + "/",
            files=[
                (
                    "skill_md",
                    ("SKILL.md", io.BytesIO(_VALID_SKILL_MD), "text/markdown"),
                ),
                (
                    "files",
                    (
                        "references/style.md",
                        io.BytesIO(b"# style guide"),
                        "text/markdown",
                    ),
                ),
                (
                    "files",
                    (
                        "references/tone.md",
                        io.BytesIO(b"# tone guide"),
                        "text/markdown",
                    ),
                ),
            ],
            data={"name": "seo-checklist"},
        )
        assert resp.status_code == 201

        attrs = span_recorder.all_attrs()
        assert attrs.get("account_id") == ACCOUNT_ID
        assert attrs.get("file_count") == 2
