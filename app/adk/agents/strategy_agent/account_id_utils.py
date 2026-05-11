"""Shared ``account_id`` validation for the analytics-agent Firestore paths.

The analytics services interpolate ``account_id`` directly into Firestore
*collection* path segments (``accounts/{account_id}/{resource}``). A value
containing ``/`` (or other unexpected characters) would silently change the
path depth — e.g. ``accounts/../../x/agent_analytics`` — instead of raising.
Validate at construction time and fail loudly.
"""

import re

_VALID_ACCOUNT_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")


def validate_account_id(account_id: str) -> str:
    """Return ``account_id`` unchanged if it is well-formed; raise ``ValueError`` otherwise.

    Well-formed = 1 to 128 characters drawn from ``[a-zA-Z0-9_-]`` (the production
    ``acc_<uuid>`` shape, plus the literal IDs used in tests).
    """
    if not isinstance(account_id, str) or not _VALID_ACCOUNT_ID_RE.match(account_id):
        raise ValueError(
            f"account_id {account_id!r} is invalid; must match [a-zA-Z0-9_-]{{1,128}}"
        )
    return account_id
