"""Unit tests for criteria_utils.sanitise_criteria.

Covers the Unicode security classes mandated by AH-74 plus ASCII allow-list
roundtrip regression tests.
"""

from __future__ import annotations

import logging

import pytest

from app.adk.agents.utils.criteria_utils import sanitise_criteria

# ---------------------------------------------------------------------------
# ASCII allow-list roundtrip — every char in the explicit allow-list must
# survive sanitisation unchanged.
# ---------------------------------------------------------------------------


def test_ascii_letters_pass_through() -> None:
    assert (
        sanitise_criteria("abcdefghijklmnopqrstuvwxyz") == "abcdefghijklmnopqrstuvwxyz"
    )
    assert (
        sanitise_criteria("ABCDEFGHIJKLMNOPQRSTUVWXYZ") == "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    )


def test_ascii_digits_pass_through() -> None:
    assert sanitise_criteria("0123456789") == "0123456789"


def test_underscore_passes_through() -> None:
    assert sanitise_criteria("snake_case_name") == "snake_case_name"


def test_whitespace_passes_through() -> None:
    assert sanitise_criteria("hello world\ttab\nnewline") == "hello world\ttab\nnewline"


@pytest.mark.parametrize(
    "char",
    [
        ".",
        ",",
        ";",
        ":",
        "(",
        ")",
        "-",
        "'",
        '"',
        "!",
        "?",
        "%",
        "@",
        "&",
        "=",
        "+",
        "/",
        "#",
        "*",
    ],
)
def test_punctuation_passes_through(char: str) -> None:
    payload = f"before{char}after"
    assert sanitise_criteria(payload) == payload


def test_typical_criteria_unchanged() -> None:
    criteria = (
        "1. Response must include at least 3 data points. "
        "2. Each point must be cited with a source URL. "
        "3. The summary must be under 200 words."
    )
    assert sanitise_criteria(criteria) == criteria


# ---------------------------------------------------------------------------
# Non-ASCII whitespace — U+00A0 NO-BREAK SPACE and U+3000 IDEOGRAPHIC SPACE
# must be stripped; only explicit ASCII whitespace ([ \t\n\r\f\v]) is allowed.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,char",
    [
        ("NO-BREAK SPACE U+00A0", chr(0x00A0)),
        ("IDEOGRAPHIC SPACE U+3000", chr(0x3000)),
    ],
)
def test_non_ascii_whitespace_stripped(name: str, char: str) -> None:
    assert sanitise_criteria(f"hello{char}world") == "helloworld", (
        f"{name} not stripped"
    )


# ---------------------------------------------------------------------------
# Zero-width / Cf-class characters — already stripped by old regex, confirmed
# as regression guard.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,char",
    [
        ("ZWSP U+200B", "​"),
        ("ZWNJ U+200C", "‌"),
        ("ZWJ  U+200D", "‍"),
    ],
)
def test_zero_width_chars_stripped(name: str, char: str) -> None:
    assert sanitise_criteria(f"hello{char}world") == "helloworld", (
        f"{name} not stripped"
    )


def test_bom_stripped() -> None:
    assert sanitise_criteria("﻿hello") == "hello"


@pytest.mark.parametrize(
    "name,char",
    [
        ("LRE U+202A", "‪"),
        ("RLE U+202B", "‫"),
        ("PDF U+202C", "‬"),
        ("LRO U+202D", "‭"),
        ("RLO U+202E", "‮"),
    ],
)
def test_bidi_overrides_stripped(name: str, char: str) -> None:
    assert sanitise_criteria(f"hello{char}world") == "helloworld", (
        f"{name} not stripped"
    )


# ---------------------------------------------------------------------------
# Cyrillic confusables — NEW: these are stripped by the updated regex but
# survived the old Unicode-aware \w pattern.
# ---------------------------------------------------------------------------


def test_cyrillic_a_confusable_stripped() -> None:
    # Cyrillic small letter a (U+0430) looks identical to Latin a but is a different code point.
    # The function must strip it — NOT transliterate, just remove.
    cyrillic_a = "\u0430"  # Cyrillic small letter a (U+0430)
    result = sanitise_criteria(f"{cyrillic_a}pple")
    assert result == "pple", f"Cyrillic a/U+0430 not stripped; got {result!r}"
    # Verify it is NOT equal to 'apple' (would indicate transliteration or passthrough)
    assert result != "apple"


def test_cyrillic_word_stripped() -> None:
    # A word composed entirely of Cyrillic letters should become empty.
    moscow = "Москва"  # All Cyrillic
    result = sanitise_criteria(moscow)
    assert result == "", f"Cyrillic word not stripped; got {result!r}"


def test_mixed_ascii_cyrillic_strips_only_cyrillic() -> None:
    # Only the Cyrillic characters are removed; ASCII letters survive.
    mixed = "\u0430dmin"  # Cyrillic a (U+0430) + Latin dmin
    result = sanitise_criteria(mixed)
    assert result == "dmin"


# ---------------------------------------------------------------------------
# Warning log emitted when characters are stripped.
# ---------------------------------------------------------------------------


def test_warning_emitted_when_chars_stripped(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="app.adk.agents.utils.criteria_utils"):
        sanitise_criteria("hello\u0430world")  # Cyrillic a (U+0430)

    assert any(
        "unsafe character(s) stripped" in record.message for record in caplog.records
    )


def test_no_warning_when_input_is_clean(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="app.adk.agents.utils.criteria_utils"):
        sanitise_criteria("clean ASCII criteria 123")

    assert not any(
        "unsafe character(s) stripped" in record.message for record in caplog.records
    )


# ---------------------------------------------------------------------------
# Combined cocktail — string mixing multiple unsafe classes at once.
# ---------------------------------------------------------------------------


def test_combined_unsafe_string_yields_clean_ascii() -> None:
    # Cyrillic confusable + ZWSP + BOM + bidi override
    dirty = "\u0430dmin​﻿‮must"  # Cyrillic a/U+0430 + ZWSP/U+200B + BOM/U+FEFF + RLO/U+202E + must
    result = sanitise_criteria(dirty)
    assert result == "dminmust"


def test_empty_string_returns_empty() -> None:
    assert sanitise_criteria("") == ""


def test_all_unsafe_returns_empty() -> None:
    assert sanitise_criteria("\u0430​﻿‮") == ""
