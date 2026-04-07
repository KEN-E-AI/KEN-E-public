"""Tests for trace metadata utilities."""

import pytest

from app.utils.trace_metadata import (
    DEFAULT_VERSION,
    SEMVER_PATTERN,
    parse_semver,
    validate_semver,
)


class TestSemverPattern:
    """Tests for the SEMVER_PATTERN regex."""

    @pytest.mark.parametrize(
        "version",
        [
            "v1.0.0",
            "v1.2.3",
            "v0.0.1",
            "v10.20.30",
            "1.0.0",
            "1.2.3",
            "v1.0.0-beta.1",
            "v1.0.0-rc1",
            "v2.1.0-alpha",
        ],
    )
    def test_valid_semver(self, version: str) -> None:
        assert SEMVER_PATTERN.match(version) is not None

    @pytest.mark.parametrize(
        "version",
        [
            "latest",
            "v1",
            "v1.0",
            "1",
            "1.0",
            "",
            "abc",
            "v1.0.0.",
            "v.1.0.0",
        ],
    )
    def test_invalid_semver(self, version: str) -> None:
        assert SEMVER_PATTERN.match(version) is None


class TestValidateSemver:
    """Tests for the validate_semver function."""

    def test_valid_with_v_prefix(self) -> None:
        assert validate_semver("v1.2.3") == "v1.2.3"

    def test_valid_without_v_prefix_adds_it(self) -> None:
        assert validate_semver("1.2.3") == "v1.2.3"

    def test_valid_prerelease(self) -> None:
        assert validate_semver("v1.0.0-beta.1") == "v1.0.0-beta.1"

    def test_none_returns_default(self) -> None:
        assert validate_semver(None) == DEFAULT_VERSION

    def test_empty_string_returns_default(self) -> None:
        assert validate_semver("") == DEFAULT_VERSION

    def test_non_string_returns_default(self) -> None:
        assert validate_semver(123) == DEFAULT_VERSION

    def test_incomplete_version_returns_default(self) -> None:
        assert validate_semver("v1.1") == DEFAULT_VERSION

    def test_word_returns_default(self) -> None:
        assert validate_semver("latest") == DEFAULT_VERSION

    def test_whitespace_stripped(self) -> None:
        assert validate_semver("  v1.0.0  ") == "v1.0.0"


class TestParseSemver:
    """Tests for the parse_semver function."""

    def test_parse_valid(self) -> None:
        assert parse_semver("v1.2.3") == (1, 2, 3)

    def test_parse_without_prefix(self) -> None:
        assert parse_semver("1.2.3") == (1, 2, 3)

    def test_parse_zeros(self) -> None:
        assert parse_semver("v0.0.0") == (0, 0, 0)

    def test_parse_two_part_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_semver("v1.2")

    def test_parse_garbage_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_semver("latest")

    def test_parse_prerelease_strips_suffix(self) -> None:
        assert parse_semver("v1.0.0-beta.1") == (1, 0, 0)
        assert parse_semver("v2.1.3-rc1") == (2, 1, 3)
        assert parse_semver("v1.0.0-alpha") == (1, 0, 0)

    def test_comparison(self) -> None:
        assert parse_semver("v1.0.1") > parse_semver("v1.0.0")
        assert parse_semver("v1.1.0") > parse_semver("v1.0.9")
        assert parse_semver("v2.0.0") > parse_semver("v1.99.99")
