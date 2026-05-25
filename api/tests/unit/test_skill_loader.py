"""Unit tests for api/src/kene_api/services/skill_loader.py.

Covers:
  - Lazy L3 behaviour (Tasks 4): read_file is NOT called during load_skill;
    it IS called when the lazy dict is accessed; results are cached.
  - Frontmatter mapping, instructions extraction, version pinning, error paths (Task 5).

Firestore reads are stubbed with lightweight fakes — the loader only calls:
  - `db.collection(...).document(...).collection(...).document(...).get()`
  - `snap.exists`
  - `snap.to_dict()`
No stream/list_documents calls should ever appear.

GCS reads are stubbed via a MagicMock(spec=SkillStorageService).

PRD reference: SK-PRD-01 §8 test_skill_loader.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest
from src.kene_api.models.skill_models import (
    SkillFileEntry,
    SkillFrontmatter,
    SkillStatus,
    SkillVersion,
    SkillVisibility,
)
from src.kene_api.services.adk_skills_adapter import Script
from src.kene_api.services.skill_loader import (
    SkillCorruptError,
    SkillNotFoundError,
    load_skill,
)
from src.kene_api.services.skill_storage import SkillStorageService

# ---------------------------------------------------------------------------
# Helpers — build fake Firestore snapshots and Skill/SkillVersion dicts
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

_CHECKSUM = "a" * 64


def _make_skill_doc(skill_id: str = "sk-123", current_version: int = 1) -> dict:
    return {
        "skill_id": skill_id,
        "owner": {"account_id": "acc-abc", "shared_with_accounts": []},
        "name": "seo-checklist",
        "description": "An SEO checklist skill",
        "current_version": current_version,
        "visibility": SkillVisibility.PRIVATE.value,
        "status": SkillStatus.PUBLISHED.value,
        "source": {"type": "authored"},
        "has_scripts": False,
        "created_at": _NOW,
        "created_by": "user-1",
        "updated_at": _NOW,
        "updated_by": "user-1",
    }


def _make_version_doc(
    version: int = 1,
    frontmatter_extra: dict | None = None,
    manifest_extra: list[SkillFileEntry] | None = None,
) -> dict:
    base_fm: dict[str, Any] = {
        "name": "seo-checklist",
        "description": "An SEO checklist skill",
        "allowed-tools": None,
        "license": None,
        "compatibility": None,
        "metadata": None,
    }
    if frontmatter_extra:
        base_fm.update(frontmatter_extra)
    # Build SkillFrontmatter to get the correct serialisation.
    fm = SkillFrontmatter.model_validate(base_fm)
    manifest = [
        SkillFileEntry(
            rel_path="SKILL.md",
            kind="skill_md",
            size_bytes=10,
            checksum_sha256=_CHECKSUM,
        )
    ]
    if manifest_extra:
        manifest.extend(manifest_extra)
    sv = SkillVersion(
        version=version,
        gcs_prefix=f"accounts/acc-abc/sk-123/{version}/",
        frontmatter=fm,
        file_manifest=manifest,
        created_at=_NOW,
        created_by="user-1",
    )
    return sv.model_dump(mode="json")


def _make_db(
    skill_data: dict | None = None,
    version_data: dict | None = None,
    call_tracker: list | None = None,
    use_defaults: bool = True,
) -> MagicMock:
    """Return a minimal Firestore client mock.

    Tracks every `.get()` call in *call_tracker* if provided so tests can
    assert the loader never calls stream/list_documents.
    Pass `use_defaults=False` to serve None for both docs (missing skill case).
    """
    if use_defaults:
        if skill_data is None:
            skill_data = _make_skill_doc()
        if version_data is None:
            version_data = _make_version_doc()

    def _make_snap(data: dict | None) -> MagicMock:
        snap = MagicMock()
        snap.exists = data is not None
        snap.to_dict.return_value = data
        return snap

    class _Ref:
        def __init__(self, path: list[str]) -> None:
            self._path = path

        def collection(self, name: str) -> _Ref:
            return _Ref([*self._path, name])

        def document(self, name: str) -> _Ref:
            return _Ref([*self._path, name])

        def get(self) -> MagicMock:
            path_str = "/".join(self._path)
            if call_tracker is not None:
                call_tracker.append(("get", path_str))
            # Resolve to skill doc or version doc based on path presence.
            if "versions" in self._path:
                return _make_snap(version_data)
            else:
                return _make_snap(skill_data)

        def stream(self) -> list:
            raise AssertionError("loader must not call stream()")

        def list_documents(self) -> list:
            raise AssertionError("loader must not call list_documents()")

    db = MagicMock()
    db.collection.side_effect = lambda name: _Ref([name])
    return db


def _make_storage(
    skill_md_content: bytes = b"---\nname: seo-checklist\ndescription: An SEO checklist skill\n---\nHello body.",
    ref_content: bytes = b"ref bytes",
    asset_content: bytes = b"asset bytes",
    script_content: bytes = b"print('hello')",
) -> MagicMock:
    svc = MagicMock(spec=SkillStorageService)

    def _read_skill_md(account_id: str, skill_id: str, version: int) -> bytes:
        return skill_md_content

    def _read_file(
        account_id: str, skill_id: str, version: int, rel_path: str
    ) -> bytes | None:
        if rel_path.startswith("references/"):
            return ref_content
        if rel_path.startswith("assets/"):
            return asset_content
        if rel_path.startswith("scripts/"):
            return script_content
        return None

    svc.read_skill_md.side_effect = _read_skill_md
    svc.read_file.side_effect = _read_file
    return svc


# ---------------------------------------------------------------------------
# Task 4: Lazy L3 behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_skill_does_not_read_l3_during_load() -> None:
    """read_file must NOT be called during load_skill() itself."""
    version_data = _make_version_doc(
        manifest_extra=[
            SkillFileEntry(
                rel_path="references/style-guide.md",
                kind="reference",
                size_bytes=100,
                checksum_sha256=_CHECKSUM,
            )
        ]
    )
    db = _make_db(version_data=version_data)
    svc = _make_storage()

    await load_skill("acc-abc", "sk-123", firestore_client=db, storage_service=svc)

    # read_skill_md is called once for SKILL.md body (L2 eager).
    svc.read_skill_md.assert_called_once_with("acc-abc", "sk-123", 1)
    # read_file must NOT be called for any L3 path.
    svc.read_file.assert_not_called()


@pytest.mark.asyncio
async def test_lazy_reference_get_streams_from_gcs_on_demand() -> None:
    """get_reference() triggers exactly one read_file; second call is cached."""
    version_data = _make_version_doc(
        manifest_extra=[
            SkillFileEntry(
                rel_path="references/style-guide.md",
                kind="reference",
                size_bytes=100,
                checksum_sha256=_CHECKSUM,
            )
        ]
    )
    db = _make_db(version_data=version_data)
    svc = _make_storage()

    skill = await load_skill("acc-abc", "sk-123", firestore_client=db, storage_service=svc)

    assert svc.read_file.call_count == 0

    result = skill.resources.get_reference("style-guide.md")
    assert result == b"ref bytes"
    assert svc.read_file.call_count == 1

    # Second access — must use cached value.
    result2 = skill.resources.get_reference("style-guide.md")
    assert result2 == b"ref bytes"
    assert svc.read_file.call_count == 1  # still 1, no second call


@pytest.mark.asyncio
async def test_lazy_asset_get_streams_from_gcs_on_demand() -> None:
    """get_asset() triggers read_file only on first access."""
    version_data = _make_version_doc(
        manifest_extra=[
            SkillFileEntry(
                rel_path="assets/schema.json",
                kind="asset",
                size_bytes=50,
                checksum_sha256=_CHECKSUM,
            )
        ]
    )
    db = _make_db(version_data=version_data)
    svc = _make_storage()

    skill = await load_skill("acc-abc", "sk-123", firestore_client=db, storage_service=svc)
    assert svc.read_file.call_count == 0

    result = skill.resources.get_asset("schema.json")
    assert result == b"asset bytes"
    assert svc.read_file.call_count == 1


@pytest.mark.asyncio
async def test_lazy_script_get_returns_Script_wrapper() -> None:
    """get_script() returns a Script instance wrapping decoded UTF-8 bytes."""
    version_data = _make_version_doc(
        manifest_extra=[
            SkillFileEntry(
                rel_path="scripts/extract.py",
                kind="script",
                size_bytes=14,
                checksum_sha256=_CHECKSUM,
            )
        ]
    )
    db = _make_db(version_data=version_data)
    svc = _make_storage()

    skill = await load_skill("acc-abc", "sk-123", firestore_client=db, storage_service=svc)

    result = skill.resources.get_script("extract.py")
    assert isinstance(result, Script)
    assert result.src == "print('hello')"


@pytest.mark.asyncio
async def test_resources_keys_list_does_not_touch_gcs() -> None:
    """list_references/list_assets/list_scripts must never call read_file."""
    version_data = _make_version_doc(
        manifest_extra=[
            SkillFileEntry(
                rel_path="references/guide.md",
                kind="reference",
                size_bytes=20,
                checksum_sha256=_CHECKSUM,
            ),
            SkillFileEntry(
                rel_path="assets/img.png",
                kind="asset",
                size_bytes=30,
                checksum_sha256=_CHECKSUM,
            ),
            SkillFileEntry(
                rel_path="scripts/run.py",
                kind="script",
                size_bytes=10,
                checksum_sha256=_CHECKSUM,
            ),
        ]
    )
    db = _make_db(version_data=version_data)
    svc = _make_storage()

    skill = await load_skill("acc-abc", "sk-123", firestore_client=db, storage_service=svc)

    # All list/keys/iter/contains operations — zero GCS reads.
    assert skill.resources.list_references() == ["guide.md"]
    assert skill.resources.list_assets() == ["img.png"]
    assert skill.resources.list_scripts() == ["run.py"]
    assert "guide.md" in skill.resources.references
    assert len(skill.resources.assets) == 1

    svc.read_file.assert_not_called()


@pytest.mark.asyncio
async def test_lazy_resource_missing_path_returns_None() -> None:
    """get_reference on an unknown key returns None without calling read_file."""
    db = _make_db()
    svc = _make_storage()

    skill = await load_skill("acc-abc", "sk-123", firestore_client=db, storage_service=svc)

    result = skill.resources.get_reference("not-in-manifest.md")
    assert result is None
    svc.read_file.assert_not_called()


# ---------------------------------------------------------------------------
# Task 5: Frontmatter mapping, version pinning, error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_skill_frontmatter_matches_stored() -> None:
    """Frontmatter fields round-trip through the loader identically."""
    version_data = _make_version_doc(
        frontmatter_extra={
            "allowed-tools": "Read Bash(git:*)",
            "metadata": {"k": "v"},
        }
    )
    db = _make_db(version_data=version_data)
    svc = _make_storage()

    skill = await load_skill("acc-abc", "sk-123", firestore_client=db, storage_service=svc)

    assert skill.frontmatter.name == "seo-checklist"
    assert skill.frontmatter.description == "An SEO checklist skill"
    # allowed-tools alias → allowed_tools on the ADK Frontmatter
    assert skill.frontmatter.allowed_tools == "Read Bash(git:*)"
    assert skill.frontmatter.metadata == {"k": "v"}


@pytest.mark.asyncio
async def test_load_skill_instructions_is_body_after_frontmatter() -> None:
    """instructions equals the SKILL.md body after the frontmatter block."""
    skill_md = b"---\nname: seo-checklist\ndescription: An SEO checklist skill\n---\nHello body."
    db = _make_db()
    svc = _make_storage(skill_md_content=skill_md)

    skill = await load_skill("acc-abc", "sk-123", firestore_client=db, storage_service=svc)

    assert skill.instructions == "Hello body."


@pytest.mark.asyncio
async def test_load_skill_resolves_current_version_when_version_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When version=None, loader uses current_version from the skill doc."""
    call_tracker: list = []
    skill_data = _make_skill_doc(current_version=3)
    version_data = _make_version_doc(version=3)
    db = _make_db(skill_data=skill_data, version_data=version_data, call_tracker=call_tracker)
    svc = _make_storage()

    skill = await load_skill("acc-abc", "sk-123", firestore_client=db, storage_service=svc)

    # Verify the version doc read targeted path with "versions" and "3"
    version_gets = [
        path for op, path in call_tracker if op == "get" and "versions" in path
    ]
    assert len(version_gets) == 1
    assert "3" in version_gets[0]
    assert skill.frontmatter.name == "seo-checklist"


