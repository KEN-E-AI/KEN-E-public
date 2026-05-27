"""Shared utilities for sanitising acceptance-criteria strings.

Extracted from dispatch_handlers.py so that agent_factory/dispatch.py and
any future dispatch wrappers can share the same sanitisation logic without
duplicating the regex or the 2000-character cap constant.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Hard cap on acceptance_criteria length before sanitisation.
# Matches the upstream guard applied by all dispatch handlers.
MAX_CRITERIA_CHARS: int = 2000

# Allow only explicit printable ASCII word characters plus common punctuation.
# Uses [A-Za-z0-9_] instead of \w so Unicode word characters (Cyrillic,
# Greek, etc.) that are visually similar to ASCII (confusables) are stripped
# rather than silently permitted into LLM system prompts.
# Uses [ \t\n\r\f\v] instead of \s so non-ASCII whitespace (U+00A0 NO-BREAK
# SPACE, U+3000 IDEOGRAPHIC SPACE, etc.) is also stripped — Python's \s is
# Unicode-aware and would otherwise let those through.
# Strips: any char not in the explicit allow-list, which includes —
#   * Unicode confusables (e.g. Cyrillic small letter "a", U+0430)
#   * Non-ASCII whitespace (U+00A0 NO-BREAK SPACE, U+3000 IDEOGRAPHIC SPACE, etc.)
#   * Cf-class invisible formatting chars (ZWSP U+200B, ZWNJ U+200C, ZWJ U+200D)
#   * BOM (U+FEFF)
#   * Bidi override marks (U+202A-U+202E)
#   * Any other non-ASCII character
_UNSAFE_CRITERIA_RE: re.Pattern[str] = re.compile(
    r"[^A-Za-z0-9_ \t\n\r\f\v.,;:()\-'\"!?%@&=+/#*]"
)


def sanitise_criteria(raw: str) -> str:
    """Remove characters that could break prompt structure or inject template variables.

    Applied to acceptance_criteria before it is interpolated into LLM system
    prompts by build_review_pipeline(), so that a manipulated root-agent
    response cannot redirect sub-agent behaviour via structural injection.
    The MAX_CRITERIA_CHARS hard cap upstream bounds the total length.

    This function is intentionally ASCII-conservative: only explicit ASCII
    printable characters are permitted. Non-ASCII Unicode word characters
    (including Cyrillic/Greek confusables) are stripped and logged at WARNING
    level so operators can detect unexpected non-ASCII input.

    Args:
        raw: The raw acceptance_criteria string from the caller.

    Returns:
        The sanitised string with unsafe characters removed.
    """
    sanitised = _UNSAFE_CRITERIA_RE.sub("", raw)
    stripped_count = len(raw) - len(sanitised)
    if stripped_count > 0:
        logger.warning(
            "[SANITISE-CRITERIA] %d unsafe character(s) stripped from input",
            stripped_count,
        )
    return sanitised
