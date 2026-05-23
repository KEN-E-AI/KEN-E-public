"""Unit tests for app.adk.deploy_ken_e._append_chat_env_vars.

Guards the CH-PRD-01 internal-OIDC bridge from regressing into the
silent-fallback behavior that shipped a literal `sm://...` string as
CHAT_INTERNAL_API_URL across all three environments. The function MUST
refuse to write a deployment env that would route the bridge to a broken
target.
"""

from pathlib import Path

import pytest

from app.adk import deploy_ken_e

ENV_CONFIG = {
    "chat_internal_api_url": "sm://000000000000/kene-api-url",
    "chat_internal_api_audience": "sm://000000000000/kene-api-url",
}


@pytest.fixture
def dest_env_file(tmp_path: Path) -> Path:
    path = tmp_path / ".env"
    path.write_text("EXISTING=value\n")
    return path


class TestAppendChatEnvVarsFailFast:
    def test_raises_when_resolution_returns_literal_sm_ref(
        self, monkeypatch: pytest.MonkeyPatch, dest_env_file: Path
    ) -> None:
        monkeypatch.setattr(
            deploy_ken_e,
            "get_env_or_secret",
            lambda key: f"sm://000000000000/{key}",
        )

        with pytest.raises(RuntimeError, match="did not resolve to a concrete URL"):
            deploy_ken_e._append_chat_env_vars(ENV_CONFIG, dest_env_file)

        assert dest_env_file.read_text() == "EXISTING=value\n"

    def test_raises_when_resolution_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, dest_env_file: Path
    ) -> None:
        monkeypatch.setattr(deploy_ken_e, "get_env_or_secret", lambda key: None)

        with pytest.raises(RuntimeError, match="did not resolve to a concrete URL"):
            deploy_ken_e._append_chat_env_vars(ENV_CONFIG, dest_env_file)

    def test_raises_when_get_env_or_secret_raises(
        self, monkeypatch: pytest.MonkeyPatch, dest_env_file: Path
    ) -> None:
        def _boom(key: str) -> str:
            raise RuntimeError("Secret kene-api-url not found in project")

        monkeypatch.setattr(deploy_ken_e, "get_env_or_secret", _boom)

        with pytest.raises(RuntimeError, match="Secret kene-api-url not found"):
            deploy_ken_e._append_chat_env_vars(ENV_CONFIG, dest_env_file)

    def test_raises_when_secrets_module_unavailable(
        self, monkeypatch: pytest.MonkeyPatch, dest_env_file: Path
    ) -> None:
        monkeypatch.setattr(deploy_ken_e, "get_env_or_secret", None)

        with pytest.raises(RuntimeError, match="get_env_or_secret is unavailable"):
            deploy_ken_e._append_chat_env_vars(ENV_CONFIG, dest_env_file)

    def test_writes_resolved_url_on_success(
        self, monkeypatch: pytest.MonkeyPatch, dest_env_file: Path
    ) -> None:
        resolved_url = "https://kene-api-staging-d3wm5f7uba-uc.a.run.app"
        monkeypatch.setattr(deploy_ken_e, "get_env_or_secret", lambda key: resolved_url)

        deploy_ken_e._append_chat_env_vars(ENV_CONFIG, dest_env_file)

        contents = dest_env_file.read_text()
        assert f"CHAT_INTERNAL_API_URL={resolved_url}" in contents
        assert f"CHAT_INTERNAL_API_AUDIENCE={resolved_url}" in contents
        assert "sm://" not in contents

    def test_skips_when_chat_url_not_configured(
        self, monkeypatch: pytest.MonkeyPatch, dest_env_file: Path
    ) -> None:
        called = {"count": 0}

        def _tracking(key: str) -> str:
            called["count"] += 1
            return "should-not-be-used"

        monkeypatch.setattr(deploy_ken_e, "get_env_or_secret", _tracking)

        deploy_ken_e._append_chat_env_vars({}, dest_env_file)

        assert called["count"] == 0
        assert dest_env_file.read_text() == "EXISTING=value\n"
