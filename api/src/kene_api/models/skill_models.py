"""Pydantic models for the Skills component.

Spec: docs/design/components/skills/projects/SK-PRD-01-skills-backend.md §4
      docs/design/components/skills/README.md §2.4, §7
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "MAX_ALLOWED_TOOLS_LEN",
    "MAX_BUNDLE_FILES",
    "MAX_COMPATIBILITY_LEN",
    "MAX_DESCRIPTION_LEN",
    "MAX_METADATA_KEYS",
    "MAX_METADATA_KEY_LEN",
    "MAX_METADATA_VALUE_LEN",
    "MAX_NAME_LEN",
    "MAX_REFERENCE_FILES",
    "MAX_REFERENCE_FILE_BYTES",
    "MAX_SKILL_MD_BYTES",
    "MAX_TOTAL_BUNDLE_BYTES",
    "SKILL_NAME_PATTERN",
    "Skill",
    "SkillFileEntry",
    "SkillFrontmatter",
    "SkillOwner",
    "SkillSource",
    "SkillStatus",
    "SkillVersion",
    "SkillVisibility",
]

# ---------------------------------------------------------------------------
# Validation constants — imported by skill_validator.py and skill_storage.py
# ---------------------------------------------------------------------------

SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

MAX_NAME_LEN: int = 64
MAX_DESCRIPTION_LEN: int = 1024
MAX_COMPATIBILITY_LEN: int = 500
MAX_SKILL_MD_BYTES: int = 5_000
MAX_REFERENCE_FILE_BYTES: int = 100_000
MAX_TOTAL_BUNDLE_BYTES: int = 2_000_000
# Per PRD §4 / §7, MAX_REFERENCE_FILES caps `references/` only — `assets/` and
# `scripts/` have no per-directory count cap (they are bounded by the total-bundle
# byte cap). Kind-aware enforcement lives in `skill_validator.py`; the model layer
# does not enforce it because `file_manifest` mixes all four kinds.
MAX_REFERENCE_FILES: int = 20

# Sanity ceiling on the full `file_manifest` list — protects model construction
# from a corrupt Firestore doc with an absurd entry count. Well above any
# plausible skill (SKILL.md + 20 references + tens of assets/scripts).
MAX_BUNDLE_FILES: int = 200

MAX_ALLOWED_TOOLS_LEN: int = 2000

# Bounds on the free-form metadata dict to prevent Firestore document inflation.
MAX_METADATA_KEYS: int = 20
MAX_METADATA_KEY_LEN: int = 64
MAX_METADATA_VALUE_LEN: int = 256


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SkillStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class SkillVisibility(str, Enum):
    PRIVATE = "private"
    # ORG = "org"  # v2


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _validate_skill_name(v: str) -> str:
    if not SKILL_NAME_PATTERN.match(v):
        raise ValueError(
            "name must be kebab-case: lowercase a-z0-9 and hyphens only, "
            "no leading/trailing/consecutive hyphens"
        )
    return v


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class SkillOwner(BaseModel):
    """Account-scoped ownership.

    Skills belong to an account, not an individual user; ``created_by`` on the
    ``Skill`` doc captures the authoring user for audit purposes.

    ``shared_with_accounts`` is forward-compat for v2 cross-account sharing.
    Persisted but ignored in v1; no API surface reads or writes it.
    """

    account_id: str = Field(min_length=1)
    shared_with_accounts: list[Annotated[str, Field(min_length=1, max_length=128)]] = (
        Field(default_factory=list, max_length=100)
    )


class SkillSource(BaseModel):
    """Provenance info. ``type="authored"`` for user-authored skills in v1.

    Note: ``type`` carries a default of ``"authored"`` so that
    ``SkillSource()`` constructs without arguments (required by issue ACs and
    the ``Skill.source`` default factory).  The PRD §4 snippet omits the
    default; the ACs and plan decisions override it.
    """

    type: Literal["authored", "github"] = "authored"
    repo: str | None = Field(default=None, max_length=500)
    sha: str | None = Field(default=None, max_length=64)
    license: str | None = Field(default=None, max_length=100)


class SkillFrontmatter(BaseModel):
    """Parsed SKILL.md YAML frontmatter. Mirrors agentskills.io spec."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    name: str = Field(min_length=1, max_length=MAX_NAME_LEN)
    description: str = Field(min_length=1, max_length=MAX_DESCRIPTION_LEN)
    license: str | None = Field(default=None, max_length=100)
    compatibility: str | None = Field(default=None, max_length=MAX_COMPATIBILITY_LEN)
    metadata: dict[str, str] | None = None
    allowed_tools: str | None = Field(
        default=None, alias="allowed-tools", max_length=MAX_ALLOWED_TOOLS_LEN
    )

    @field_validator("name")
    @classmethod
    def _name_regex(cls, v: str) -> str:
        return _validate_skill_name(v)

    @field_validator("metadata")
    @classmethod
    def _metadata_limits(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        if v is None:
            return v
        if len(v) > MAX_METADATA_KEYS:
            raise ValueError(f"metadata must not exceed {MAX_METADATA_KEYS} keys")
        for key, value in v.items():
            if len(key) > MAX_METADATA_KEY_LEN:
                raise ValueError(
                    f"metadata key {key!r} exceeds {MAX_METADATA_KEY_LEN} characters"
                )
            if len(value) > MAX_METADATA_VALUE_LEN:
                raise ValueError(
                    f"metadata value for key {key!r} exceeds {MAX_METADATA_VALUE_LEN} characters"
                )
        return v


class SkillFileEntry(BaseModel):
    """One entry in the bundle manifest — tracks every file uploaded with the skill."""

    rel_path: str = Field(min_length=1)
    kind: Literal["skill_md", "reference", "asset", "script"]
    size_bytes: int = Field(ge=0)
    # Exactly 64 lowercase hex chars produced by hashlib.sha256().hexdigest().
    checksum_sha256: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )

    @field_validator("rel_path")
    @classmethod
    def _no_path_traversal(cls, v: str) -> str:
        if "\x00" in v or v.startswith("/"):
            raise ValueError("rel_path must be a relative path with no null bytes")
        parts = v.replace("\\", "/").split("/")
        if any(p == ".." for p in parts):
            raise ValueError("rel_path must not contain path traversal segments")
        return v