@pytest.mark.asyncio
async def test_load_skill_version_pinning() -> None:
    """version=1 reads the version 1 doc and lazy dicts use version=1 for GCS."""
    version_data_v1 = _make_version_doc(
        version=1,
        manifest_extra=[
            SkillFileEntry(
                rel_path="references/guide.md",
                kind="reference",
                size_bytes=20,
                checksum_sha256=_CHECKSUM,
            )
        ],
    )
    # Skill doc advertises current_version=3 but we pin to version=1.
    skill_data = _make_skill_doc(current_version=3)
    db = _make_db(skill_data=skill_data, version_data=version_data_v1)
    svc = _make_storage()

    skill = await load_skill(
        "acc-abc", "sk-123", version=1, firestore_client=db, storage_service=svc
    )

    # Trigger a lazy read to confirm version=1 is used.
    skill.resources.get_reference("guide.md")
    svc.read_file.assert_called_once_with("acc-abc", "sk-123", 1, "references/guide.md")


@pytest.mark.asyncio
async def test_load_skill_missing_skill_doc_raises_SkillNotFoundError() -> None:
    """load_skill raises SkillNotFoundError when the skill doc is absent."""
    db = _make_db(use_defaults=False)
    svc = _make_storage()

    with pytest.raises(SkillNotFoundError, match="skill_id"):
        await load_skill("acc-abc", "sk-missing", firestore_client=db, storage_service=svc)


