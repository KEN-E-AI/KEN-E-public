"""
Tests for lychee.toml config and offline markdown link-checking behavior.

These tests run without requiring the lychee binary — they use Python's
tomllib for config validation and a lightweight link scanner for behavioral
tests. This covers TC-0 through TC-5 from the CH-2 Test Instructions.

Run with:
    uv run pytest tests/unit/test_lychee_config.py -v
"""

import re
from pathlib import Path

import pytest
import tomllib

REPO_ROOT = Path(__file__).parent.parent.parent
LYCHEE_CONFIG_PATH = REPO_ROOT / "lychee.toml"

# Regex matching markdown hyperlinks: [text](target)
_LINK_RE = re.compile(r"\[(?:[^\[\]]*)\]\(([^)]+)\)")
# Regex stripping fenced code blocks (``` ... ```) when include_verbatim=False
_FENCED_BLOCK_RE = re.compile(r"```[^`]*```", re.DOTALL)


def _load_config() -> dict:
    with LYCHEE_CONFIG_PATH.open("rb") as f:
        return tomllib.load(f)


def _is_excluded(path: Path, exclude_paths: list[str]) -> bool:
    """Return True if path falls under any entry in exclude_paths."""
    try:
        rel = str(path.relative_to(REPO_ROOT))
    except ValueError:
        return False  # path outside repo root — repo-relative exclusions don't apply
    for excl in exclude_paths:
        clean = excl.strip("/")
        if rel == clean or rel.startswith(clean + "/"):
            return True
    return False


def _collect_markdown_files(base: Path, config: dict) -> list[Path]:
    """Return files matching config extensions under base, respecting exclude_path."""
    excluded = config.get("exclude_path", [])
    exts = set(config.get("extensions", ["md"]))
    files: list[Path] = []
    if base.is_file():
        if base.suffix.lstrip(".") in exts and not _is_excluded(base, excluded):
            files.append(base)
    elif base.is_dir():
        for f in sorted(base.rglob("*")):
            if (
                f.is_file()
                and f.suffix.lstrip(".") in exts
                and not _is_excluded(f, excluded)
            ):
                files.append(f)
    return files


def _extract_relative_links(content: str, include_verbatim: bool = True) -> list[str]:
    """Return relative (non-URL) links found in markdown content.

    When include_verbatim=False, links inside fenced code blocks are skipped.
    Skips http(s)/mailto/ftp links, anchor-only refs, and template literals
    that start with '{' or '<' (these are not real file paths).
    """
    if not include_verbatim:
        content = _FENCED_BLOCK_RE.sub("", content)
    raw = _LINK_RE.findall(content)
    return [
        lnk
        for lnk in raw
        if not lnk.startswith(
            ("http://", "https://", "mailto:", "ftp://", "#", "<", "{")
        )
        and not lnk.startswith("/")  # absolute paths are not local relative links
    ]


def _find_broken_links(
    files: list[Path], include_verbatim: bool
) -> list[tuple[Path, str]]:
    """Return (source_file, link) pairs for every unresolvable relative link."""
    broken: list[tuple[Path, str]] = []
    for f in files:
        content = f.read_text(encoding="utf-8", errors="replace")
        links = _extract_relative_links(content, include_verbatim)
        for link in links:
            target_str = link.split("#")[0]  # strip anchor fragment
            if not target_str:
                continue
            target = (f.parent / target_str).resolve()
            # For repo files: links that resolve outside REPO_ROOT (e.g. path traversal
            # via ../../../../etc/passwd) are flagged rather than checked against the
            # host filesystem, which would produce false negatives.
            if f.is_relative_to(REPO_ROOT) and not target.is_relative_to(REPO_ROOT):
                broken.append((f, link))
                continue
            if not target.exists():
                broken.append((f, link))
    return broken


# ── TC-0: Config structure ─────────────────────────────────────────────────