# ---------------------------------------------------------------------------
# Core documents
# ---------------------------------------------------------------------------


class SkillVersion(BaseModel):
    """Immutable per-version snapshot.

    Stored at ``accounts/{account_id}/skills/{skill_id}/versions/{version}``.
    The ``gcs_prefix`` is keyed by ``skill_id`` (not ``skill_name``) so that
    renaming a skill does not split its version history across two GCS prefixes.
    """

    version: int = Field(ge=1)
    gcs_prefix: str = Field(min_length=1)
    frontmatter: SkillFrontmatter
    file_manifest: list[SkillFileEntry] = Field(max_length=MAX_BUNDLE_FILES)
    created_at: datetime
    created_by: str = Field(min_length=1)
    commit_message: str | None = Field(default=None, max_length=1000)


class Skill(BaseModel):
    """Firestore document at ``accounts/{account_id}/skills/{skill_id}``."""

    skill_id: str = Field(min_length=1)
    owner: SkillOwner
    name: str = Field(min_length=1, max_length=MAX_NAME_LEN)
    description: str = Field(min_length=1, max_length=MAX_DESCRIPTION_LEN)
    current_version: int = Field(ge=1)
    visibility: SkillVisibility = SkillVisibility.PRIVATE
    status: SkillStatus = SkillStatus.DRAFT
    source: SkillSource = Field(default_factory=SkillSource)
    has_scripts: bool = False
    created_at: datetime
    created_by: str = Field(min_length=1)
    updated_at: datetime
    updated_by: str = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def _name_regex(cls, v: str) -> str:
        return _validate_skill_name(v)
