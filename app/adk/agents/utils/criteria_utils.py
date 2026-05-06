"""Shared utilities for sanitising acceptance-criteria strings.

Extracted from dispatch_handlers.py so that agent_factory/dispatch.py and
any future dispatch wrappers can share the same sanitisation logic without
duplicating the regex or the 2000-character cap constant.
"""

from __future__ import annotations

import re

# Hard cap on acceptance_criteria length before sanitisation.
# Matches the upstream guard applied by all dispatch handlers.
MAX_CRITERIA_CHARS: int = 2000

# Allow only printable ASCII minus control characters (no angle brackets,
# backtick, or curly braces that could be misread as template variables or
# HTML by the LLM).
_UNSAFE_CRITERIA_RE: re.Pattern[str] = re.compile(r"[^\w\s.,;:()\-'\"!?%@&=+/#*]")


def sanitise_criteria(raw: str) -> str:
    """Remove characters that could break prompt structure or inject template variables.

    Applied to acceptance_criteria before it is interpolated into LLM system
    prompts by build_review_pipeline(), so that a manipulated root-agent
    response cannot redirect sub-agent behaviour via structural injection.
    The MAX_CRITERIA_CHARS hard cap upstream bounds the total length.

    Args:
        raw: The raw acceptance_criteria string from the caller.

    Returns:
        The sanitised string with unsafe characters removed.
    """
    return _UNSAFE_CRITERIA_RE.sub("", raw)