class TestConfigStructure:
    """TC-0: lychee.toml exists and contains all required fields."""

    def test_file_exists(self) -> None:
        assert LYCHEE_CONFIG_PATH.exists(), "lychee.toml not found at repo root"

    def test_parses_as_valid_toml(self) -> None:
        cfg = _load_config()
        assert isinstance(cfg, dict)

    def test_offline_mode_via_scheme_file_only(self) -> None:
        """scheme = ["file"] is the correct lychee config key for offline mode.

        lychee does not recognise `offline = true` as a config-file key.
        Using `scheme = ["file"]` restricts checking to local file:// URIs,
        which is equivalent to the --offline CLI flag.
        """
        cfg = _load_config()
        scheme = cfg.get("scheme")
        assert scheme == ["file"], (
            f'Expected scheme = ["file"] for offline mode, got: {scheme!r}. '
            "lychee ignores 'offline = true' in config; use scheme instead."
        )

    def test_cache_disabled(self) -> None:
        cfg = _load_config()
        assert cfg.get("cache") is False

    def test_include_verbatim_enabled(self) -> None:
        cfg = _load_config()
        assert cfg.get("include_verbatim") is True

    def test_extensions_md_only(self) -> None:
        cfg = _load_config()
        assert cfg.get("extensions") == ["md"]

    def test_figma_export_excluded(self) -> None:
        cfg = _load_config()
        exclude_paths = cfg.get("exclude_path", [])
        assert any("figma-export" in ep for ep in exclude_paths), (
            f"docs/figma-export missing from exclude_path: {exclude_paths}"
        )

    def test_archive_excluded(self) -> None:
        cfg = _load_config()
        exclude_paths = cfg.get("exclude_path", [])
        assert any("archive" in ep for ep in exclude_paths), (
            f"docs/archive missing from exclude_path: {exclude_paths}"
        )

    def test_node_modules_excluded(self) -> None:
        cfg = _load_config()
        exclude_paths = cfg.get("exclude_path", [])
        assert any("node_modules" in ep for ep in exclude_paths), (
            f"node_modules missing from exclude_path: {exclude_paths}"
        )

    def test_git_excluded(self) -> None:
        cfg = _load_config()
        exclude_paths = cfg.get("exclude_path", [])
        assert any(".git" in ep for ep in exclude_paths), (
            f".git missing from exclude_path: {exclude_paths}"
        )

    def test_all_exclude_paths_have_inline_comments(self) -> None:
        """Each exclude_path entry must be accompanied by an explanatory comment
        so future maintainers know why it is excluded."""
        raw = LYCHEE_CONFIG_PATH.read_text()
        # After the `exclude_path = [` line, each entry line should end with `# ...`
        in_block = False
        uncommented: list[str] = []
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("exclude_path"):
                in_block = True
                continue
            if in_block:
                if stripped == "]":
                    break
                if stripped and not stripped.startswith("#") and stripped != "[":
                    # This is a value line — it must have an inline comment
                    if "#" not in stripped:
                        uncommented.append(stripped)
        assert not uncommented, (
            f"These exclude_path entries lack inline comments: {uncommented}"
        )


# ── TC-2: Negative scan — broken links detected ───────────────────────────


