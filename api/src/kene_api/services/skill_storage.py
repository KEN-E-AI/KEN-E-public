"""GCS storage service for skill bundles.

Owns:
- Writing a bundle to ``gs://kene-skills-{env}/accounts/{account_id}/{skill_id}/{version}/``
  with ``Cache-Control: no-cache``.
- Generating and persisting ``.manifest.json`` per version.
- Reading individual files (SKILL.md body, references, assets, scripts) under a
  stable rel-path API with manifest-backed validation.
- Moving a skill's prefix to the trash bucket on soft-delete.
- Deleting a whole account's prefix for the account-deletion sweep.

This is pure GCS plumbing — no Firestore, no auth, no ID allocation.

PRD reference: docs/design/components/skills/projects/SK-PRD-01-skills-backend.md §4, §5, §7
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from functools import lru_cache
from typing import Literal

from google.cloud import storage

from ..models.skill_models import SkillFileEntry, SkillFrontmatter, SkillVersion

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Files written by write_bundle that must not be supplied by callers.
_RESERVED_FILES: frozenset[str] = frozenset({"SKILL.md", ".manifest.json"})

# Map from first path segment (or full name for SKILL.md) to SkillFileEntry.kind
_KIND_MAP: dict[str, Literal["skill_md", "reference", "asset", "script"]] = {
    "SKILL.md": "skill_md",
    "references": "reference",
    "assets": "asset",
    "scripts": "script",
}

# ---------------------------------------------------------------------------
# Pure-function path safety (exported for use by the router and unit tests)
# ---------------------------------------------------------------------------


def safe_rel_path(rel_path: str) -> str | None:
    """Return the canonical relative path or ``None`` if it should be rejected.

    Rejects:
    - Empty string.
    - Leading ``/`` (absolute path).
    - Null bytes (``\\x00``).
    - Backslashes (mixed separators that could hide traversal on Windows).
    - Any ``%`` character — covers URL-encoded (``%2e``) and double-encoded
      (``%252e``) sequences that could decode to ``..`` after gateway processing.
    - Any path that contains ``..`` after ``os.path.normpath`` normalization.
    - Absolute Windows-style paths (e.g., ``C:\\...`` or ``//share/...``).

    Returns:
        The canonical POSIX-normalized rel_path on success, ``None`` on any
        rejection.
    """
    if not rel_path:
        return None

    # Null bytes are never valid in file paths.
    if "\x00" in rel_path:
        return None

    # Backslashes indicate mixed separators — reject rather than silently convert.
    if "\\" in rel_path:
        return None

    # Reject any percent sign — covers URL-encoded dots (%2e, %2E) and
    # double-encoded sequences (%252e) that could decode to traversal sequences
    # after gateway URL-decoding passes.
    if "%" in rel_path:
        return None

    # Leading slash → absolute path.
    if rel_path.startswith("/"):
        return None

    normalized = os.path.normpath(rel_path)

    # normpath on a POSIX system converts the empty string to "." — handle that
    # edge case (the empty-string guard above already fires, but be defensive).
    if normalized in (".", ""):
        return None

    # After normalization, reject if the result starts with ".." or contains a
    # ".." component (deep traversal like "a/../../b" normalizes to "../b").
    parts = normalized.split(os.sep)
    if any(part == ".." for part in parts):
        return None

    return normalized


_STORAGE_ID_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")


def _validate_storage_id(value: str, label: str) -> None:
    """Raise ``ValueError`` if *value* is unsafe as a GCS object-path segment.

    Prevents callers from injecting ``/``, ``..``, ``%``, or other traversal
    sequences into the ``accounts/{account_id}/{skill_id}/`` prefix.  Only
    alphanumeric characters, underscores, and hyphens are allowed.
    """
    if not _STORAGE_ID_RE.fullmatch(value):
        raise ValueError(
            f"{label} {value!r} contains characters not allowed in GCS object paths"
        )


# ---------------------------------------------------------------------------
# SkillStorageService
# ---------------------------------------------------------------------------


class SkillStorageService:
    """GCS layer for skill bundles.

    Constructor caches the ``storage.Client`` singleton; call
    ``get_skill_storage_service()`` for the FastAPI ``Depends()``-compatible
    singleton factory.
    """

    def __init__(
        self,
        project_id: str | None = None,
        environment: str | None = None,
    ) -> None:
        self._project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        env = (environment or os.getenv("ENVIRONMENT", "development")).lower()
        self.primary_bucket_name = f"kene-skills-{env}"
        self.trash_bucket_name = f"kene-skills-{env}-trash"
        self.client = storage.Client(project=self._project_id)
        # Instance-level manifest cache keyed by (account_id, skill_id, version).
        # Manifests are immutable per version so cache invalidation is not needed.
        # Using a plain dict avoids the B019 memory-leak risk of @lru_cache on a method.
        self._manifest_cache: dict[
            tuple[str, str, int], list[SkillFileEntry] | None
        ] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _primary_bucket(self) -> storage.Bucket:
        return self.client.bucket(self.primary_bucket_name)

    def _trash_bucket(self) -> storage.Bucket:
        return self.client.bucket(self.trash_bucket_name)

    @staticmethod
    def _object_prefix(account_id: str, skill_id: str, version: int) -> str:
        return f"accounts/{account_id}/{skill_id}/{version}/"

    @staticmethod
    def _account_prefix(account_id: str) -> str:
        return f"accounts/{account_id}/"

    @staticmethod
    def _skill_prefix(account_id: str, skill_id: str) -> str:
        return f"accounts/{account_id}/{skill_id}/"

    @staticmethod
    def _infer_kind(
        rel_path: str,
    ) -> Literal["skill_md", "reference", "asset", "script"]:
        """Infer the SkillFileEntry.kind from a relative path.

        Raises ``ValueError`` if the path is not under a recognised directory.
        """
        if rel_path == "SKILL.md":
            return "skill_md"
        first_segment = rel_path.split("/")[0]
        kind = _KIND_MAP.get(first_segment)
        if kind is None:
            raise ValueError(
                f"rel_path {rel_path!r} is not under one of "
                f"references/, assets/, scripts/, or SKILL.md"
            )
        return kind

    @staticmethod
    def _checksum(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _upload_blob(
        self,
        bucket: storage.Bucket,
        blob_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Upload *data* to *blob_name* in *bucket* with Cache-Control: no-cache."""
        blob = bucket.blob(blob_name)
        blob.cache_control = "no-cache"
        blob.upload_from_string(data, content_type=content_type)

    # ------------------------------------------------------------------
    # Manifest cache — per (account_id, skill_id, version) tuple.
    # Manifests are immutable per version so caching is safe.
    # ------------------------------------------------------------------

    def _load_manifest(
        self,
        account_id: str,
        skill_id: str,
        version: int,
    ) -> list[SkillFileEntry] | None:
        """Read and parse ``.manifest.json`` for the given version.

        Absent-blob results are cached (a missing version is permanent).
        Parse failures are NOT cached so a re-written manifest can be picked
        up on the next call without a process restart.
        Returns ``None`` if the manifest blob does not exist or cannot be parsed.
        """
        cache_key = (account_id, skill_id, version)
        if cache_key in self._manifest_cache:
            return self._manifest_cache[cache_key]

        prefix = self._object_prefix(account_id, skill_id, version)
        manifest_name = f"{prefix}.manifest.json"
        bucket = self._primary_bucket()
        blob = bucket.blob(manifest_name)
        result: list[SkillFileEntry] | None
        try:
            raw = blob.download_as_bytes()
        except Exception:
            result = None
            self._manifest_cache[cache_key] = result
            return result
        try:
            data = json.loads(raw)
            result = [SkillFileEntry(**entry) for entry in data["files"]]
        except Exception:
            logger.error(
                "manifest_parse_failed",
                extra={
                    "account_id": account_id,
                    "skill_id": skill_id,
                    "version": version,
                },
            )
            # Do not cache — a re-written manifest should be readable on retry.
            return None
        self._manifest_cache[cache_key] = result
        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write_bundle(
        self,
        *,
        account_id: str,
        skill_id: str,
        version: int,
        skill_md_bytes: bytes,
        files: list[tuple[str, bytes]],
        frontmatter: SkillFrontmatter,
        created_by: str,
        commit_message: str | None = None,
    ) -> SkillVersion:
        """Upload all files to the correct GCS prefix and write ``.manifest.json``.

        Note: if an upload raises mid-way (e.g. GCS 5xx), the already-uploaded
        blobs are left as orphans.  The caller should not retry with the same
        (skill_id, version) without first deleting the prefix.

        Args:
            account_id: Account that owns the skill.
            skill_id: UUID of the skill (stable across renames).
            version: Version number (monotonically increasing, starts at 1).
            skill_md_bytes: Raw bytes of the ``SKILL.md`` file.
            files: List of ``(rel_path, content)`` tuples for additional files.
                   Each ``rel_path`` must pass :func:`safe_rel_path` and be under
                   one of ``references/``, ``assets/``, or ``scripts/``.
            frontmatter: Parsed frontmatter (used to build the returned SkillVersion).
            created_by: User ID of the author (for SkillVersion.created_by).
            commit_message: Optional human-readable note about this version.

        Returns:
            A ``SkillVersion`` populated with the upload results.

        Raises:
            ValueError: If any ``rel_path`` in *files* is invalid or uses a
                        reserved name, or if *account_id* / *skill_id* contain
                        disallowed characters.
        """
        _validate_storage_id(account_id, "account_id")
        _validate_storage_id(skill_id, "skill_id")
        prefix = self._object_prefix(account_id, skill_id, version)
        bucket = self._primary_bucket()
        manifest_entries: list[SkillFileEntry] = []

        # --- Upload SKILL.md ---
        skill_md_blob_name = f"{prefix}SKILL.md"
        self._upload_blob(bucket, skill_md_blob_name, skill_md_bytes, "text/markdown")
        manifest_entries.append(
            SkillFileEntry(
                rel_path="SKILL.md",
                kind="skill_md",
                size_bytes=len(skill_md_bytes),
                checksum_sha256=self._checksum(skill_md_bytes),
            )
        )

        # --- Upload additional files ---
        for rel_path, content in files:
            # Validate and normalise the path.
            canonical = safe_rel_path(rel_path)
            if canonical is None:
                raise ValueError(
                    f"Invalid rel_path {rel_path!r}: failed path-traversal safety check"
                )
            if canonical in _RESERVED_FILES:
                raise ValueError(
                    f"rel_path {rel_path!r} is a reserved filename and cannot be supplied by callers"
                )
            kind = self._infer_kind(canonical)
            blob_name = f"{prefix}{canonical}"
            self._upload_blob(bucket, blob_name, content)
            manifest_entries.append(
                SkillFileEntry(
                    rel_path=canonical,
                    kind=kind,
                    size_bytes=len(content),
                    checksum_sha256=self._checksum(content),
                )
            )

        # --- Write .manifest.json ---
        manifest_data = {"files": [entry.model_dump() for entry in manifest_entries]}
        manifest_bytes = json.dumps(manifest_data, indent=2).encode()
        manifest_blob_name = f"{prefix}.manifest.json"
        self._upload_blob(
            bucket, manifest_blob_name, manifest_bytes, "application/json"
        )

        return SkillVersion(
            version=version,
            gcs_prefix=prefix,
            frontmatter=frontmatter,
            file_manifest=manifest_entries,
            created_at=datetime.now(timezone.utc),
            created_by=created_by,
            commit_message=commit_message,
        )

    def read_file(
        self,
        account_id: str,
        skill_id: str,
        version: int,
        rel_path: str,
    ) -> bytes | None:
        """Return the bytes for *rel_path* within a versioned skill bundle.

        Validates the path in two layers:

        1. :func:`safe_rel_path` — syntactic check (rejects traversal).
        2. Manifest membership — checks that *rel_path* was part of this version's
           bundle (rejects paths that look safe but were never uploaded).

        Returns ``None`` if either check fails or the blob is absent.
        """
        _validate_storage_id(account_id, "account_id")
        _validate_storage_id(skill_id, "skill_id")
        canonical = safe_rel_path(rel_path)
        if canonical is None:
            return None

        manifest = self._load_manifest(account_id, skill_id, version)
        if manifest is None:
            return None

        manifest_paths = {entry.rel_path for entry in manifest}
        if canonical not in manifest_paths:
            return None

        prefix = self._object_prefix(account_id, skill_id, version)
        blob_name = f"{prefix}{canonical}"
        bucket = self._primary_bucket()
        blob = bucket.blob(blob_name)
        try:
            return blob.download_as_bytes()
        except Exception:
            return None

    def read_skill_md(
        self,
        account_id: str,
        skill_id: str,
        version: int,
    ) -> bytes:
        """Return the raw bytes of the ``SKILL.md`` file.

        Shortcut for the most common read.  Raises :exc:`FileNotFoundError`
        rather than returning ``None`` because a missing ``SKILL.md`` means
        the version is corrupt — not a normal user-visible 404.
        """
        data = self.read_file(account_id, skill_id, version, "SKILL.md")
        if data is None:
            raise FileNotFoundError(
                f"SKILL.md missing for account={account_id} skill={skill_id} version={version}"
            )
        return data

    def move_to_trash(self, account_id: str, skill_id: str) -> None:
        """Move every blob under the skill's prefix to the trash bucket.

        Uses ``blob.rewrite`` (server-side copy) to avoid egress charges.
        Deletes the source blobs only after all rewrites succeed.

        Idempotent: if the prefix has no blobs (already moved), returns
        without error.

        Partial-failure ordering: rewrite all → only then delete sources.
        If a rewrite fails mid-way, the source is still intact and the
        operation can safely be retried.
        """
        _validate_storage_id(account_id, "account_id")
        _validate_storage_id(skill_id, "skill_id")
        skill_prefix = self._skill_prefix(account_id, skill_id)
        primary = self._primary_bucket()
        trash = self._trash_bucket()

        blobs_to_move = list(self.client.list_blobs(primary, prefix=skill_prefix))
        if not blobs_to_move:
            return

        # Rewrite all blobs to trash first.  blob.rewrite is paginated for
        # objects > 5 MB — loop until the continuation token is None.
        for blob in blobs_to_move:
            dest_blob = trash.blob(blob.name)
            dest_blob.cache_control = "no-cache"
            token = None
            while True:
                token, _, _ = blob.rewrite(dest_blob, token=token)
                if token is None:
                    break

        # Only delete sources once all rewrites have succeeded.
        for blob in blobs_to_move:
            try:
                blob.delete()
            except Exception:
                logger.warning(
                    "move_to_trash_delete_failed",
                    extra={
                        "account_id": account_id,
                        "skill_id": skill_id,
                        "blob_name": blob.name,
                    },
                )

    def delete_account_prefix(self, account_id: str) -> int:
        """Delete every blob under ``accounts/{account_id}/`` in the primary bucket.

        Returns the number of blobs deleted.  Used by the account-deletion sweep
        (SK-18).

        Note: callers in the account-deletion flow should run this in
        ``asyncio.to_thread`` to avoid blocking the event loop, matching the
        pattern in ``routers/accounts.py``.

        Note: this only sweeps the primary bucket.  Skills soft-deleted before
        account deletion remain in the trash bucket until the lifecycle rule
        fires.
        """
        _validate_storage_id(account_id, "account_id")
        account_prefix = self._account_prefix(account_id)
        primary = self._primary_bucket()
        blobs = list(self.client.list_blobs(primary, prefix=account_prefix))
        count = 0
        for blob in blobs:
            try:
                blob.delete()
                count += 1
            except Exception:
                logger.warning(
                    "delete_account_prefix_blob_failed",
                    extra={"account_id": account_id, "blob_name": blob.name},
                )
        return count


# ---------------------------------------------------------------------------
# FastAPI dependency injection factory
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_skill_storage_service() -> SkillStorageService:
    """Return the process-wide ``SkillStorageService`` singleton.

    Wire into FastAPI routes via ``Depends(get_skill_storage_service)``.
    Mirrors ``dependencies.get_firestore_client`` (``@lru_cache(maxsize=1)``).
    """
    return SkillStorageService()
