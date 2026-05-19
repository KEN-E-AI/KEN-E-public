"""Unit tests for api/src/kene_api/chat/context_windows.py (CH-PRD-01 §7 AC-11)."""

import subprocess
import sys
from pathlib import Path

import pytest
from src.kene_api.chat.context_windows import (
    MODEL_CONTEXT_WINDOW_REGISTRY,
    get_model_context_window,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[4]
LINT_SCRIPT = (
    REPO_ROOT / "api" / "scripts" / "lint" / "check_context_window_registry_coverage.py"
)

# Models that are deployed in non-test code under app/adk/agents/
DEPLOYED_MODEL_IDS = frozenset(
    {
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gpt-4o",
        "gpt-4o-2024-08-06",
    }
)


# ---------------------------------------------------------------------------
# Registry content
# ---------------------------------------------------------------------------


class TestRegistryCoversDeployedModels:
    def test_all_deployed_models_are_registered(self) -> None:
        missing = DEPLOYED_MODEL_IDS - set(MODEL_CONTEXT_WINDOW_REGISTRY.keys())
        assert not missing, (
            f"Deployed models missing from registry: {missing}. "
            "Add them to api/src/kene_api/chat/context_windows.py."
        )

    def test_context_window_max_is_positive_for_each_entry(self) -> None:
        for model_id in DEPLOYED_MODEL_IDS:
            entry = MODEL_CONTEXT_WINDOW_REGISTRY[model_id]
            assert entry.context_window_max > 0, (
                f"{model_id}: context_window_max must be positive"
            )

    def test_no_pricing_fields_on_any_entry(self) -> None:
        for entry in MODEL_CONTEXT_WINDOW_REGISTRY.values():
            assert not hasattr(entry, "cost_per_input_token")
            assert not hasattr(entry, "cost_per_output_token")
            assert not hasattr(entry, "price")

    def test_registry_keys_match_entry_model_id(self) -> None:
        for key, entry in MODEL_CONTEXT_WINDOW_REGISTRY.items():
            assert key == entry.model_id, (
                f"Registry key '{key}' does not match entry.model_id '{entry.model_id}'"
            )

    def test_gemini_context_windows_are_one_million_plus(self) -> None:
        for model_id in ("gemini-2.5-flash", "gemini-2.5-pro"):
            entry = MODEL_CONTEXT_WINDOW_REGISTRY[model_id]
            assert entry.context_window_max >= 1_000_000, (
                f"{model_id}: expected context_window_max >= 1M, got {entry.context_window_max}"
            )

    def test_gpt4o_context_window(self) -> None:
        for model_id in ("gpt-4o", "gpt-4o-2024-08-06"):
            entry = MODEL_CONTEXT_WINDOW_REGISTRY[model_id]
            assert entry.context_window_max == 128_000


# ---------------------------------------------------------------------------
# get_model_context_window helper
# ---------------------------------------------------------------------------


class TestGetModelContextWindow:
    def test_returns_entry_for_known_model(self) -> None:
        entry = get_model_context_window("gemini-2.5-pro")
        assert entry.model_id == "gemini-2.5-pro"
        assert entry.context_window_max > 0

    def test_raises_keyerror_for_unknown_model(self) -> None:
        with pytest.raises(KeyError) as exc_info:
            get_model_context_window("not-a-real-model")
        # Error message must name the registry path so the caller knows how to fix it
        error_text = str(exc_info.value)
        assert "not-a-real-model" in error_text
        assert "context_windows" in error_text

    def test_returns_entry_for_each_deployed_model(self) -> None:
        for model_id in DEPLOYED_MODEL_IDS:
            entry = get_model_context_window(model_id)
            assert entry.model_id == model_id


# ---------------------------------------------------------------------------
# Lint script: clean tree
# ---------------------------------------------------------------------------


class TestLintScript:
    def test_lint_passes_on_clean_tree(self) -> None:
        """The lint script should exit 0 on the current (clean) tree."""
        result = subprocess.run(
            [sys.executable, str(LINT_SCRIPT)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Lint script failed on clean tree.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_lint_fails_on_unregistered_model(self, tmp_path: Path) -> None:
        """A file with model='not-real-model' must cause the lint to exit
        non-zero and name the unregistered model.

        The fixture is written into pytest's tmp_path and the lint is pointed
        at it via --agents-root, so the real source tree is never mutated —
        no leftover-on-crash risk, and the test is safe under pytest-xdist.
        """
        fixture_file = tmp_path / "agent.py"
        fixture_file.write_text(
            "# lint fixture — scanned only via --agents-root\n"
            "class _FakeAgent:\n"
            "    pass\n"
            "\n"
            "# Call-site kwarg — the lint checks ast.Call keyword args:\n"
            "_agent = _FakeAgent(model='not-real-model')\n"
        )

        result = subprocess.run(
            [sys.executable, str(LINT_SCRIPT), "--agents-root", str(tmp_path)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, (
            "Lint script should exit non-zero when an unregistered model literal exists"
        )
        combined = result.stdout + result.stderr
        assert "not-real-model" in combined, (
            f"Lint output should name the unregistered model.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