@pytest.mark.asyncio
async def test_load_skill_missing_version_doc_raises_SkillNotFoundError() -> None:
    """load_skill raises SkillNotFoundError when the version doc is absent."""
    db = _make_db(skill_data=_make_skill_doc(), version_data=None, use_defaults=False)
    svc = _make_storage()

    with pytest.raises(SkillNotFoundError, match="version"):
        await load_skill("acc-abc", "sk-123", firestore_client=db, storage_service=svc)


@pytest.mark.asyncio
async def test_load_skill_missing_skill_md_raises_SkillCorruptError() -> None:
    """load_skill raises SkillCorruptError when SKILL.md is missing from GCS."""
    db = _make_db()
    svc = MagicMock(spec=SkillStorageService)
    svc.read_skill_md.side_effect = FileNotFoundError("SKILL.md missing")

    with pytest.raises(SkillCorruptError, match=r"SKILL\.md missing"):
        await load_skill("acc-abc", "sk-123", firestore_client=db, storage_service=svc)


@pytest.mark.asyncio
async def test_load_skill_does_not_walk_versions_subcollection() -> None:
    """Loader makes exactly two Firestore `.get()` calls — skill doc + version doc."""
    call_tracker: list = []
    db = _make_db(call_tracker=call_tracker)
    svc = _make_storage()

    await load_skill("acc-abc", "sk-123", firestore_client=db, storage_service=svc)

    get_calls = [op for op, _ in call_tracker if op == "get"]
    assert len(get_calls) == 2, f"Expected exactly 2 get() calls, got: {call_tracker}"


@pytest.mark.asyncio
async def test_load_skill_malformed_skill_md_raises_SkillCorruptError() -> None:
    """load_skill raises SkillCorruptError when SKILL.md has no frontmatter delimiter."""
    db = _make_db()
    svc = _make_storage(skill_md_content=b"This is just a body without any frontmatter.")

    with pytest.raises(SkillCorruptError, match="malformed"):
        await load_skill("acc-abc", "sk-123", firestore_client=db, storage_service=svc)


@pytest.mark.asyncio
async def test_load_skill_invalid_current_version_raises_SkillCorruptError() -> None:
    """load_skill raises SkillCorruptError when skill doc has invalid current_version."""
    skill_data = _make_skill_doc()
    skill_data["current_version"] = None  # simulate corrupt Firestore doc
    db = _make_db(skill_data=skill_data, version_data=_make_version_doc(), use_defaults=False)
    svc = _make_storage()

    with pytest.raises(SkillCorruptError, match="current_version"):
        await load_skill("acc-abc", "sk-123", firestore_client=db, storage_service=svc)
