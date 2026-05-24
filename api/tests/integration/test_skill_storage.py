"""Integration tests for ``SkillStorageService``.

Uses an in-process ``_FakeGcsClient`` that mirrors the exact GCS API surface
the service depends on, following the project pattern established in
``test_account_deletion_no_orphans.py``.

AC coverage (SK-PRD-01 §7 / SK-14 acceptance criteria):
  AC-4  path-traversal attempts on read return None; write raises ValueError
  AC-5  a PUT creates a new versioned prefix alongside the previous one
  AC-6  soft-delete moves prefix to trash; original returns None
  + manifest sha256 correctness
  + Cache-Control header on every blob
  + delete_account_prefix sweeps all account blobs
  + manifest-gate: syntactically safe path not in manifest returns None
  + read_skill_md returns the SKILL.md bytes

PRD reference: docs/design/components/skills/projects/SK-PRD-01-skills-backend.md §8
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, ClassVar

import pytest
from src.kene_api.models.skill_models import SkillFrontmatter
from src.kene_api.services.skill_storage import SkillStorageService

# ---------------------------------------------------------------------------
# _FakeGcsClient — minimal in-memory GCS fake
# ---------------------------------------------------------------------------


class _FakeBlob:
    """Simulates ``google.cloud.storage.Blob``."""

    def __init__(self, bucket: _FakeBucket, name: str) -> None:
        self._bucket = bucket
        self.name = name
        self.cache_control: str | None = None
        self._data: bytes | None = None
        self._deleted = False

    # --- upload ---

    def upload_from_string(
        self, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        self._deleted = False
        self._data = data
        self._bucket._store[self.name] = self

    # --- download ---

    def download_as_bytes(self) -> bytes:
        if self._deleted or self._data is None:
            raise Exception(f"Blob {self.name!r} not found")
        return self._data

    # --- existence ---

    def exists(self) -> bool:
        blob = self._bucket._store.get(self.name)
        return blob is not None and not blob._deleted

    # --- delete ---

    def delete(self) -> None:
        self._deleted = True
        self._bucket._store.pop(self.name, None)

    # --- rewrite (server-side copy) ---

    def rewrite(
        self, destination: _FakeBlob, *, token: Any = None
    ) -> tuple[Any, Any, Any]:
        if self._deleted or self._data is None:
            raise Exception(f"Source blob {self.name!r} not found")
        destination._data = self._data
        destination.cache_control = self.cache_control
        destination._deleted = False
        destination._bucket._store[destination.name] = destination
        return None, None, None  # (token=None → copy complete, no continuation)


class _FakeBucket:
    """Simulates ``google.cloud.storage.Bucket``."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._store: dict[str, _FakeBlob] = {}

    def blob(self, blob_name: str) -> _FakeBlob:
        # Always return the existing blob if it exists, or create a new shell.
        if blob_name in self._store:
            return self._store[blob_name]
        return _FakeBlob(self, blob_name)