class TestNegativeScan:
    """TC-2: A file with a broken relative link must be detected as broken."""

    def test_broken_relative_link_detected(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_broken.md"
        test_file.write_text("[broken](./does-not-exist.md)\n")
        broken = _find_broken_links([test_file], include_verbatim=True)
        assert broken == [(test_file, "./does-not-exist.md")]

    def test_valid_relative_link_not_flagged(self, tmp_path: Path) -> None:
        target = tmp_path / "exists.md"
        target.write_text("# exists\n")
        test_file = tmp_path / "source.md"
        test_file.write_text("[valid](./exists.md)\n")
        broken = _find_broken_links([test_file], include_verbatim=True)
        assert broken == []

    def test_http_links_not_flagged(self, tmp_path: Path) -> None:
        """http(s) links are skipped — this is the offline-mode guarantee."""
        test_file = tmp_path / "http_test.md"
        test_file.write_text("[external](https://example.com/page)\n")
        broken = _find_broken_links([test_file], include_verbatim=True)
        assert broken == [], "https:// links must be excluded in offline mode"

    def test_anchor_only_links_not_flagged(self, tmp_path: Path) -> None:
        test_file = tmp_path / "anchors.md"
        test_file.write_text("[section](#some-heading)\n")
        broken = _find_broken_links([test_file], include_verbatim=True)
        assert broken == []

    def test_verbatim_links_in_code_blocks_detected(self, tmp_path: Path) -> None:
        """With include_verbatim=True, broken links inside code blocks are caught."""
        test_file = tmp_path / "verbatim_test.md"
        test_file.write_text("```\n[broken](./missing.md)\n```\n")
        broken = _find_broken_links([test_file], include_verbatim=True)
        assert len(broken) == 1


# ── TC-3: Excluded directories produce no scan results ─────────────────────


class TestExclusionLogic:
    """TC-3: Files inside excluded directories are not collected for scanning."""

    def test_figma_export_files_excluded(self) -> None:
        cfg = _load_config()
        figma_dir = REPO_ROOT / "docs" / "figma-export"
        if not figma_dir.exists():
            pytest.skip("docs/figma-export does not exist — nothing to exclude")
        files = _collect_markdown_files(figma_dir, cfg)
        assert files == [], (
            f"docs/figma-export/ should be excluded but collected: {files[:3]}"
        )

    def test_archive_files_excluded(self) -> None:
        cfg = _load_config()
        archive_dir = REPO_ROOT / "docs" / "archive"
        if not archive_dir.exists():
            pytest.skip("docs/archive does not exist — nothing to exclude")
        files = _collect_markdown_files(archive_dir, cfg)
        assert files == [], (
            f"docs/archive/ should be excluded but collected: {files[:3]}"
        )

    def test_git_dir_excluded(self) -> None:
        cfg = _load_config()
        git_dir = REPO_ROOT / ".git"
        if not git_dir.exists():
            pytest.skip(".git directory does not exist")
        files = _collect_markdown_files(git_dir, cfg)
        assert files == [], ".git/ must not be scanned"


# ── TC-4: Only .md files are scanned ──────────────────────────────────────


class TestExtensionsFilter:
    """TC-4: collect_markdown_files returns only .md files."""

    def test_html_files_not_collected(self, tmp_path: Path) -> None:
        cfg = _load_config()
        html_file = tmp_path / "test.html"
        html_file.write_text('<a href="broken.html">x</a>')
        files = _collect_markdown_files(html_file, cfg)
        assert files == [], ".html files must not be collected"

    def test_python_files_not_collected(self, tmp_path: Path) -> None:
        cfg = _load_config()
        py_file = tmp_path / "test.py"
        py_file.write_text("# [link](./missing.md)")
        files = _collect_markdown_files(py_file, cfg)
        assert files == [], ".py files must not be collected"

    def test_md_files_are_collected(self, tmp_path: Path) -> None:
        cfg = _load_config()
        # tmp_path is outside REPO_ROOT so _is_excluded won't match;
        # override exclude_paths to empty for this directory test.
        md_file = tmp_path / "test.md"
        md_file.write_text("# hello\n")
        # Temporarily bypass exclude check by using empty config
        files = _collect_markdown_files(
            md_file, {"exclude_path": [], "extensions": ["md"]}
        )
        assert md_file in files

    def test_only_md_files_collected_from_docs(self) -> None:
        cfg = _load_config()
        files = _collect_markdown_files(REPO_ROOT / "docs", cfg)
        for f in files:
            assert f.suffix == ".md", f"Non-.md file collected: {f}"


# ── TC-5: Root markdown files have no broken links ────────────────────────


class TestRootMarkdownFiles:
    """TC-5: README.md, CLAUDE.md, and REVIEW.md have no broken relative links."""

    def _check(self, filename: str) -> list[tuple[Path, str]]:
        cfg = _load_config()
        f = REPO_ROOT / filename
        if not f.exists():
            return []
        return _find_broken_links(
            [f], include_verbatim=cfg.get("include_verbatim", True)
        )

    def test_readme_has_no_broken_links(self) -> None:
        broken = self._check("README.md")
        assert broken == [], f"README.md broken links: {broken}"

    def test_claude_md_has_no_broken_links(self) -> None:
        broken = self._check("CLAUDE.md")
        assert broken == [], f"CLAUDE.md broken links: {broken}"

    def test_review_md_has_no_broken_links(self) -> None:
        broken = self._check("REVIEW.md")
        assert broken == [], f"REVIEW.md broken links: {broken}"


# ── TC-1: Positive scan — no unexpected broken links ──────────────────────


class TestPositiveScan:
    """TC-1: Full scan of docs/ finds only the known chat-PRD forward-references.

    Before CH-1 merges: exactly the chat-PRD forward-refs in
    docs/design/components/chat/** are broken (those are CH-1's scope).
    After CH-1 merges: zero broken links.

    This test passes in either state. Any broken link OUTSIDE
    docs/design/components/chat/** is flagged as an unexpected regression.
    """

    def test_no_unexpected_broken_links_outside_chat_prd(self) -> None:
        cfg = _load_config()
        docs_dir = REPO_ROOT / "docs"
        files = _collect_markdown_files(docs_dir, cfg)
        broken = _find_broken_links(
            files, include_verbatim=cfg.get("include_verbatim", True)
        )

        unexpected = [
            (f, lnk) for f, lnk in broken if "docs/design/components/chat" not in str(f)
        ]
        assert unexpected == [], (
            "Broken links found OUTSIDE docs/design/components/chat/ — "
            "these are regressions not covered by CH-1:\n"
            + "\n".join(f"  {f.relative_to(REPO_ROOT)}: {lnk}" for f, lnk in unexpected)
        )

    def test_broken_links_in_chat_prd_are_known_forward_refs(self) -> None:
        """All broken links in chat PRDs must point to implementation files
        that are being forward-referenced (not random noise)."""
        cfg = _load_config()
        chat_dir = REPO_ROOT / "docs" / "design" / "components" / "chat"
        files = _collect_markdown_files(chat_dir, cfg)
        broken = _find_broken_links(
            files, include_verbatim=cfg.get("include_verbatim", True)
        )

        # After CH-1, this list will be empty.
        # Before CH-1, the broken links should point to either implementation
        # forward-refs or obvious example/placeholder links used in PRD prose.
        # Note: lychee's include_verbatim only affects fenced code blocks, not
        # inline code spans. The Python scanner is broader, so CH-PRD-06's
        # inline-code examples (path/to/unbuilt/file, does-not-exist.md) appear
        # here even though lychee would skip them.
        known_patterns = (
            "api/src/kene_api/",
            "app/adk/",
            "frontend/src/",
            "firestore.rules",
            "deployment/",
            "path/to/",  # placeholder used as example in CH-PRD-06 prose
            "does-not-exist",  # example link in CH-PRD-06 test-plan description
        )
        unexpected_chat = [
            (f, lnk)
            for f, lnk in broken
            if not any(pat in lnk for pat in known_patterns)
        ]
        assert unexpected_chat == [], (
            "Unexpected broken links in chat PRDs (not recognised as "
            "implementation forward-refs):\n"
            + "\n".join(
                f"  {f.relative_to(REPO_ROOT)}: {lnk}" for f, lnk in unexpected_chat
            )
        )
