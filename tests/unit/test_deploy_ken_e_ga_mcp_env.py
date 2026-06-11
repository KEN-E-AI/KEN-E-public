"""Unit tests for app.adk.deploy_ken_e._append_ga_mcp_env_var.

Guards against the silent regression that shipped a dev agent engine with no
GA MCP toolset: ``GA_MCP_SERVER_URL`` was never injected into the deploy
process env (only staging/prod CD set it), and a missing value is caught and
the GA toolset silently dropped by ``mcp.load_toolsets_for_specialist``.

The fix makes the URL an in-code per-env constant (``ENV_CONFIG``) and refuses
to deploy if it cannot resolve to a concrete URL — the same fail-loud contract
as ``CHAT_INTERNAL_API_URL``. The helper is the single authoritative writer of
the value into the deployed ``.env`` (de-duping any line ``process_env_file``
copied from the gitignored ``.env.<env>`` file).
"""

import os
from pathlib import Path

import pytest

from app.adk import deploy_ken_e

ENV_CONFIG = {
    "ga_mcp_server_url": "https://google-analytics-mcp-4quwenkusq-uc.a.run.app",
}


@pytest.fixture
def dest_env_file(tmp_path: Path) -> Path:
    path = tmp_path / ".env"
    path.write_text("EXISTING=value\n")
    return path


@pytest.fixture(autouse=True)
def _clear_ga_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GA_MCP_SERVER_URL", raising=False)


class TestAppendGaMcpEnvVarFailFast:
    def test_raises_when_resolution_returns_literal_sm_ref(
        self, monkeypatch: pytest.MonkeyPatch, dest_env_file: Path
    ) -> None:
        monkeypatch.setattr(
            deploy_ken_e,
            "get_env_or_secret",
            lambda key: f"sm://000000000000/{key}",
        )

        with pytest.raises(RuntimeError, match="did not resolve to a concrete URL"):
            deploy_ken_e._append_ga_mcp_env_var(ENV_CONFIG, dest_env_file)

        assert dest_env_file.read_text() == "EXISTING=value\n"

    def test_raises_when_resolution_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, dest_env_file: Path
    ) -> None:
        monkeypatch.setattr(deploy_ken_e, "get_env_or_secret", lambda key: None)

        with pytest.raises(RuntimeError, match="did not resolve to a concrete URL"):
            deploy_ken_e._append_ga_mcp_env_var(ENV_CONFIG, dest_env_file)

    def test_raises_when_secrets_module_unavailable(
        self, monkeypatch: pytest.MonkeyPatch, dest_env_file: Path
    ) -> None:
        monkeypatch.setattr(deploy_ken_e, "get_env_or_secret", None)

        with pytest.raises(RuntimeError, match="get_env_or_secret is unavailable"):
            deploy_ken_e._append_ga_mcp_env_var(ENV_CONFIG, dest_env_file)

    def test_writes_resolved_url_and_sets_process_env_on_success(
        self, monkeypatch: pytest.MonkeyPatch, dest_env_file: Path
    ) -> None:
        url = ENV_CONFIG["ga_mcp_server_url"]
        monkeypatch.setattr(deploy_ken_e, "get_env_or_secret", lambda key: url)

        deploy_ken_e._append_ga_mcp_env_var(ENV_CONFIG, dest_env_file)

        contents = dest_env_file.read_text()
        assert f"GA_MCP_SERVER_URL={url}" in contents
        # The deploy process env is set so any deploy-time consumer resolves it.
        assert os.environ["GA_MCP_SERVER_URL"] == url

    def test_is_single_authoritative_writer_no_duplicate(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # process_env_file may have already copied a GA line from the gitignored
        # .env.<env>; the helper must replace it, not append a duplicate.
        stale = "https://stale-ga.example.com"
        dest = tmp_path / ".env"
        dest.write_text(f"EXISTING=value\nGA_MCP_SERVER_URL={stale}\nOTHER=1\n")
        url = ENV_CONFIG["ga_mcp_server_url"]
        monkeypatch.setattr(deploy_ken_e, "get_env_or_secret", lambda key: url)

        deploy_ken_e._append_ga_mcp_env_var(ENV_CONFIG, dest)

        contents = dest.read_text()
        assert contents.count("GA_MCP_SERVER_URL=") == 1
        assert f"GA_MCP_SERVER_URL={url}" in contents
        assert stale not in contents
        assert "EXISTING=value" in contents
        assert "OTHER=1" in contents

    def test_skips_when_ga_url_not_configured(
        self, monkeypatch: pytest.MonkeyPatch, dest_env_file: Path
    ) -> None:
        called = {"count": 0}

        def _tracking(key: str) -> str:
            called["count"] += 1
            return "should-not-be-used"

        monkeypatch.setattr(deploy_ken_e, "get_env_or_secret", _tracking)

        deploy_ken_e._append_ga_mcp_env_var({}, dest_env_file)

        assert called["count"] == 0
        assert dest_env_file.read_text() == "EXISTING=value\n"


class TestEnvConfigHasGaUrl:
    def test_every_env_defines_a_concrete_ga_url(self) -> None:
        for env, cfg in deploy_ken_e.ENV_CONFIG.items():
            url = cfg.get("ga_mcp_server_url", "")
            assert url and not url.startswith("sm://"), (
                f"ENV_CONFIG[{env!r}] must define a concrete ga_mcp_server_url so "
                "the GA specialist never deploys with a silently-dropped toolset"
            )
