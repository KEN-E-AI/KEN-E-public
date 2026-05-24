"""Pure-function skill validation service.

Enforces every server-side rule from SK-PRD-01 §4 Frontmatter validation.
No I/O, no async, no Firestore, no GCS.

Reused by:
  - POST /api/v1/accounts/{account_id}/skills          (SK-15)
  - PUT  /api/v1/accounts/{account_id}/skills/{id}     (SK-15)
  - POST /api/v1/accounts/{account_id}/skills/validate (SK-16)

PRD reference: docs/design/components/skills/projects/SK-PRD-01-skills-backend.md §4, §7, §8
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

import yaml
from pydantic import ValidationError as PydanticValidationError

from ..models.skill_models import (
    MAX_BUNDLE_FILES,
    MAX_REFERENCE_FILE_BYTES,
    MAX_REFERENCE_FILES,
    MAX_SKILL_MD_BYTES,
    MAX_TOTAL_BUNDLE_BYTES,
    SkillFileEntry,
    SkillFrontmatter,
)

__all__ = [
    "ParsedFrontmatter",
    "ValidationIssue",
    "ValidationReport",
    "parse_frontmatter",
    "validate_bundle",
]

# ---------------------------------------------------------------------------
# Error code vocabulary
# ---------------------------------------------------------------------------
# frontmatter_missing       -no opening "---" delimiter
# frontmatter_unclosed      -opening "---" found but no closing "---"
# frontmatter_empty         -opening + closing "---" but YAML region is blank
# frontmatter_tab_indent    -leading tab(s) on a frontmatter line
# frontmatter_yaml_invalid  -yaml.YAMLError or non-dict YAML or non-UTF-8
# name_regex                -frontmatter.name fails SKILL_NAME_PATTERN or length
# description_length        -frontmatter.description empty or >MAX_DESCRIPTION_LEN
# compatibility_length      -frontmatter.compatibility >MAX_COMPATIBILITY_LEN
# allowed_tools_length      -frontmatter.allowed-tools >MAX_ALLOWED_TOOLS_LEN
# frontmatter_field_invalid -Pydantic error for any unmapped frontmatter field
# name_mismatch             -frontmatter.name != outer_name (form field)
# skill_md_too_large        -SKILL.md byte count > MAX_SKILL_MD_BYTES
# file_too_large            -individual file > MAX_REFERENCE_FILE_BYTES
# bundle_too_large          -total bundle > MAX_TOTAL_BUNDLE_BYTES
# too_many_reference_files  -references/ count > MAX_REFERENCE_FILES
# reference_path_depth      -reference path has >1 segment after references/
# too_many_files            -len(files) > MAX_BUNDLE_FILES (DoS guard)
# unknown_file_kind         -top-level directory not in {references,assets,scripts}
# rel_path_invalid          -path traversal or null byte in a file's rel_path

_TAB_RE = re.compile(r"^\t+", re.MULTILINE)
# Matches the closing "---" delimiter at the start of a line, followed by \r\n, \n, or EOF.
_FM_CLOSER_RE = re.compile(r"^---(?:\r\n|\n|$)", re.MULTILINE)


# ---------------------------------------------------------------------------
# Result types (frozen dataclasses — no Pydantic, no I/O)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationIssue:
    """A single validation failure with a field pointer and machine code."""

    field: str
    code: str
    message: str


@dataclass(frozen=True)
class ParsedFrontmatter:
    """Result of parse_frontmatter()."""

    frontmatter: SkillFrontmatter | None
    body: bytes
    issues: list[ValidationIssue]


@dataclass(frozen=True)
class ValidationReport:
    """Result of validate_bundle()."""

    valid: bool
    frontmatter: SkillFrontmatter | None
    file_manifest: list[SkillFileEntry]
    has_scripts: bool
    issues: list[ValidationIssue]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _issue(field: str, code: str, message: str) -> ValidationIssue:
    return ValidationIssue(field=field, code=code, message=message)


def _split_frontmatter(raw: str) -> tuple[str | None, str, str | None]:
    """Split raw SKILL.md text into (yaml_block, body, error_code).

    Returns a 3-tuple (yaml_block, body, error_code) where error_code
    is None on success or a string error code on failure.
    """
    if not raw.startswith("---\n") and not raw.startswith("---\r\n"):
        return None, raw, "frontmatter_missing"

    # Strip the opening "---" line.
    after_open = raw[4:] if raw.startswith("---\n") else raw[5:]

    # Find the closing "---" line anchored to the start of a line.
    # Using a MULTILINE regex avoids the false-close bug where a bare "\n---"
    # substring search would match "---" inside a YAML block scalar.
    m = _FM_CLOSER_RE.search(after_open)
    if m is None:
        return None, raw, "frontmatter_unclosed"

    yaml_block = after_open[: m.start()]
    body = after_open[m.end() :]
    return yaml_block, body, None


def _check_tab_indent(yaml_block: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for lineno, line in enumerate(yaml_block.splitlines(), start=2):
        if _TAB_RE.match(line):
            issues.append(
                _issue(
                    "frontmatter",
                    "frontmatter_tab_indent",
                    f"Line {lineno} of frontmatter uses leading tab indentation; "
                    "use spaces instead.",
                )
            )
    return issues


def _classify_kind(
    rel_path: str,
) -> Literal["skill_md", "reference", "asset", "script"] | None:
    """Map a rel_path to its bundle kind. Returns None for unknown top-level dirs."""
    if rel_path == "SKILL.md":
        return "skill_md"
    parts = rel_path.replace("\\", "/").split("/", 1)
    mapping: dict[str, Literal["reference", "asset", "script"]] = {
        "references": "reference",
        "assets": "asset",
        "scripts": "script",
    }
    return mapping.get(parts[0])


def _check_skill_md_size(data: bytes) -> ValidationIssue | None:
    if len(data) > MAX_SKILL_MD_BYTES:
        return _issue(
            "skill_md",
            "skill_md_too_large",
            f"SKILL.md is {len(data):,} bytes; maximum is {MAX_SKILL_MD_BYTES:,} bytes.",
        )
    return None


def _check_individual_file(
    rel_path: str, size: int, idx: int
) -> ValidationIssue | None:
    if size > MAX_REFERENCE_FILE_BYTES:
        return _issue(
            f"files[{idx}]",
            "file_too_large",
            f"File '{rel_path}' is {size:,} bytes; "
            f"maximum is {MAX_REFERENCE_FILE_BYTES:,} bytes.",
        )
    return None


def _check_total_bundle(total: int) -> ValidationIssue | None:
    if total > MAX_TOTAL_BUNDLE_BYTES:
        return _issue(
            "files",
            "bundle_too_large",
            f"Total bundle size is {total:,} bytes; "
            f"maximum is {MAX_TOTAL_BUNDLE_BYTES:,} bytes.",
        )
    return None


def _check_reference_constraints(ref_paths: list[str]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if len(ref_paths) > MAX_REFERENCE_FILES:
        issues.append(
            _issue(
                "files",
                "too_many_reference_files",
                f"Found {len(ref_paths)} files in references/; "
                f"maximum is {MAX_REFERENCE_FILES}.",
            )
        )
    for rp in ref_paths:
        # Strip "references/" prefix; if there is still a "/" the path is 2-levels deep.
        remainder = rp[len("references/") :]
        if "/" in remainder:
            issues.append(
                _issue(
                    "files",
                    "reference_path_depth",
                    f"Reference file '{rp}' is nested more than one level deep "
                    "inside references/; files must be directly under references/.",
                )
            )
    return issues


# Maps Pydantic field names to the AC-2-required specific error codes.
# Any field not listed here falls back to frontmatter_field_invalid.
_PYDANTIC_LOC_TO_CODE: dict[str, str] = {
    "name": "name_regex",
    "description": "description_length",
    "compatibility": "compatibility_length",
    "allowed_tools": "allowed_tools_length",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_frontmatter(skill_md_bytes: bytes) -> ParsedFrontmatter:
    """Parse the YAML frontmatter from a raw SKILL.md byte blob.

    Always returns a ``ParsedFrontmatter`` — never raises.  Callers can collect
    *all* parse errors without crashing on the first one.

    L1/L2 are materialized here:
      - L1: frontmatter fields (returned as ``SkillFrontmatter``)
      - L2: Markdown body bytes (returned as ``body``)

    Args:
        skill_md_bytes: Raw bytes of the uploaded SKILL.md file.

    Returns:
        ParsedFrontmatter with ``frontmatter=None`` and populated ``issues``
        on any failure, or ``frontmatter=<SkillFrontmatter>`` and empty
        ``issues`` on success.
    """
    issues: list[ValidationIssue] = []

    # 1. Decode to text.
    try:
        raw = skill_md_bytes.decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        issues.append(
            _issue(
                "skill_md",
                "frontmatter_yaml_invalid",
                "SKILL.md is not valid UTF-8.",
            )
        )
        return ParsedFrontmatter(frontmatter=None, body=b"", issues=issues)

    # 2. Split on "---" delimiters.
    yaml_block, body_str, error_code = _split_frontmatter(raw)
    body_bytes = body_str.encode("utf-8") if isinstance(body_str, str) else body_str

    if error_code == "frontmatter_missing":
        issues.append(
            _issue(
                "skill_md",
                "frontmatter_missing",
                "SKILL.md does not begin with a '---' frontmatter delimiter.",
            )
        )
        return ParsedFrontmatter(frontmatter=None, body=body_bytes, issues=issues)

    if error_code == "frontmatter_unclosed":
        issues.append(
            _issue(
                "skill_md",
                "frontmatter_unclosed",
                "SKILL.md frontmatter block is not closed with a '---' delimiter.",
            )
        )
        return ParsedFrontmatter(frontmatter=None, body=body_bytes, issues=issues)

    if yaml_block is None:
        # Defensive: both error paths above return early; this is unreachable in practice.
        issues.append(
            _issue("skill_md", "frontmatter_yaml_invalid", "Internal parse error.")
        )
        return ParsedFrontmatter(frontmatter=None, body=body_bytes, issues=issues)

    # 3. Check for empty frontmatter.
    if not yaml_block.strip():
        issues.append(
            _issue(
                "skill_md",
                "frontmatter_empty",
                "SKILL.md frontmatter block is empty.",
            )
        )
        return ParsedFrontmatter(frontmatter=None, body=body_bytes, issues=issues)

    # 4. Leading-tab pre-check.
    tab_issues = _check_tab_indent(yaml_block)
    if tab_issues:
        issues.extend(tab_issues)
        # We can still attempt to parse the YAML, but we record the tab issues.

    # 5. Parse YAML.
    try:
        parsed_yaml = yaml.safe_load(yaml_block)
    except yaml.YAMLError as exc:
        issues.append(
            _issue(
                "skill_md",
                "frontmatter_yaml_invalid",
                f"SKILL.md frontmatter contains invalid YAML: {exc}",
            )
        )
        return ParsedFrontmatter(frontmatter=None, body=body_bytes, issues=issues)

    if not isinstance(parsed_yaml, dict):
        issues.append(
            _issue(
                "skill_md",
                "frontmatter_yaml_invalid",
                "SKILL.md frontmatter must be a YAML mapping (key: value pairs), "
                f"not {type(parsed_yaml).__name__}.",
            )
        )
        return ParsedFrontmatter(frontmatter=None, body=body_bytes, issues=issues)

    # 6. Validate with Pydantic.
    try:
        fm = SkillFrontmatter.model_validate(parsed_yaml)
    except PydanticValidationError as exc:
        for err in exc.errors():
            loc = err.get("loc", ())
            field_name = (
                f"frontmatter.{'.'.join(str(part) for part in loc)}"
                if loc
                else "frontmatter"
            )
            top_key = str(loc[0]) if loc else ""
            code = _PYDANTIC_LOC_TO_CODE.get(top_key, "frontmatter_field_invalid")
            issues.append(_issue(field_name, code, err.get("msg", "Invalid value")))
        return ParsedFrontmatter(frontmatter=None, body=body_bytes, issues=issues)

    # If we had tab issues but YAML was otherwise valid, still return frontmatter=None
    # to signal that the file needs to be fixed before it can be used.
    if issues:
        return ParsedFrontmatter(frontmatter=None, body=body_bytes, issues=issues)

    return ParsedFrontmatter(frontmatter=fm, body=body_bytes, issues=[])


def validate_bundle(
    skill_md_bytes: bytes,
    files: list[tuple[str, bytes]],
    outer_name: str | None,
) -> ValidationReport:
    """Validate a complete skill bundle.

    Runs every check from SK-PRD-01 §4 Frontmatter validation:
      - SKILL.md size cap
      - Individual file size cap (uniform across all kinds)
      - Total bundle size cap
      - references/ file-count cap (≤ MAX_REFERENCE_FILES)
      - references/ path depth cap (1 level deep only)
      - Frontmatter name ↔ outer_name agreement
      - sha256 checksum computation for every file

    Args:
        skill_md_bytes: Raw SKILL.md file bytes.
        files: List of (rel_path, data) tuples for every additional uploaded file.
               The router translates UploadFiles to (filename, await file.read())
               before calling this function.
        outer_name: The ``name`` form field from the multipart request, or None
                    on PUT (where the name is allowed to change and is taken from
                    frontmatter). When provided, it must match frontmatter.name
                    case-sensitively.

    Returns:
        ValidationReport with ``valid=True`` and a populated ``file_manifest``
        on success, or ``valid=False`` with ``issues`` listing every violation.
    """
    issues: list[ValidationIssue] = []
    manifest: list[SkillFileEntry] = []

    # Step a: Parse frontmatter.
    parsed = parse_frontmatter(skill_md_bytes)
    issues.extend(parsed.issues)

    # Step b: SKILL.md size cap.
    size_issue = _check_skill_md_size(skill_md_bytes)
    if size_issue:
        issues.append(size_issue)

    # Add SKILL.md to manifest unconditionally (storage service needs it).
    skill_md_checksum = hashlib.sha256(skill_md_bytes).hexdigest()
    try:
        skill_md_entry = SkillFileEntry(
            rel_path="SKILL.md",
            kind="skill_md",
            size_bytes=len(skill_md_bytes),
            checksum_sha256=skill_md_checksum,
        )
        manifest.append(skill_md_entry)
    except PydanticValidationError as exc:
        for err in exc.errors():
            issues.append(
                _issue(
                    "skill_md",
                    "rel_path_invalid",
                    err.get("msg", "Invalid SKILL.md entry"),
                )
            )

    # Step c: Bundle file count guard (DoS protection — short-circuit before O(n) loop).
    if len(files) > MAX_BUNDLE_FILES:
        issues.append(
            _issue(
                "files",
                "too_many_files",
                f"Bundle contains {len(files)} files; maximum is {MAX_BUNDLE_FILES}.",
            )
        )
        return ValidationReport(
            valid=False,
            frontmatter=parsed.frontmatter,
            file_manifest=manifest,
            has_scripts=False,
            issues=issues,
        )

    # Step d: Process each additional file.
    total_bytes = len(skill_md_bytes)
    ref_paths: list[str] = []

    for idx, (rel_path, data) in enumerate(files):
        kind = _classify_kind(rel_path)

        if kind is None:
            issues.append(
                _issue(
                    f"files[{idx}]",
                    "unknown_file_kind",
                    f"File '{rel_path}' is not under a recognised directory "
                    "(references/, assets/, or scripts/).",
                )
            )
            continue

        if kind == "skill_md":
            # Uploading SKILL.md again as a separate file is an error.
            issues.append(
                _issue(
                    f"files[{idx}]",
                    "unknown_file_kind",
                    "SKILL.md must be uploaded via the 'skill_md' form field, "
                    "not as a separate file in 'files'.",
                )
            )
            continue

        # Per-file size check (uniform cap on all kinds per PRD §4 / §7).
        file_issue = _check_individual_file(rel_path, len(data), idx)
        if file_issue:
            issues.append(file_issue)

        total_bytes += len(data)

        if kind == "reference":
            ref_paths.append(rel_path)

        # Compute checksum and build manifest entry.
        checksum = hashlib.sha256(data).hexdigest()
        try:
            entry = SkillFileEntry(
                rel_path=rel_path,
                kind=kind,
                size_bytes=len(data),
                checksum_sha256=checksum,
            )
            manifest.append(entry)
        except PydanticValidationError as exc:
            for err in exc.errors():
                issues.append(
                    _issue(
                        f"files[{idx}]",
                        "rel_path_invalid",
                        err.get("msg", f"Invalid rel_path for file '{rel_path}'"),
                    )
                )

    # Step e: Total bundle size cap.
    bundle_issue = _check_total_bundle(total_bytes)
    if bundle_issue:
        issues.append(bundle_issue)

    # Step f: Reference constraints.
    issues.extend(_check_reference_constraints(ref_paths))

    # Step g: Outer name agreement.
    if (
        outer_name is not None
        and parsed.frontmatter is not None
        and outer_name != parsed.frontmatter.name
    ):
        issues.append(
            _issue(
                "name",
                "name_mismatch",
                f"The 'name' form field ({outer_name!r}) does not match the "
                f"name in SKILL.md frontmatter ({parsed.frontmatter.name!r}). "
                "Both must be identical (case-sensitive).",
            )
        )

    # Step h: has_scripts derived from manifest.
    has_scripts = any(e.kind == "script" for e in manifest)

    # Step i: Determine validity.
    valid = len(issues) == 0

    return ValidationReport(
        valid=valid,
        frontmatter=parsed.frontmatter,
        file_manifest=manifest,
        has_scripts=has_scripts,
        issues=issues,
    )
