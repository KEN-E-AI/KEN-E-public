"""Regression test: GA token refresh must resolve sm:// client credentials.

`refresh_if_expired` previously read GOOGLE_OAUTH_CLIENT_ID via os.getenv, which
returns the unresolved "sm://GOOGLE_OAUTH_CLIENT_ID" literal in environments that
store it as a Secret Manager reference. Google then rejects the refresh with
invalid_client, so an expired GA token never refreshes and the agent reports an
auth error. The fix routes the client_id through get_env_or_secret (sm://-aware).
"""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.kene_api.services.ga_credential_helper import GACredentialHelper


@pytest.mark.asyncio
async def test_refresh_sends_resolved_client_id_not_sm_literal():
    helper = GACredentialHelper(MagicMock())
    helper.creds_service.update_credentials = AsyncMock()

    expired_creds = {
        "access_token": "old",
        "refresh_token": "refresh-tok",
        # Expired an hour ago → triggers the refresh path.
        "expires_at": datetime.datetime.now().timestamp() - 3600,
    }

    captured: dict = {}

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"access_token": "new", "expires_in": 3600}

    async def fake_post(url, data=None):
        captured["data"] = data
        return mock_resp

    def fake_secret(key, default=None):
        # Trailing newline/space simulates the Secret Manager value that broke
        # refresh with invalid_client — must be stripped before use.
        return {
            "GOOGLE_OAUTH_CLIENT_ID": "real-client-id.apps.googleusercontent.com\n",
            "GOOGLE_OAUTH_CLIENT_SECRET": "real-secret ",
        }.get(key, default)

    with (
        patch("shared.secrets.get_env_or_secret", side_effect=fake_secret),
        patch(
            "src.kene_api.services.ga_credential_helper.httpx.AsyncClient"
        ) as mock_client_cls,
    ):
        client = mock_client_cls.return_value.__aenter__.return_value
        client.post = fake_post
        result = await helper.refresh_if_expired("acc_x", expired_creds)

    # Refresh succeeded and the access token was updated.
    assert result is not None
    assert result["access_token"] == "new"
    # The resolved client_id (NOT an "sm://..." literal) was sent to Google.
    assert captured["data"]["client_id"] == "real-client-id.apps.googleusercontent.com"
    assert captured["data"]["client_secret"] == "real-secret"
