# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Firebase ID token helper for the KEN-E Chat sidebar polling load test.

This module mints a Firebase ID token for a dedicated load-test user so that
Locust workers can authenticate against the KEN-E API without performing a
full sign-in flow on every virtual user.

Required environment variables
-------------------------------
FIREBASE_WEB_API_KEY
    The Firebase web API key (found in the Firebase console under Project
    Settings → General → Web API Key).  This is *not* a service-account key.
FIREBASE_PROJECT_ID
    The target Firebase project (e.g. ``ken-e-staging``).
FIREBASE_ADMIN_SA_EMAIL
    The target project's Firebase Admin SDK service account, formatted as
    ``firebase-adminsdk-*@<project>.iam.gserviceaccount.com``.  The caller
    must hold ``roles/iam.serviceAccountTokenCreator`` on this SA so the
    Admin SDK can sign custom tokens for the target project via signBlob.
CHAT_LOADTEST_UID
    The Firebase Auth UID of the pre-created load-test user account.

Usage
-----
    from chat_load_test_auth import get_id_token

    token = get_id_token()
    headers = {"Authorization": f"Bearer {token}"}

The first call fetches and caches the token; subsequent calls return the
cached value.  To force a refresh, set the module-level ``_cached_id_token``
back to ``None`` before calling ``get_id_token()`` again.
"""

import logging
import os
import time

import firebase_admin
import requests
from firebase_admin import auth as fb_auth

logger = logging.getLogger(__name__)

_firebase_app: firebase_admin.App | None = None
_cached_id_token: str | None = None
_token_expiry: float = 0.0  # epoch seconds; 0 means "not yet fetched"

_SIGN_IN_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken"
)
# Re-fetch the token this many seconds before its actual expiry.
_TOKEN_REFRESH_BUFFER_SECONDS = 300  # 5 minutes


def _ensure_firebase() -> None:
    """Initialize the Firebase Admin SDK exactly once.

    Binds the SDK to the target Firebase project and tells it which service
    account to sign custom tokens as.  Both are required when running from
    Cloud Build: ADC otherwise resolves to the build project and signs custom
    tokens as the build service account, so ``signInWithCustomToken`` against
    the target project's API key returns 400.

    Required env vars (load-test step sets both via Cloud Build substitutions):
        FIREBASE_PROJECT_ID         — target project (e.g. ``ken-e-staging``)
        FIREBASE_ADMIN_SA_EMAIL     — the project's Firebase Admin SDK SA
                                      (``firebase-adminsdk-*@<project>.iam.gserviceaccount.com``).
                                      The caller must hold
                                      ``roles/iam.serviceAccountTokenCreator``
                                      on this SA so the Admin SDK can sign
                                      custom tokens via signBlob.
    """
    global _firebase_app
    if _firebase_app is not None:
        return

    project_id = os.environ.get("FIREBASE_PROJECT_ID")
    if not project_id:
        raise RuntimeError(
            "Required environment variable FIREBASE_PROJECT_ID is not set"
        )

    admin_sa_email = os.environ.get("FIREBASE_ADMIN_SA_EMAIL")
    if not admin_sa_email:
        raise RuntimeError(
            "Required environment variable FIREBASE_ADMIN_SA_EMAIL is not set"
        )

    _firebase_app = firebase_admin.initialize_app(
        options={"projectId": project_id, "serviceAccountId": admin_sa_email}
    )


def _exchange_custom_token(custom_token_str: str, api_key: str) -> tuple[str, int]:
    """Exchange a Firebase custom token for a Firebase ID token.

    Separated into its own function so that tests can monkey-patch it without
    touching the Firebase Admin SDK initialization path.

    Args:
        custom_token_str: The custom token string produced by the Admin SDK.
        api_key: The Firebase web API key.

    Returns:
        Tuple of ``(idToken, expiresIn)`` from the Identity Toolkit response.

    Raises:
        RuntimeError: On any network error or if the response does not contain
            an ``idToken`` field.
    """
    try:
        response = requests.post(
            _SIGN_IN_URL,
            params={"key": api_key},
            json={"token": custom_token_str, "returnSecureToken": True},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Failed to exchange custom token with Firebase Identity Toolkit: {exc}"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "Firebase Identity Toolkit returned a non-JSON response"
        ) from exc

    id_token = payload.get("idToken")
    if not id_token:
        raise RuntimeError(
            "Firebase Identity Toolkit response did not contain an 'idToken' field"
        )

    expires_in = int(payload.get("expiresIn", 3600))
    return str(id_token), expires_in


def get_id_token() -> str:
    """Return a Firebase ID token for the load-test user.

    The token is cached at module level after the first successful fetch.
    Subsequent calls return the cached value until the token is within
    ``_TOKEN_REFRESH_BUFFER_SECONDS`` of expiry, at which point a fresh
    token is minted automatically.  Firebase ID tokens expire after 1 hour.

    Returns:
        A Firebase ID token string suitable for use in an ``Authorization:
        Bearer <token>`` header.

    Raises:
        RuntimeError: If required environment variables are absent, or if
            token minting or exchange fails.
    """
    global _cached_id_token, _token_expiry

    if (
        _cached_id_token is not None
        and time.time() < _token_expiry - _TOKEN_REFRESH_BUFFER_SECONDS
    ):
        logger.debug(
            "Returning cached Firebase ID token (%.0fs remaining)",
            _token_expiry - time.time(),
        )
        return _cached_id_token

    api_key = os.environ.get("FIREBASE_WEB_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Required environment variable FIREBASE_WEB_API_KEY is not set"
        )

    uid = os.environ.get("CHAT_LOADTEST_UID")
    if not uid:
        raise RuntimeError("Required environment variable CHAT_LOADTEST_UID is not set")

    _ensure_firebase()

    custom_token_bytes: bytes = fb_auth.create_custom_token(uid)
    custom_token_str = custom_token_bytes.decode("utf-8")

    id_token, expires_in = _exchange_custom_token(custom_token_str, api_key)

    _cached_id_token = id_token
    _token_expiry = time.time() + expires_in
    logger.info(
        "Fetched and cached new Firebase ID token for load-test user (expires_in=%ds)",
        expires_in,
    )

    return _cached_id_token
