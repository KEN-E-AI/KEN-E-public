"""FastAPI dependency for internal OIDC caller verification.

Used by endpoints reachable only from Cloud Run service-to-service calls
authenticated by Google-signed OIDC tokens.

CHAT_INTERNAL_OIDC_SKIP=true skips verification for emulator / local tests.
"""

from __future__ import annotations

import logging
import os

from fastapi import HTTPException, Request
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

logger = logging.getLogger(__name__)

# Comma-separated list of permitted service-account emails.
_ALLOWLIST_ENV = "CHAT_INTERNAL_SA_ALLOWLIST"
_AUDIENCE_ENV = "CHAT_INTERNAL_OIDC_AUDIENCE"
_SKIP_ENV = "CHAT_INTERNAL_OIDC_SKIP"


def verify_internal_oidc_caller(request: Request) -> str:
    """FastAPI dependency that verifies an inbound Google OIDC bearer token.

    Returns the verified service-account email on success.
    Raises HTTPException(401) on authentication failure or (403) if the caller's
    email is not in the allowlist. Raises HTTPException(500) if the server is
    misconfigured (missing audience or allowlist).
    """
    if os.getenv(_SKIP_ENV, "").lower() == "true":
        logger.warning("OIDC verification skipped (CHAT_INTERNAL_OIDC_SKIP=true)")
        return "oidc-skip@local"

    authorization: str = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization[len("Bearer "):]

    audience = os.getenv(_AUDIENCE_ENV, "")
    if not audience:
        logger.error("CHAT_INTERNAL_OIDC_AUDIENCE is not set")
        raise HTTPException(status_code=500, detail="Server misconfiguration: missing audience")

    allowlist_raw = os.getenv(_ALLOWLIST_ENV, "")
    allowlist = {e.strip() for e in allowlist_raw.split(",") if e.strip()}
    if not allowlist:
        logger.error("CHAT_INTERNAL_SA_ALLOWLIST is empty — denying all callers")
        raise HTTPException(status_code=500, detail="Server misconfiguration: allowlist not configured")

    try:
        id_info = id_token.verify_oauth2_token(token, GoogleRequest(), audience=audience)
    except Exception as exc:
        logger.warning("OIDC token verification failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid OIDC token") from exc

    if not id_info.get("email_verified"):
        logger.warning("OIDC token has unverified email claim")
        raise HTTPException(status_code=401, detail="Token email not verified")

    email: str = id_info.get("email", "")
    if email not in allowlist:
        logger.warning("OIDC caller %r not in allowlist", email)
        raise HTTPException(status_code=403, detail="Caller not authorized")

    return email
