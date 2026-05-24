"""Unit tests for ``models.skill_models``.

Covers Pydantic model construction and field validator enforcement for the
Skills component.  These tests exercise models directly — no HTTP layer, no
database, no external services.

AC-1  All 8 types exported and all 11 module-level constants exported.
AC-2  SKILL_NAME_PATTERN / SkillFrontmatter.name enforcement.
      (Also covers SkillFrontmatter.description, .compatibility, .metadata validators.)
AC-14 Lint + unit tests pass.

PRD reference: docs/design/components/skills/projects/SK-PRD-01-skills-backend.md §4, §7, §8
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from src.kene_api.models.skill_models import (
    MAX_ALLOWED_TOOLS_LEN,
    MAX_BUNDLE_FILES,
    MAX_COMPATIBILITY_LEN,
    MAX_DESCRIPTION_LEN,
    MAX_METADATA_KEY_LEN,
    MAX_METADATA_KEYS,
    MAX_METADATA_VALUE_LEN,
    MAX_NAME_LEN,
    MAX_REFERENCE_FILE_BYTES,
    MAX_REFERENCE_FILES,
    MAX_SKILL_MD_BYTES,
    MAX_TOTAL_BUNDLE_BYTES,
    SKILL_NAME_PATTERN,
    Skill,
    SkillFileEntry,
    SkillFrontmatter,
    SkillOwner,
    SkillSource,
    SkillStatus,
    SkillVersion,
    SkillVisibility,
)
from src.kene_api.services.skill_validator import validate_bundle

# Valid 64-char lowercase hex SHA-256 digest used across all test helpers.
_VALID_CHECKSUM = "a" * 64

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------


def _minimal_frontmatter(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "seo-checklist",
        "description": "A concise SEO checklist for page optimisation.",
    }
    base.update(overrides)
    return base


def _minimal_skill(**overrides: object) -> dict[str, object]:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    base: dict[str, object] = {
        "skill_id": "sk_abc123",
        "owner": SkillOwner(account_id="acc_xyz"),
        "name": "seo-checklist",
        "description": "SEO checklist skill.",
        "current_version": 1,
        "created_at": now,
        "created_by": "user_111",
        "updated_at": now,
        "updated_by": "user_111",
    }
    base.update(overrides)
    return base


def _minimal_skill_version(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "version": 1,
        "gcs_prefix": "accounts/acc_xyz/sk_abc123/1/",
        "frontmatter": SkillFrontmatter(**_minimal_frontmatter()),
        "file_manifest": [
            SkillFileEntry(
                rel_path="SKILL.md",
                kind="skill_md",
                size_bytes=512,
                checksum_sha256=_VALID_CHECKSUM,
            )
        ],
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "created_by": "user_111",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# AC-1: Constant exports smoke test
# ---------------------------------------------------------------------------


class TestConstantExports:
    """All 11 module-level constants from AC-5 are importable and correctly typed."""

    def test_skill_name_pattern_is_compiled_regex(self) -> None:
        import re

        assert isinstance(SKILL_NAME_PATTERN, re.Pattern)

    def test_integer_constants_have_correct_types(self) -> None:
        for name, val in [
            ("MAX_NAME_LEN", MAX_NAME_LEN),
            ("MAX_DESCRIPTION_LEN", MAX_DESCRIPTION_LEN),
            ("MAX_COMPATIBILITY_LEN", MAX_COMPATIBILITY_LEN),
            ("MAX_SKILL_MD_BYTES", MAX_SKILL_MD_BYTES),
            ("MAX_REFERENCE_FILE_BYTES", MAX_REFERENCE_FILE_BYTES),
            ("MAX_TOTAL_BUNDLE_BYTES", MAX_TOTAL_BUNDLE_BYTES),
            ("MAX_REFERENCE_FILES", MAX_REFERENCE_FILES),
            ("MAX_BUNDLE_FILES", MAX_BUNDLE_FILES),
            ("MAX_ALLOWED_TOOLS_LEN", MAX_ALLOWED_TOOLS_LEN),
            ("MAX_METADATA_KEYS", MAX_METADATA_KEYS),
            ("MAX_METADATA_KEY_LEN", MAX_METADATA_KEY_LEN),
            ("MAX_METADATA_VALUE_LEN", MAX_METADATA_VALUE_LEN),
        ]:
            assert isinstance(val, int), f"{name} must be int"
            assert val > 0, f"{name} must be positive"

    def test_bundle_files_cap_exceeds_reference_cap(self) -> None:
        # MAX_BUNDLE_FILES must leave room for SKILL.md + all 20 references
        # plus a reasonable number of assets and scripts (PRD §4: no per-dir
        # cap on assets/scripts).
        assert MAX_BUNDLE_FILES > MAX_REFERENCE_FILES + 1

    def test_bundle_cap_constants_ordering(self) -> None:
        # Sanity check: per-file caps must be smaller than total bundle cap.
        assert MAX_SKILL_MD_BYTES < MAX_TOTAL_BUNDLE_BYTES
        assert MAX_REFERENCE_FILE_BYTES < MAX_TOTAL_BUNDLE_BYTES


# ---------------------------------------------------------------------------
# AC-2: SkillFrontmatter.name — SKILL_NAME_PATTERN enforcement
# ---------------------------------------------------------------------------


class TestSkillFrontmatterNameRegex:
    """SkillFrontmatter.name must be kebab-case per SKILL_NAME_PATTERN."""

    @pytest.mark.parametrize(
        "valid_name",
        [
            "seo-checklist",
            "a",
            "a" * MAX_NAME_LEN,  # exactly MAX_NAME_LEN characters
            "abc",
            "a1-b2",
            "my-skill-v2",
            # PRD says "a-z0-9" — all-digit names are valid per spec.
            "123",
            "1a2b",
        ],
    )
    def test_valid_names_accepted(self, valid_name: str) -> None:
        fm = SkillFrontmatter(**_minimal_frontmatter(name=valid_name))
        assert fm.name == valid_name

    @pytest.mark.parametrize(
        "bad_name",
        [
            "PDF-Processing",  # uppercase letter
            "SEO",  # all uppercase
            "-leading",  # leading hyphen
            "trailing-",  # trailing hyphen
            "double--hyphen",  # consecutive hyphens
            "",  # empty string
            "a" * (MAX_NAME_LEN + 1),  # exceeds MAX_NAME_LEN
            "seo checklist",  # space — common user mistake
            "seo_checklist",  # underscore — common user mistake
        ],
    )
    def test_invalid_names_raise(self, bad_name: str) -> None:
        with pytest.raises(ValidationError):
            SkillFrontmatter(**_minimal_frontmatter(name=bad_name))


# ---------------------------------------------------------------------------
# AC-2: SkillFrontmatter.description length validation
# ---------------------------------------------------------------------------


class TestSkillFrontmatterDescription:
    """SkillFrontmatter.description must be 1-1024 characters."""

    def test_single_char_accepted(self) -> None:
        fm = SkillFrontmatter(**_minimal_frontmatter(description="X"))
        assert fm.description == "X"

    def test_exactly_max_chars_accepted(self) -> None:
        desc = "d" * MAX_DESCRIPTION_LEN
        fm = SkillFrontmatter(**_minimal_frontmatter(description=desc))
        assert len(fm.description) == MAX_DESCRIPTION_LEN

    def test_empty_description_raises(self) -> None:
        with pytest.raises(ValidationError):
            SkillFrontmatter(**_minimal_frontmatter(description=""))

    def test_over_max_chars_raises(self) -> None:
        with pytest.raises(ValidationError):
            SkillFrontmatter(
                **_minimal_frontmatter(description="d" * (MAX_DESCRIPTION_LEN + 1))
            )


# ---------------------------------------------------------------------------
# AC-2: SkillFrontmatter.compatibility length validation
# ---------------------------------------------------------------------------


class TestSkillFrontmatterCompatibility:
    """SkillFrontmatter.compatibility must be None or <= MAX_COMPATIBILITY_LEN characters."""

    def test_none_accepted(self) -> None:
        fm = SkillFrontmatter(**_minimal_frontmatter(compatibility=None))
        assert fm.compatibility is None

    def test_single_char_accepted(self) -> None:
        fm = SkillFrontmatter(**_minimal_frontmatter(compatibility="X"))
        assert fm.compatibility == "X"

    def test_exactly_max_chars_accepted(self) -> None:
        fm = SkillFrontmatter(
            **_minimal_frontmatter(compatibility="c" * MAX_COMPATIBILITY_LEN)
        )
        assert fm.compatibility is not None
        assert len(fm.compatibility) == MAX_COMPATIBILITY_LEN

    def test_over_max_chars_raises(self) -> None:
        with pytest.raises(ValidationError):
            SkillFrontmatter(
                **_minimal_frontmatter(compatibility="c" * (MAX_COMPATIBILITY_LEN + 1))
            )


# ---------------------------------------------------------------------------
# AC-2: SkillFrontmatter.allowed_tools alias handling
# ---------------------------------------------------------------------------


class TestSkillFrontmatterAllowedToolsAlias:
    """allowed-tools YAML key (alias) and allowed_tools Python kwarg both work."""

    def test_alias_key_in_model_validate(self) -> None:
        fm = SkillFrontmatter.model_validate(
            {"name": "my-skill", "description": "desc", "allowed-tools": "Read Write"}
        )
        assert fm.allowed_tools == "Read Write"

    def test_python_attribute_name_in_kwarg(self) -> None:
        fm = SkillFrontmatter(name="my-skill", description="desc", allowed_tools="Bash")
        assert fm.allowed_tools == "Bash"

    def test_omitted_defaults_to_none(self) -> None:
        fm = SkillFrontmatter(name="my-skill", description="desc")
        assert fm.allowed_tools is None

    def test_over_max_len_raises(self) -> None:
        with pytest.raises(ValidationError):
            SkillFrontmatter(
                name="my-skill",
                description="desc",
                allowed_tools="x" * (MAX_ALLOWED_TOOLS_LEN + 1),
            )


# ---------------------------------------------------------------------------
# AC-2: SkillFrontmatter.metadata validation
# ---------------------------------------------------------------------------


class TestSkillFrontmatterMetadata:
    """SkillFrontmatter.metadata enforces key/value count and length limits."""

    def test_none_accepted(self) -> None:
        fm = SkillFrontmatter(**_minimal_frontmatter(metadata=None))
        assert fm.metadata is None

    def test_valid_metadata_accepted(self) -> None:
        fm = SkillFrontmatter(**_minimal_frontmatter(metadata={"key": "value"}))
        assert fm.metadata == {"key": "value"}

    def test_exactly_max_keys_accepted(self) -> None:
        meta = {f"k{i}": "v" for i in range(MAX_METADATA_KEYS)}
        fm = SkillFrontmatter(**_minimal_frontmatter(metadata=meta))
        assert fm.metadata is not None
        assert len(fm.metadata) == MAX_METADATA_KEYS

    def test_too_many_keys_raises(self) -> None:
        meta = {f"k{i}": "v" for i in range(MAX_METADATA_KEYS + 1)}
        with pytest.raises(ValidationError):
            SkillFrontmatter(**_minimal_frontmatter(metadata=meta))

    def test_key_at_max_length_accepted(self) -> None:
        meta = {"k" * MAX_METADATA_KEY_LEN: "value"}
        fm = SkillFrontmatter(**_minimal_frontmatter(metadata=meta))
        assert fm.metadata is not None

    def test_key_over_max_length_raises(self) -> None:
        meta = {"k" * (MAX_METADATA_KEY_LEN + 1): "value"}
        with pytest.raises(ValidationError):
            SkillFrontmatter(**_minimal_frontmatter(metadata=meta))

    def test_value_at_max_length_accepted(self) -> None:
        meta = {"key": "v" * MAX_METADATA_VALUE_LEN}
        fm = SkillFrontmatter(**_minimal_frontmatter(metadata=meta))
        assert fm.metadata is not None

    def test_value_over_max_length_raises(self) -> None:
        meta = {"key": "v" * (MAX_METADATA_VALUE_LEN + 1)}
        with pytest.raises(ValidationError):
            SkillFrontmatter(**_minimal_frontmatter(metadata=meta))


# ---------------------------------------------------------------------------
# SkillSource defaults and explicit construction
# ---------------------------------------------------------------------------


class TestSkillSource:
    """SkillSource defaults to type='authored'; github type accepted."""

    def test_default_type_is_authored(self) -> None:
        src = SkillSource()
        assert src.type == "authored"
        assert src.repo is None
        assert src.sha is None
        assert src.license is None

    def test_explicit_authored_type(self) -> None:
        src = SkillSource(type="authored")
        assert src.type == "authored"

    def test_github_type_with_repo_and_sha(self) -> None:
        src = SkillSource(
            type="github",
            repo="acme/skills",
            sha="abc1234",
            license="Apache-2.0",
        )
        assert src.type == "github"
        assert src.repo == "acme/skills"
        assert src.sha == "abc1234"
        assert src.license == "Apache-2.0"

    def test_invalid_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            SkillSource(type="npm")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# SkillOwner defaults
# ---------------------------------------------------------------------------


class TestSkillOwner:
    """SkillOwner.shared_with_accounts defaults to []; explicit list accepted."""

    def test_shared_with_accounts_defaults_to_empty_list(self) -> None:
        owner = SkillOwner(account_id="acc_a")
        assert owner.shared_with_accounts == []

    def test_explicit_account_id_stored(self) -> None:
        owner = SkillOwner(account_id="acc_xyz")
        assert owner.account_id == "acc_xyz"

    def test_explicit_shared_with_accounts(self) -> None:
        owner = SkillOwner(account_id="acc_a", shared_with_accounts=["acc_b", "acc_c"])
        assert owner.shared_with_accounts == ["acc_b", "acc_c"]

    def test_empty_account_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            SkillOwner(account_id="")


# ---------------------------------------------------------------------------
# SkillStatus / SkillVisibility enum string literals
# ---------------------------------------------------------------------------


class TestSkillStatusAndVisibilityEnums:
    """Enum values must match the string literals in PRD §4."""

    def test_skill_status_draft_value(self) -> None:
        assert SkillStatus.DRAFT.value == "draft"

    def test_skill_status_published_value(self) -> None:
        assert SkillStatus.PUBLISHED.value == "published"

    def test_skill_status_archived_value(self) -> None:
        assert SkillStatus.ARCHIVED.value == "archived"

    def test_skill_visibility_private_value(self) -> None:
        assert SkillVisibility.PRIVATE.value == "private"

    def test_skill_status_is_str(self) -> None:
        assert isinstance(SkillStatus.DRAFT, str)

    def test_skill_visibility_is_str(self) -> None:
        assert isinstance(SkillVisibility.PRIVATE, str)


# ---------------------------------------------------------------------------
# Skill smoke construction
# ---------------------------------------------------------------------------


class TestSkillConstruction:
    """Smoke test for the top-level Skill document model."""

    def test_minimal_skill_constructs(self) -> None:
        skill = Skill(**_minimal_skill())

        assert skill.skill_id == "sk_abc123"
        assert skill.current_version == 1
        assert skill.has_scripts is False

    def test_has_scripts_defaults_to_false(self) -> None:
        skill = Skill(**_minimal_skill())
        assert skill.has_scripts is False

    def test_visibility_defaults_to_private(self) -> None:
        skill = Skill(**_minimal_skill())
        assert skill.visibility == SkillVisibility.PRIVATE

    def test_status_defaults_to_draft(self) -> None:
        skill = Skill(**_minimal_skill())
        assert skill.status == SkillStatus.DRAFT

    def test_source_defaults_to_authored(self) -> None:
        skill = Skill(**_minimal_skill())
        assert skill.source.type == "authored"

    def test_explicit_has_scripts_true(self) -> None:
        skill = Skill(**_minimal_skill(has_scripts=True))
        assert skill.has_scripts is True

    def test_empty_skill_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            Skill(**_minimal_skill(skill_id=""))

    def test_zero_current_version_raises(self) -> None:
        with pytest.raises(ValidationError):
            Skill(**_minimal_skill(current_version=0))

    def test_invalid_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            Skill(**_minimal_skill(name="Invalid-Name"))

    def test_name_over_max_len_raises(self) -> None:
        with pytest.raises(ValidationError):
            Skill(**_minimal_skill(name="a" * (MAX_NAME_LEN + 1)))

    def test_description_over_max_len_raises(self) -> None:
        with pytest.raises(ValidationError):
            Skill(**_minimal_skill(description="d" * (MAX_DESCRIPTION_LEN + 1)))

    def test_empty_description_raises(self) -> None:
        with pytest.raises(ValidationError):
            Skill(**_minimal_skill(description=""))


# ---------------------------------------------------------------------------
# SkillVersion smoke construction
# ---------------------------------------------------------------------------


class TestSkillVersionConstruction:
    """SkillVersion constructs with frontmatter and a file manifest."""

    def test_minimal_version_constructs(self) -> None:
        version = SkillVersion(**_minimal_skill_version())

        assert version.version == 1
        assert version.gcs_prefix == "accounts/acc_xyz/sk_abc123/1/"
        assert len(version.file_manifest) == 1
        assert version.commit_message is None

    def test_with_commit_message(self) -> None:
        version = SkillVersion(**_minimal_skill_version(commit_message="Add SEO steps"))
        assert version.commit_message == "Add SEO steps"

    def test_file_manifest_entry_accessible(self) -> None:
        version = SkillVersion(**_minimal_skill_version())
        entry = version.file_manifest[0]
        assert entry.rel_path == "SKILL.md"
        assert entry.kind == "skill_md"

    def test_zero_version_raises(self) -> None:
        with pytest.raises(ValidationError):
            SkillVersion(**_minimal_skill_version(version=0))

    def test_empty_gcs_prefix_raises(self) -> None:
        with pytest.raises(ValidationError):
            SkillVersion(**_minimal_skill_version(gcs_prefix=""))

    def test_file_manifest_over_bundle_cap_raises(self) -> None:
        # The model layer enforces only the MAX_BUNDLE_FILES sanity ceiling.
        # Per-kind caps (MAX_REFERENCE_FILES on `kind="reference"` only) live
        # in skill_validator.py — see PRD §4 / §7.
        oversized = [
            SkillFileEntry(
                rel_path=f"refs/file{i}.md",
                kind="reference",
                size_bytes=100,
                checksum_sha256=_VALID_CHECKSUM,
            )
            for i in range(MAX_BUNDLE_FILES + 1)
        ]
        with pytest.raises(ValidationError):
            SkillVersion(**_minimal_skill_version(file_manifest=oversized))

    def test_mixed_kind_manifest_beyond_reference_cap_accepted(self) -> None:
        # PRD §4: assets/scripts have no per-directory file-count cap. A
        # legitimate bundle of SKILL.md + 20 references + 30 assets must
        # construct cleanly at the model layer (52 entries < MAX_BUNDLE_FILES).
        manifest: list[SkillFileEntry] = [
            SkillFileEntry(
                rel_path="SKILL.md",
                kind="skill_md",
                size_bytes=500,
                checksum_sha256=_VALID_CHECKSUM,
            )
        ]
        manifest.extend(
            SkillFileEntry(
                rel_path=f"references/ref{i}.md",
                kind="reference",
                size_bytes=100,
                checksum_sha256=_VALID_CHECKSUM,
            )
            for i in range(MAX_REFERENCE_FILES)
        )
        manifest.extend(
            SkillFileEntry(
                rel_path=f"assets/asset{i}.png",
                kind="asset",
                size_bytes=100,
                checksum_sha256=_VALID_CHECKSUM,
            )
            for i in range(30)
        )

        version = SkillVersion(**_minimal_skill_version(file_manifest=manifest))
        assert len(version.file_manifest) == 1 + MAX_REFERENCE_FILES + 30


# ---------------------------------------------------------------------------
# SkillFileEntry.kind Literal validation
# ---------------------------------------------------------------------------


class TestSkillFileEntryKind:
    """SkillFileEntry.kind accepts each valid kind and rejects bogus values."""

    @pytest.mark.parametrize("kind", ["skill_md", "reference", "asset", "script"])
    def test_valid_kinds_accepted(self, kind: str) -> None:
        entry = SkillFileEntry(
            rel_path=f"path/to/{kind}",
            kind=kind,  # type: ignore[arg-type]
            size_bytes=100,
            checksum_sha256=_VALID_CHECKSUM,
        )
        assert entry.kind == kind

    def test_bogus_kind_raises(self) -> None:
        with pytest.raises(ValidationError):
            SkillFileEntry(
                rel_path="path/to/unknown",
                kind="bogus",  # type: ignore[arg-type]
                size_bytes=100,
                checksum_sha256=_VALID_CHECKSUM,
            )

    def test_negative_size_bytes_raises(self) -> None:
        with pytest.raises(ValidationError):
            SkillFileEntry(
                rel_path="path/to/file",
                kind="reference",
                size_bytes=-1,
                checksum_sha256=_VALID_CHECKSUM,
            )

    def test_empty_rel_path_raises(self) -> None:
        with pytest.raises(ValidationError):
            SkillFileEntry(
                rel_path="",
                kind="asset",
                size_bytes=0,
                checksum_sha256=_VALID_CHECKSUM,
            )

    def test_empty_checksum_raises(self) -> None:
        with pytest.raises(ValidationError):
            SkillFileEntry(
                rel_path="path/to/file",
                kind="script",
                size_bytes=0,
                checksum_sha256="",
            )


# ---------------------------------------------------------------------------
# SkillFileEntry.checksum_sha256 format validation
# ---------------------------------------------------------------------------


class TestSkillFileEntryChecksum:
    """checksum_sha256 must be exactly 64 lowercase hex characters."""

    def test_valid_64_char_hex_accepted(self) -> None:
        entry = SkillFileEntry(
            rel_path="SKILL.md",
            kind="skill_md",
            size_bytes=100,
            checksum_sha256=_VALID_CHECKSUM,
        )
        assert entry.checksum_sha256 == _VALID_CHECKSUM

    def test_63_char_hex_raises(self) -> None:
        with pytest.raises(ValidationError):
            SkillFileEntry(
                rel_path="f",
                kind="asset",
                size_bytes=0,
                checksum_sha256="a" * 63,
            )

    def test_65_char_hex_raises(self) -> None:
        with pytest.raises(ValidationError):
            SkillFileEntry(
                rel_path="f",
                kind="asset",
                size_bytes=0,
                checksum_sha256="a" * 65,
            )

    def test_uppercase_hex_raises(self) -> None:
        with pytest.raises(ValidationError):
            SkillFileEntry(
                rel_path="f",
                kind="asset",
                size_bytes=0,
                checksum_sha256="A" * 64,
            )

    def test_non_hex_chars_raise(self) -> None:
        with pytest.raises(ValidationError):
            SkillFileEntry(
                rel_path="f",
                kind="asset",
                size_bytes=0,
                checksum_sha256="g" * 64,
            )


# ---------------------------------------------------------------------------
# SkillFileEntry.rel_path path-traversal validation
# ---------------------------------------------------------------------------


class TestSkillFileEntryRelPath:
    """rel_path must not contain traversal segments, absolute paths, or null bytes."""

    @pytest.mark.parametrize(
        "safe_path",
        [
            "SKILL.md",
            "refs/guide.md",
            "assets/logo.png",
            "scripts/run.py",
            "a/b/c/d.txt",
        ],
    )
    def test_safe_relative_paths_accepted(self, safe_path: str) -> None:
        entry = SkillFileEntry(
            rel_path=safe_path,
            kind="reference",
            size_bytes=0,
            checksum_sha256=_VALID_CHECKSUM,
        )
        assert entry.rel_path == safe_path

    @pytest.mark.parametrize(
        "traversal_path",
        [
            "../secret",
            "../../etc/passwd",
            "refs/../../../other",
            "/absolute/path",
            "path/with\x00null",
            "..\\secret",  # Windows-style traversal normalised by replace("\\", "/")
        ],
    )
    def test_traversal_paths_raise(self, traversal_path: str) -> None:
        with pytest.raises(ValidationError):
            SkillFileEntry(
                rel_path=traversal_path,
                kind="reference",
                size_bytes=0,
                checksum_sha256=_VALID_CHECKSUM,
            )


# ---------------------------------------------------------------------------
# TestValidateBundle — appended by SK-13
# ---------------------------------------------------------------------------
# These tests exercise validate_bundle() from skill_validator.py.
# The existing classes above exercise skill_models.py only; this class does
# NOT disturb them.
# ---------------------------------------------------------------------------


def _skill_md(name: str = "my-skill", description: str = "Desc.") -> bytes:
    return f"---\nname: {name}\ndescription: {description}\n---\nBody text.\n".encode()


def _file(rel_path: str, size: int) -> tuple[str, bytes]:
    return (rel_path, b"x" * size)


class TestValidateBundle:
    """validate_bundle() enforces every cap from SK-PRD-01 §4."""

    # ------------------------------------------------------------------
    # Happy paths
    # ------------------------------------------------------------------

    def test_minimal_skill_md_only(self) -> None:
        md = _skill_md()
        report = validate_bundle(md, [], "my-skill")

        assert report.valid is True
        assert report.has_scripts is False
        assert len(report.file_manifest) == 1  # only SKILL.md
        assert report.file_manifest[0].kind == "skill_md"
        assert report.issues == []

    def test_skill_md_plus_one_reference(self) -> None:
        md = _skill_md()
        report = validate_bundle(md, [_file("references/guide.md", 100)], "my-skill")

        assert report.valid is True
        assert len(report.file_manifest) == 2
        assert report.issues == []

    def test_zero_references_valid(self) -> None:
        report = validate_bundle(_skill_md(), [], "my-skill")
        assert report.valid is True

    def test_exactly_max_reference_files_valid(self) -> None:
        refs = [_file(f"references/ref{i}.md", 100) for i in range(MAX_REFERENCE_FILES)]
        report = validate_bundle(_skill_md(), refs, "my-skill")

        assert report.valid is True
        assert len(report.file_manifest) == 1 + MAX_REFERENCE_FILES

    def test_50_assets_valid_no_per_dir_cap(self) -> None:
        assets = [_file(f"assets/img{i}.png", 100) for i in range(50)]
        report = validate_bundle(_skill_md(), assets, "my-skill")

        assert report.valid is True

    def test_50_scripts_sets_has_scripts_true(self) -> None:
        scripts = [_file(f"scripts/run{i}.py", 100) for i in range(50)]
        report = validate_bundle(_skill_md(), scripts, "my-skill")

        assert report.valid is True
        assert report.has_scripts is True

    def test_outer_name_none_skips_name_check(self) -> None:
        # PUT path: outer_name is None — no name_mismatch even if names differ.
        md = _skill_md(name="my-skill")
        report = validate_bundle(md, [], None)

        assert report.valid is True
        assert not any(i.code == "name_mismatch" for i in report.issues)

    def test_sha256_digest_correctness(self) -> None:
        data = b"hello world"
        expected = hashlib.sha256(data).hexdigest()
        report = validate_bundle(
            _skill_md(),
            [("references/test.txt", data)],
            "my-skill",
        )

        assert report.valid is True
        ref_entry = next(e for e in report.file_manifest if e.kind == "reference")
        assert ref_entry.checksum_sha256 == expected

    def test_allowed_tools_alias_survives_round_trip(self) -> None:
        md = b"---\nname: my-skill\ndescription: desc\nallowed-tools: Read Write\n---\nBody.\n"
        report = validate_bundle(md, [], "my-skill")

        assert report.valid is True
        assert report.frontmatter is not None
        assert report.frontmatter.allowed_tools == "Read Write"

    # ------------------------------------------------------------------
    # Failure: too many reference files
    # ------------------------------------------------------------------

    def test_21_reference_files_rejected(self) -> None:
        refs = [_file(f"references/ref{i}.md", 100) for i in range(21)]
        report = validate_bundle(_skill_md(), refs, "my-skill")

        assert report.valid is False
        assert any(
            i.code == "too_many_reference_files" and i.field == "files"
            for i in report.issues
        )

    # ------------------------------------------------------------------
    # Failure: file size
    # ------------------------------------------------------------------

    def test_file_at_exactly_max_size_valid(self) -> None:
        report = validate_bundle(
            _skill_md(),
            [_file("references/big.md", MAX_REFERENCE_FILE_BYTES)],
            "my-skill",
        )
        assert report.valid is True

    def test_file_one_byte_over_max_rejected(self) -> None:
        report = validate_bundle(
            _skill_md(),
            [_file("references/huge.md", MAX_REFERENCE_FILE_BYTES + 1)],
            "my-skill",
        )

        assert report.valid is False
        assert any(
            i.code == "file_too_large" and i.field == "files[0]" for i in report.issues
        )

    def test_zero_size_file_valid(self) -> None:
        report = validate_bundle(
            _skill_md(), [_file("references/empty.md", 0)], "my-skill"
        )
        assert report.valid is True

    # ------------------------------------------------------------------
    # Failure: SKILL.md size
    # ------------------------------------------------------------------

    def test_skill_md_too_large_rejected(self) -> None:
        large_md = (
            b"---\nname: my-skill\ndescription: desc\n---\n" + b"x" * MAX_SKILL_MD_BYTES
        )
        report = validate_bundle(large_md, [], "my-skill")

        assert report.valid is False
        assert any(
            i.code == "skill_md_too_large" and i.field == "skill_md"
            for i in report.issues
        )

    # ------------------------------------------------------------------
    # Failure: total bundle size
    # ------------------------------------------------------------------

    def test_bundle_just_over_2mb_rejected(self) -> None:
        # SKILL.md itself is tiny; one script file that pushes the total over 2 MB.
        big_script = b"x" * (MAX_TOTAL_BUNDLE_BYTES + 1)
        report = validate_bundle(
            _skill_md(), [("scripts/big.py", big_script)], "my-skill"
        )

        assert report.valid is False
        assert any(
            i.code == "file_too_large" or i.code == "bundle_too_large"
            for i in report.issues
        )

    # ------------------------------------------------------------------
    # Failure: name mismatch
    # ------------------------------------------------------------------

    def test_name_mismatch_outer_differs(self) -> None:
        md = _skill_md(name="pdf-processing")
        report = validate_bundle(md, [], "PDF-Processing")

        assert report.valid is False
        assert any(
            i.code == "name_mismatch" and i.field == "name" for i in report.issues
        )

    def test_name_match_outer_same_valid(self) -> None:
        md = _skill_md(name="pdf-processing")
        report = validate_bundle(md, [], "pdf-processing")

        assert report.valid is True

    # ------------------------------------------------------------------
    # Failure: unknown file kind
    # ------------------------------------------------------------------

    def test_unknown_top_level_dir_rejected(self) -> None:
        report = validate_bundle(
            _skill_md(),
            [_file("garbage/foo.txt", 10)],
            "my-skill",
        )

        assert report.valid is False
        assert any(i.code == "unknown_file_kind" for i in report.issues)

    # ------------------------------------------------------------------
    # Failure: reference path depth
    # ------------------------------------------------------------------

    def test_reference_2_levels_deep_rejected(self) -> None:
        report = validate_bundle(
            _skill_md(),
            [_file("references/sub/nested.md", 10)],
            "my-skill",
        )

        assert report.valid is False
        assert any(i.code == "reference_path_depth" for i in report.issues)

    def test_reference_1_level_deep_valid(self) -> None:
        report = validate_bundle(
            _skill_md(),
            [_file("references/guide.md", 10)],
            "my-skill",
        )

        assert report.valid is True

    # ------------------------------------------------------------------
    # Failure: path traversal in file rel_path
    # ------------------------------------------------------------------

    def test_traversal_path_in_file_rejected(self) -> None:
        report = validate_bundle(
            _skill_md(),
            [("../etc/passwd", b"x")],
            "my-skill",
        )

        assert report.valid is False
        assert len(report.issues) > 0

    # ------------------------------------------------------------------
    # Failure: too many files (DoS guard)
    # ------------------------------------------------------------------

    def test_exactly_max_bundle_files_valid(self) -> None:
        # MAX_BUNDLE_FILES assets — should pass (no per-asset cap).
        assets = [_file(f"assets/img{i}.png", 1) for i in range(MAX_BUNDLE_FILES)]
        report = validate_bundle(_skill_md(), assets, "my-skill")

        assert report.valid is True

    def test_one_over_max_bundle_files_rejected(self) -> None:
        assets = [_file(f"assets/img{i}.png", 1) for i in range(MAX_BUNDLE_FILES + 1)]
        report = validate_bundle(_skill_md(), assets, "my-skill")

        assert report.valid is False
        assert any(
            i.code == "too_many_files" and i.field == "files" for i in report.issues
        )

    # ------------------------------------------------------------------
    # AC-2: specific error codes for field-level violations
    # ------------------------------------------------------------------

    def test_uppercase_name_emits_name_regex_code(self) -> None:
        md = _skill_md(name="Invalid-Name")
        report = validate_bundle(md, [], "Invalid-Name")

        assert report.valid is False
        assert any(i.code == "name_regex" for i in report.issues)

    def test_description_too_long_emits_description_length_code(self) -> None:
        md = f"---\nname: my-skill\ndescription: {'d' * 1025}\n---\nBody.\n".encode()
        report = validate_bundle(md, [], "my-skill")

        assert report.valid is False
        assert any(i.code == "description_length" for i in report.issues)
