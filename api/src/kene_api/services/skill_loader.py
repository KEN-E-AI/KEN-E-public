"""Skill loader — converts stored skill bundles into ADK `Skill` objects.

Entry point for SK-PRD-02's `_build_skill_toolset`. Reads from Firestore
(metadata + version doc) and GCS (SKILL.md body + L3 files on demand).

Progressive disclosure levels:
  L1 — frontmatter: materialized eagerly from the stored SkillVersion.frontmatter.
  L2 — instructions: SKILL.md body decoded from GCS on each load_skill() call.
  L3 — resources: lazy dict subclasses that defer GCS reads to first access.

Account scoping: `account_id` is always required. Skills live under
`accounts/{account_id}/skills/{skill_id}` (Shape B per DM-PRD-00) and GCS
prefix `accounts/{account_id}/{skill_id}/{version}/`.

PRD reference: docs/design/components/skills/projects/SK-PRD-01-skills-backend.md §5, §7 AC-11, §8, §9
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.cloud import firestore

from ..dependencies import get_firestore_client
from ..models.skill_models import SkillFrontmatter, SkillVersion
from .adk_skills_adapter import Frontmatter, Resources, Script, Skill
from .skill_storage import (
    SkillStorageService,
    _validate_storage_id,
    get_skill_storage_service,
)
from .skill_validator import parse_frontmatter

logger = logging.getLogger(__name__)

__all__ = [
    "SkillCorruptError",
    "SkillNotFoundError",
    "load_skill",
]


# ---------------------------------------------------------------------------
# Module-local exceptions
# ---------------------------------------------------------------------------


class SkillNotFoundError(Exception):
    """Raised when the skill doc or requested version doc does not exist in Firestore."""


class SkillCorruptError(Exception):
    """Raised when SKILL.md is missing from GCS (the version is corrupt)."""


# ---------------------------------------------------------------------------
# Lazy resource dicts — L3 on-demand GCS reads
# ---------------------------------------------------------------------------


class _LazyResourceDict(dict):
    """dict subclass whose values are fetched from GCS on first access.

    Keys are populated at construction time from the file manifest so
    `keys()`, `__contains__`, and `__iter__` work without any GCS I/O.
    Values are fetched from GCS once and cached per instance thereafter.

    Strips the directory prefix from manifest rel_paths so keys match ADK's
    `_load_dir` convention (e.g., `references/style-guide.md` → `style-guide.md`).
    """

    # `_prefix` e.g. "references/" — stripped from manifest paths to form dict keys
    _prefix: str
    _storage_service: SkillStorageService
    _account_id: str
    _skill_id: str
    _version: int
    # Map from stripped key back to the full rel_path used by SkillStorageService.read_file
    _rel_path_map: dict[str, str]
    # Per-instance GCS read cache — avoids re-fetching within one agent turn
    _cache: dict[str, bytes | None]

    def __init__(
        self,
        *,
        storage_service: SkillStorageService,
        account_id: str,
        skill_id: str,
        version: int,
        manifest_entries: list[str],
        prefix: str,
    ) -> None:
        rel_path_map: dict[str, str] = {}
        for rel_path in manifest_entries:
            if not rel_path.startswith(prefix):
                logger.error(
                    "manifest_prefix_mismatch",
                    extra={"rel_path": rel_path, "expected_prefix": prefix},
                )
                continue
            stripped = rel_path[len(prefix) :]
            rel_path_map[stripped] = rel_path
        # Populate the underlying dict with key→None placeholders so all
        # `dict` introspection methods work without GCS I/O.
        super().__init__(dict.fromkeys(rel_path_map))
        self._prefix = prefix
        self._storage_service = storage_service
        self._account_id = account_id
        self._skill_id = skill_id
        self._version = version
        self._rel_path_map = rel_path_map
        self._cache = {}

    def _fetch(self, stripped_key: str) -> bytes | None:
        """Fetch bytes from GCS, caching the result on the instance."""
        if stripped_key in self._cache:
            return self._cache[stripped_key]
        rel_path = self._rel_path_map.get(stripped_key)
        if rel_path is None:
            self._cache[stripped_key] = None
            return None
        data = self._storage_service.read_file(
            self._account_id, self._skill_id, self._version, rel_path
        )
        self._cache[stripped_key] = data
        return data

    def __getitem__(self, key: str) -> bytes:
        if key not in self._rel_path_map:
            raise KeyError(key)
        data = self._fetch(key)
        if data is None:
            raise KeyError(key)
        return data

    def get(self, key: str, default: bytes | None = None) -> bytes | None:  # type: ignore[override]
        if key not in self._rel_path_map:
            return default
        data = self._fetch(key)
        return data if data is not None else default


class _LazyScriptDict(_LazyResourceDict):
    """Like _LazyResourceDict but wraps returned bytes in `Script(src=...)`.

    Caches decoded Script objects so repeated access avoids re-decoding.
    """

    _script_cache: dict[str, Script]

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._script_cache = {}

    def _decode(self, key: str, raw: bytes) -> Script:
        if key not in self._script_cache:
            try:
                self._script_cache[key] = Script(src=raw.decode("utf-8"))
            except UnicodeDecodeError:
                logger.error(
                    "script_decode_failed",
                    extra={
                        "account_id": self._account_id,
                        "skill_id": self._skill_id,
                        "version": self._version,
                        "key": key,
                    },
                )
                raise KeyError(key) from None
        return self._script_cache[key]

    def __getitem__(self, key: str) -> Script:  # type: ignore[override]
        raw = super().__getitem__(key)
        return self._decode(key, raw)

    def get(self, key: str, default: Script | None = None) -> Script | None:  # type: ignore[override]
        raw = _LazyResourceDict.get(self, key)
        if raw is None:
            return default
        try:
            return self._decode(key, raw)
        except KeyError:
            return default


# ---------------------------------------------------------------------------
# Firestore helpers — run sync client in a thread to avoid blocking the loop
# ---------------------------------------------------------------------------


async def _get_skill_doc(
    db: firestore.Client,
    account_id: str,
    skill_id: str,
) -> dict | None:
    """Return the Skill Firestore document dict or None if missing."""

    def _fetch() -> dict | None:
        ref = (
            db.collection("accounts")
            .document(account_id)
            .collection("skills")
            .document(skill_id)
        )
        snap = ref.get()
        if not snap.exists:
            return None
        return snap.to_dict()

    return await asyncio.to_thread(_fetch)


async def _get_version_doc(
    db: firestore.Client,
    account_id: str,
    skill_id: str,
    version: int,
) -> dict | None:
    """Return the SkillVersion Firestore document dict or None if missing."""

    def _fetch() -> dict | None:
        ref = (
            db.collection("accounts")
            .document(account_id)
            .collection("skills")
            .document(skill_id)
            .collection("versions")
            .document(str(version))
        )
        snap = ref.get()
        if not snap.exists:
            return None
        return snap.to_dict()

    return await asyncio.to_thread(_fetch)


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------


async def load_skill(
    account_id: str,
    skill_id: str,
    *,
    version: int | None = None,
    firestore_client: firestore.Client | None = None,
    storage_service: SkillStorageService | None = None,
) -> Skill:
    """Load a skill from Firestore + GCS and return an ADK `Skill` object.

    L1 (frontmatter) and L2 (instructions body) are materialized eagerly.
    L3 resources are returned as lazy dict subclasses that defer GCS reads
    to first access — SKILL.md is the only GCS read performed here.

    Args:
        account_id: Required. Resolves the Firestore subcollection
            (`accounts/{account_id}/skills`) and GCS prefix
            (`accounts/{account_id}/{skill_id}/{version}/`).
        skill_id: Firestore document ID for the skill.
        version: Specific version to load. Defaults to `Skill.current_version`.
        firestore_client: Injected for unit tests; production callers pass None.
        storage_service: Injected for unit tests; production callers pass None.

    Returns:
        ADK `Skill` with:
          - `frontmatter` populated from the stored `SkillVersion.frontmatter`
          - `instructions` set to the SKILL.md body (after the frontmatter block)
          - `resources.references`, `.assets`, `.scripts` as lazy dicts

    Raises:
        SkillNotFoundError: If the skill doc or version doc does not exist.
        SkillCorruptError: If SKILL.md is missing from GCS.
    """
    _validate_storage_id(account_id, "account_id")
    _validate_storage_id(skill_id, "skill_id")

    db = firestore_client if firestore_client is not None else get_firestore_client()
    svc = storage_service if storage_service is not None else get_skill_storage_service()

    skill_data = await _get_skill_doc(db, account_id, skill_id)
    if skill_data is None:
        raise SkillNotFoundError(
            f"Skill not found: account_id={account_id!r} skill_id={skill_id!r}"
        )

    if version is not None:
        resolved_version = version
    else:
        raw_version = skill_data.get("current_version")
        if not isinstance(raw_version, int) or raw_version < 1:
            raise SkillCorruptError(
                f"skill doc has invalid current_version={raw_version!r}"
                f" account_id={account_id!r} skill_id={skill_id!r}"
            )
        resolved_version = raw_version

    version_data = await _get_version_doc(db, account_id, skill_id, resolved_version)
    if version_data is None:
        raise SkillNotFoundError(
            f"Version not found: account_id={account_id!r} skill_id={skill_id!r}"
            f" version={resolved_version}"
        )

    skill_version = SkillVersion.model_validate(version_data)
    stored_fm: SkillFrontmatter = skill_version.frontmatter

    try:
        skill_md_bytes = await asyncio.to_thread(
            svc.read_skill_md, account_id, skill_id, resolved_version
        )
    except FileNotFoundError as exc:
        raise SkillCorruptError(
            f"SKILL.md missing for account_id={account_id!r} skill_id={skill_id!r}"
            f" version={resolved_version}"
        ) from exc

    parsed = parse_frontmatter(skill_md_bytes)
    if parsed.issues:
        raise SkillCorruptError(
            f"SKILL.md is malformed for account_id={account_id!r} skill_id={skill_id!r}"
            f" version={resolved_version}: {parsed.issues[0].code}"
        )
    instructions = parsed.body.decode("utf-8").lstrip("\n")

    # model_dump with by_alias=True converts allowed_tools → "allowed-tools"
    # so model_validate on the ADK Frontmatter picks it up via its alias.
    fm_dict = stored_fm.model_dump(by_alias=True, exclude_none=True)
    adk_frontmatter = Frontmatter.model_validate(fm_dict)

    manifest = skill_version.file_manifest

    ref_paths = [e.rel_path for e in manifest if e.kind == "reference"]
    asset_paths = [e.rel_path for e in manifest if e.kind == "asset"]
    script_paths = [e.rel_path for e in manifest if e.kind == "script"]

    lazy_refs = _LazyResourceDict(
        storage_service=svc,
        account_id=account_id,
        skill_id=skill_id,
        version=resolved_version,
        manifest_entries=ref_paths,
        prefix="references/",
    )
    lazy_assets = _LazyResourceDict(
        storage_service=svc,
        account_id=account_id,
        skill_id=skill_id,
        version=resolved_version,
        manifest_entries=asset_paths,
        prefix="assets/",
    )
    lazy_scripts = _LazyScriptDict(
        storage_service=svc,
        account_id=account_id,
        skill_id=skill_id,
        version=resolved_version,
        manifest_entries=script_paths,
        prefix="scripts/",
    )

    # Use model_construct to bypass Pydantic's copy-into-plain-dict coercion
    # so our lazy subclasses survive field assignment intact.
    resources = Resources.model_construct(
        references=lazy_refs,
        assets=lazy_assets,
        scripts=lazy_scripts,
    )

    return Skill.model_construct(
        frontmatter=adk_frontmatter,
        instructions=instructions,
        resources=resources,
    )
