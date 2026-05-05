"""OAuth header-provider factory for MCP toolset construction (AH-PRD-02 §5.3).

Each `mcp_servers/{server_id}` Firestore document carries an `auth_type` field.
`_make_header_provider(auth_type)` converts that value into a closure the ADK
`McpToolset(header_provider=...)` callsite accepts.

Credential source (current): session state keys listed in CREDENTIAL_KEYS.
Future replacement (IN-PRD-06): closure body will be rewritten to call
  GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}
instead of reading session state.  The closure signature, the header_provider=
callsite, and the fail-fast-on-unknown-auth-type behaviour here remain stable —
only the credential source moves.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.adk.agents.readonly_context import ReadonlyContext

# Maps every auth_type value recognised by the factory to the session-state
# credential key it reads.  Unknown values raise ValueError at factory build
# time (not inside the returned closure) so config typos surface before deploy.
CREDENTIAL_KEYS: dict[str, str] = {
    "ga_oauth": "ga_credentials",
    "google_ads_oauth": "google_ads_credentials",
    "meta_ads_oauth": "meta_ads_credentials",
    "mailchimp_oauth": "mailchimp_credentials",
}


def _make_header_provider(
    auth_type: str,
) -> Callable[[ReadonlyContext], dict[str, str]]:
    """Return an ADK header-provider closure for the given OAuth auth type.

    The closure reads the corresponding session-state credential key on every
    MCP call and emits:
      - ``Authorization: Bearer <access_token>``  (omitted when token is falsy)
      - ``X-Tenant-ID: <tenant_id>``              (omitted when tenant_id is falsy)

    Args:
        auth_type: One of the keys in CREDENTIAL_KEYS
            (``"ga_oauth"``, ``"google_ads_oauth"``, ``"meta_ads_oauth"``,
            ``"mailchimp_oauth"``).

    Returns:
        A callable ``(ReadonlyContext) -> dict[str, str]`` suitable for
        ``McpToolset(header_provider=...)``.

    Raises:
        ValueError: If ``auth_type`` is not a recognised value — raised
            synchronously at factory build time, not inside the closure.
    """
    if auth_type not in CREDENTIAL_KEYS:
        raise ValueError(
            f"Unknown auth_type {auth_type!r}. "
            f"Valid values: {sorted(CREDENTIAL_KEYS)}"
        )
    state_key = CREDENTIAL_KEYS[auth_type]

    def header_provider(context: ReadonlyContext) -> dict[str, str]:
        creds: dict[str, str] = context.state.get(state_key, {})
        headers: dict[str, str] = {}
        if token := creds.get("access_token", ""):
            headers["Authorization"] = f"Bearer {token}"
        if tenant_id := creds.get("tenant_id", ""):
            headers["X-Tenant-ID"] = tenant_id
        return headers

    return header_provider