class _FakeGcsClient:
    """Simulates ``google.cloud.storage.Client``."""

    def __init__(self) -> None:
        self._buckets: dict[str, _FakeBucket] = {}

    def bucket(self, name: str) -> _FakeBucket:
        if name not in self._buckets:
            self._buckets[name] = _FakeBucket(name)
        return self._buckets[name]

    def list_blobs(self, bucket_or_name: Any, prefix: str = "") -> list[_FakeBlob]:
        if isinstance(bucket_or_name, _FakeBucket):
            bkt = bucket_or_name
        else:
            bkt = self.bucket(bucket_or_name)
        return [b for name, b in bkt._store.items() if name.startswith(prefix)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_FRONTMATTER = SkillFrontmatter(
    name="test-skill",
    description="A skill for testing.",
)

_SAMPLE_SKILL_MD = (
    b"---\nname: test-skill\ndescription: A skill for testing.\n---\n# Body"
)

_SAMPLE_REF = b"# Style guide content"
_SAMPLE_ASSET = b"\x89PNG\r\n"  # fake PNG header
_SAMPLE_SCRIPT = b"print('hello')"


def _make_service() -> tuple[SkillStorageService, _FakeGcsClient]:
    """Return a SkillStorageService with a _FakeGcsClient injected."""
    svc = SkillStorageService(project_id="test-project", environment="development")
    fake_client = _FakeGcsClient()
    svc.client = fake_client
    return svc, fake_client


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestBundleGcsPrefixStructure:
    """TC-1: write_bundle creates blobs at exactly the right paths and nothing else."""

    def test_blob_paths(self) -> None:
        svc, _fake = _make_service()
        svc.write_bundle(
            account_id="acc1",
            skill_id="sk001",
            version=1,
            skill_md_bytes=_SAMPLE_SKILL_MD,
            files=[
                ("references/style.md", _SAMPLE_REF),
                ("assets/logo.png", _SAMPLE_ASSET),
                ("scripts/extract.py", _SAMPLE_SCRIPT),
            ],
            frontmatter=_SAMPLE_FRONTMATTER,
            created_by="user1",
        )
        bucket = _fake.bucket("kene-skills-development")
        expected_names = {
            "accounts/acc1/sk001/1/SKILL.md",
            "accounts/acc1/sk001/1/references/style.md",
            "accounts/acc1/sk001/1/assets/logo.png",
            "accounts/acc1/sk001/1/scripts/extract.py",
            "accounts/acc1/sk001/1/.manifest.json",
        }
        assert set(bucket._store.keys()) == expected_names


class TestManifestSha256Correctness:
    """TC-2: manifest entries have correct sha256, sizes, and kinds."""

    def test_manifest_entries(self) -> None:
        svc, _fake = _make_service()
        result = svc.write_bundle(
            account_id="acc1",
            skill_id="sk001",
            version=1,
            skill_md_bytes=_SAMPLE_SKILL_MD,
            files=[
                ("references/style.md", _SAMPLE_REF),
                ("scripts/run.py", _SAMPLE_SCRIPT),
            ],
            frontmatter=_SAMPLE_FRONTMATTER,
            created_by="user1",
        )
        by_path = {e.rel_path: e for e in result.file_manifest}

        # SKILL.md
        assert by_path["SKILL.md"].checksum_sha256 == _sha256(_SAMPLE_SKILL_MD)
        assert by_path["SKILL.md"].size_bytes == len(_SAMPLE_SKILL_MD)
        assert by_path["SKILL.md"].kind == "skill_md"

        # references/style.md
        assert by_path["references/style.md"].checksum_sha256 == _sha256(_SAMPLE_REF)
        assert by_path["references/style.md"].size_bytes == len(_SAMPLE_REF)
        assert by_path["references/style.md"].kind == "reference"

        # scripts/run.py
        assert by_path["scripts/run.py"].checksum_sha256 == _sha256(_SAMPLE_SCRIPT)
        assert by_path["scripts/run.py"].size_bytes == len(_SAMPLE_SCRIPT)
        assert by_path["scripts/run.py"].kind == "script"

    def test_manifest_json_on_disk_matches_return_value(self) -> None:
        svc, _fake = _make_service()
        result = svc.write_bundle(
            account_id="acc1",
            skill_id="sk001",
            version=1,
            skill_md_bytes=_SAMPLE_SKILL_MD,
            files=[("assets/logo.png", _SAMPLE_ASSET)],
            frontmatter=_SAMPLE_FRONTMATTER,
            created_by="user1",
        )
        bucket = _fake.bucket("kene-skills-development")
        manifest_blob = bucket._store["accounts/acc1/sk001/1/.manifest.json"]
        on_disk = json.loads(manifest_blob.download_as_bytes())
        file_paths = {e["rel_path"] for e in on_disk["files"]}
        returned_paths = {e.rel_path for e in result.file_manifest}
        assert file_paths == returned_paths


class TestCacheControlHeader:
    """TC-3: every uploaded blob carries cache_control == 'no-cache'."""

    def test_all_blobs_have_no_cache(self) -> None:
        svc, _fake = _make_service()
        svc.write_bundle(
            account_id="acc1",
            skill_id="sk001",
            version=1,
            skill_md_bytes=_SAMPLE_SKILL_MD,
            files=[
                ("references/style.md", _SAMPLE_REF),
                ("assets/logo.png", _SAMPLE_ASSET),
                ("scripts/extract.py", _SAMPLE_SCRIPT),
            ],
            frontmatter=_SAMPLE_FRONTMATTER,
            created_by="user1",
        )
        bucket = _fake.bucket("kene-skills-development")
        for blob in bucket._store.values():
            assert blob.cache_control == "no-cache", (
                f"Blob {blob.name!r} has cache_control={blob.cache_control!r}"
            )


class TestPathTraversalRejections:
    """TC-4: path-traversal attempts on read_file return None;
    write_bundle with such paths raises ValueError.

    Covers PRD §7 AC-4.
    """

    _TRAVERSAL_INPUTS: ClassVar[list[str]] = [
        "../etc/passwd",
        "%2e%2e/etc",
        "%2E%2E/etc",
        "/etc/passwd",
        "references\\..\\etc",
        "a\x00b",
        "",
    ]

    @pytest.mark.parametrize("bad_path", _TRAVERSAL_INPUTS)
    def test_read_file_returns_none(self, bad_path: str) -> None:
        svc, _fake = _make_service()
        # Seed a bundle first so the manifest exists.
        svc.write_bundle(
            account_id="acc1",
            skill_id="sk001",
            version=1,
            skill_md_bytes=_SAMPLE_SKILL_MD,
            files=[("references/style.md", _SAMPLE_REF)],
            frontmatter=_SAMPLE_FRONTMATTER,
            created_by="user1",
        )
        result = svc.read_file("acc1", "sk001", 1, bad_path)
        assert result is None, f"Expected None for {bad_path!r}, got {result!r}"

    @pytest.mark.parametrize(
        "bad_path",
        [
            "../etc/passwd",
            "%2e%2e/etc",
            "/etc/passwd",
            "references\\..\\etc",
            "a\x00b",
        ],
    )
    def test_write_bundle_raises_for_bad_paths(self, bad_path: str) -> None:
        svc, _ = _make_service()
        with pytest.raises(ValueError):
            svc.write_bundle(
                account_id="acc1",
                skill_id="sk001",
                version=1,
                skill_md_bytes=_SAMPLE_SKILL_MD,
                files=[(bad_path, b"content")],
                frontmatter=_SAMPLE_FRONTMATTER,
                created_by="user1",
            )

    def test_read_file_no_gcs_io_on_traversal(self) -> None:
        """safe_rel_path rejects before any GCS I/O — even without a seeded bundle."""
        svc, _fake = _make_service()
        # No bundle seeded; if safe_rel_path does not short-circuit, _load_manifest
        # would raise (no .manifest.json in an empty fake client).
        result = svc.read_file("acc1", "sk001", 1, "../etc/passwd")
        assert result is None


class TestSoftDeleteMoveToTrash:
    """TC-5: move_to_trash moves blobs to trash; original location 404s; idempotent.

    Covers PRD §7 AC-6.
    """

    def test_move_to_trash_populates_trash_bucket(self) -> None:
        svc, _fake = _make_service()
        svc.write_bundle(
            account_id="acc1",
            skill_id="sk001",
            version=1,
            skill_md_bytes=_SAMPLE_SKILL_MD,
            files=[("references/style.md", _SAMPLE_REF)],
            frontmatter=_SAMPLE_FRONTMATTER,
            created_by="user1",
        )
        svc.move_to_trash("acc1", "sk001")

        primary = _fake.bucket("kene-skills-development")
        trash = _fake.bucket("kene-skills-development-trash")

        # All original blobs should be gone from the primary.
        skill_blobs_in_primary = [
            name for name in primary._store if name.startswith("accounts/acc1/sk001/")
        ]
        assert skill_blobs_in_primary == [], (
            f"Primary still has blobs: {skill_blobs_in_primary}"
        )

        # Trash bucket should have the same paths.
        expected_trash = {
            "accounts/acc1/sk001/1/SKILL.md",
            "accounts/acc1/sk001/1/references/style.md",
            "accounts/acc1/sk001/1/.manifest.json",
        }
        assert set(trash._store.keys()) == expected_trash

    def test_move_to_trash_original_read_returns_none(self) -> None:
        svc, _fake = _make_service()
        svc.write_bundle(
            account_id="acc1",
            skill_id="sk001",
            version=1,
            skill_md_bytes=_SAMPLE_SKILL_MD,
            files=[],
            frontmatter=_SAMPLE_FRONTMATTER,
            created_by="user1",
        )
        svc.move_to_trash("acc1", "sk001")
        # The manifest lru_cache still holds the old manifest (immutable-version
        # guarantee), so SKILL.md appears in the manifest. The underlying GCS
        # blob is gone, so download_as_bytes raises → read_file returns None →
        # read_skill_md propagates as FileNotFoundError.
        assert svc.read_file("acc1", "sk001", 1, "SKILL.md") is None
        with pytest.raises(FileNotFoundError):
            svc.read_skill_md("acc1", "sk001", 1)

    def test_move_to_trash_idempotent(self) -> None:
        svc, _fake = _make_service()
        svc.write_bundle(
            account_id="acc1",
            skill_id="sk001",
            version=1,
            skill_md_bytes=_SAMPLE_SKILL_MD,
            files=[],
            frontmatter=_SAMPLE_FRONTMATTER,
            created_by="user1",
        )
        svc.move_to_trash("acc1", "sk001")
        # Second call on the same prefix should not raise.
        svc.move_to_trash("acc1", "sk001")


class TestDeleteAccountPrefix:
    """TC-6: delete_account_prefix deletes all blobs for the account."""

    def test_deletes_all_account_blobs(self) -> None:
        svc, _fake = _make_service()
        # Write two skills under the same account.
        svc.write_bundle(
            account_id="acc1",
            skill_id="sk001",
            version=1,
            skill_md_bytes=_SAMPLE_SKILL_MD,
            files=[("references/style.md", _SAMPLE_REF)],
            frontmatter=_SAMPLE_FRONTMATTER,
            created_by="user1",
        )
        svc.write_bundle(
            account_id="acc1",
            skill_id="sk002",
            version=1,
            skill_md_bytes=_SAMPLE_SKILL_MD,
            files=[("assets/logo.png", _SAMPLE_ASSET)],
            frontmatter=_SAMPLE_FRONTMATTER,
            created_by="user1",
        )
        primary = _fake.bucket("kene-skills-development")
        total_blobs_before = len(
            [name for name in primary._store if name.startswith("accounts/acc1/")]
        )
        count = svc.delete_account_prefix("acc1")
        assert count == total_blobs_before
        remaining = [
            name for name in primary._store if name.startswith("accounts/acc1/")
        ]
        assert remaining == []

    def test_does_not_delete_other_accounts(self) -> None:
        svc, _fake = _make_service()
        svc.write_bundle(
            account_id="acc1",
            skill_id="sk001",
            version=1,
            skill_md_bytes=_SAMPLE_SKILL_MD,
            files=[],
            frontmatter=_SAMPLE_FRONTMATTER,
            created_by="user1",
        )
        svc.write_bundle(
            account_id="acc2",
            skill_id="sk_other",
            version=1,
            skill_md_bytes=_SAMPLE_SKILL_MD,
            files=[],
            frontmatter=_SAMPLE_FRONTMATTER,
            created_by="user2",
        )
        svc.delete_account_prefix("acc1")
        primary = _fake.bucket("kene-skills-development")
        acc2_blobs = [
            name for name in primary._store if name.startswith("accounts/acc2/")
        ]
        assert acc2_blobs  # acc2 untouched


class TestManifestGateBeatsS3SyntacticGate:
    """TC-7: a syntactically safe path not in the manifest returns None."""

    def test_path_not_in_manifest_returns_none(self) -> None:
        svc, _fake = _make_service()
        svc.write_bundle(
            account_id="acc1",
            skill_id="sk001",
            version=1,
            skill_md_bytes=_SAMPLE_SKILL_MD,
            files=[("references/style.md", _SAMPLE_REF)],
            frontmatter=_SAMPLE_FRONTMATTER,
            created_by="user1",
        )
        # "references/other.md" passes safe_rel_path but was never uploaded.
        result = svc.read_file("acc1", "sk001", 1, "references/other.md")
        assert result is None


class TestReadSkillMd:
    """TC-8: read_skill_md returns the SKILL.md bytes."""

    def test_read_skill_md_returns_bytes(self) -> None:
        svc, _fake = _make_service()
        svc.write_bundle(
            account_id="acc1",
            skill_id="sk001",
            version=1,
            skill_md_bytes=_SAMPLE_SKILL_MD,
            files=[],
            frontmatter=_SAMPLE_FRONTMATTER,
            created_by="user1",
        )
        result = svc.read_skill_md("acc1", "sk001", 1)
        assert result == _SAMPLE_SKILL_MD

    def test_read_skill_md_raises_when_missing(self) -> None:
        svc, _fake = _make_service()
        with pytest.raises(FileNotFoundError):
            svc.read_skill_md("acc1", "nonexistent-skill", 1)


class TestVersionedPrefixes:
    """Covers PRD §7 AC-5: PUT creates versioned prefix alongside previous one."""

    def test_two_versions_coexist(self) -> None:
        svc, _fake = _make_service()
        v1_content = b"version 1 content"
        v2_content = b"version 2 content"
        svc.write_bundle(
            account_id="acc1",
            skill_id="sk001",
            version=1,
            skill_md_bytes=v1_content,
            files=[],
            frontmatter=_SAMPLE_FRONTMATTER,
            created_by="user1",
        )
        svc.write_bundle(
            account_id="acc1",
            skill_id="sk001",
            version=2,
            skill_md_bytes=v2_content,
            files=[],
            frontmatter=_SAMPLE_FRONTMATTER,
            created_by="user1",
        )
        primary = _fake.bucket("kene-skills-development")
        assert "accounts/acc1/sk001/1/SKILL.md" in primary._store
        assert "accounts/acc1/sk001/2/SKILL.md" in primary._store

        # Clearing the manifest cache to re-read from fake storage.
        svc._manifest_cache.clear()
        assert svc.read_skill_md("acc1", "sk001", 1) == v1_content
        assert svc.read_skill_md("acc1", "sk001", 2) == v2_content


class TestWriteBundleValidation:
    """Edge cases for write_bundle input validation."""

    def test_rejects_path_under_unknown_directory(self) -> None:
        svc, _ = _make_service()
        with pytest.raises(ValueError, match="not under one of"):
            svc.write_bundle(
                account_id="acc1",
                skill_id="sk001",
                version=1,
                skill_md_bytes=_SAMPLE_SKILL_MD,
                files=[("unknown_dir/file.txt", b"data")],
                frontmatter=_SAMPLE_FRONTMATTER,
                created_by="user1",
            )

    def test_rejects_reserved_filename_manifest(self) -> None:
        svc, _ = _make_service()
        with pytest.raises(ValueError, match="reserved"):
            svc.write_bundle(
                account_id="acc1",
                skill_id="sk001",
                version=1,
                skill_md_bytes=_SAMPLE_SKILL_MD,
                files=[(".manifest.json", b"{}")],
                frontmatter=_SAMPLE_FRONTMATTER,
                created_by="user1",
            )

    def test_empty_files_list_succeeds(self) -> None:
        svc, _fake = _make_service()
        result = svc.write_bundle(
            account_id="acc1",
            skill_id="sk001",
            version=1,
            skill_md_bytes=_SAMPLE_SKILL_MD,
            files=[],
            frontmatter=_SAMPLE_FRONTMATTER,
            created_by="user1",
        )
        assert result.version == 1
        assert len(result.file_manifest) == 1  # just SKILL.md
        assert result.file_manifest[0].rel_path == "SKILL.md"


class TestMoveToTrashRewriteAtomicity:
    """AC-6: source blobs are preserved when a rewrite fails mid-way.

    Covers the rewrite-all-then-delete ordering guarantee: if any rewrite
    raises, the delete phase must not run and every source blob must still
    be present in the primary bucket.
    """

    def test_rewrite_failure_preserves_source_blobs(self) -> None:
        svc, _fake = _make_service()
        svc.write_bundle(
            account_id="acc1",
            skill_id="sk001",
            version=1,
            skill_md_bytes=_SAMPLE_SKILL_MD,
            files=[("references/style.md", _SAMPLE_REF)],
            frontmatter=_SAMPLE_FRONTMATTER,
            created_by="user1",
        )
        primary = _fake.bucket("kene-skills-development")
        source_names = set(primary._store.keys())
        assert len(source_names) >= 2

        # Make the second blob's rewrite raise.
        blobs = list(primary._store.values())
        original_rewrite = blobs[1].rewrite

        def _failing_rewrite(dest: Any, **kwargs: Any) -> Any:
            raise Exception("simulated rewrite failure")

        blobs[1].rewrite = _failing_rewrite  # type: ignore[method-assign]

        with pytest.raises(Exception, match="simulated rewrite failure"):
            svc.move_to_trash("acc1", "sk001")

        # All source blobs must still exist in the primary bucket.
        for name in source_names:
            assert name in primary._store, (
                f"Source blob {name!r} was deleted despite rewrite failure"
            )

        blobs[1].rewrite = original_rewrite  # type: ignore[method-assign]


class TestStorageIdValidation:
    """account_id and skill_id are validated to prevent GCS prefix injection."""

    _INVALID_IDS: ClassVar[list[str]] = [
        "../other-account",
        "acc1/../acc2",
        "acc one",
        "acc/1",
        "acc.1",
        "",
        "a" * 129,  # exceeds max length
    ]

    @pytest.mark.parametrize("bad_id", _INVALID_IDS)
    def test_write_bundle_raises_for_invalid_account_id(self, bad_id: str) -> None:
        svc, _ = _make_service()
        with pytest.raises(ValueError, match="account_id"):
            svc.write_bundle(
                account_id=bad_id,
                skill_id="sk001",
                version=1,
                skill_md_bytes=_SAMPLE_SKILL_MD,
                files=[],
                frontmatter=_SAMPLE_FRONTMATTER,
                created_by="user1",
            )

    @pytest.mark.parametrize("bad_id", _INVALID_IDS)
    def test_write_bundle_raises_for_invalid_skill_id(self, bad_id: str) -> None:
        svc, _ = _make_service()
        with pytest.raises(ValueError, match="skill_id"):
            svc.write_bundle(
                account_id="acc1",
                skill_id=bad_id,
                version=1,
                skill_md_bytes=_SAMPLE_SKILL_MD,
                files=[],
                frontmatter=_SAMPLE_FRONTMATTER,
                created_by="user1",
            )

    def test_read_file_raises_for_invalid_account_id(self) -> None:
        svc, _ = _make_service()
        with pytest.raises(ValueError, match="account_id"):
            svc.read_file("acc/1", "sk001", 1, "SKILL.md")

    def test_move_to_trash_raises_for_invalid_account_id(self) -> None:
        svc, _ = _make_service()
        with pytest.raises(ValueError, match="account_id"):
            svc.move_to_trash("acc/../other", "sk001")

    def test_delete_account_prefix_raises_for_invalid_account_id(self) -> None:
        svc, _ = _make_service()
        with pytest.raises(ValueError, match="account_id"):
            svc.delete_account_prefix("acc/../other")

    def test_double_encoded_traversal_rejected_by_safe_rel_path(self) -> None:
        """Double-encoded %252e%252e is rejected at the rel_path layer."""
        svc, _fake = _make_service()
        svc.write_bundle(
            account_id="acc1",
            skill_id="sk001",
            version=1,
            skill_md_bytes=_SAMPLE_SKILL_MD,
            files=[],
            frontmatter=_SAMPLE_FRONTMATTER,
            created_by="user1",
        )
        result = svc.read_file("acc1", "sk001", 1, "%252e%252e/etc/passwd")
        assert result is None
