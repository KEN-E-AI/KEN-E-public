"""Unit tests for app.utils.weave_observability."""

from unittest.mock import patch

import pytest


class TestInitWeaveIfNeeded:
    """Tests for the init_weave_if_needed idempotent initializer."""

    def _reset_module_state(self) -> None:
        """Reset the module-level _WEAVE_INITIALIZED flag between tests."""
        import app.utils.weave_observability as mod

        mod._WEAVE_INITIALIZED = False

    def setup_method(self) -> None:
        self._reset_module_state()

    def teardown_method(self) -> None:
        self._reset_module_state()

    @patch.dict("os.environ", {}, clear=True)
    @patch("app.utils.weave_observability.WEAVE_AVAILABLE", False)
    def test_graceful_degradation_when_weave_not_installed(self) -> None:
        from app.utils.weave_observability import init_weave_if_needed

        result = init_weave_if_needed()
        assert result is False

    @patch.dict("os.environ", {}, clear=True)
    @patch("app.utils.weave_observability.WEAVE_AVAILABLE", False)
    def test_weave_unavailable_permanently_short_circuits(self) -> None:
        """After WEAVE_AVAILABLE=False, second call short-circuits via _WEAVE_INITIALIZED."""
        import app.utils.weave_observability as mod
        from app.utils.weave_observability import init_weave_if_needed

        init_weave_if_needed()
        assert mod._WEAVE_INITIALIZED is True
        # Second call returns immediately without re-logging
        result = init_weave_if_needed()
        assert result is False

    @patch.dict("os.environ", {}, clear=True)
    @patch("app.utils.weave_observability.WEAVE_AVAILABLE", True)
    def test_graceful_degradation_when_api_key_missing(self) -> None:
        from app.utils.weave_observability import init_weave_if_needed

        with patch("app.utils.weave_observability.weave"):
            # Patch secret retrieval to return None
            with patch(
                "shared.secrets.get_env_or_secret", return_value=None
            ):
                result = init_weave_if_needed()
                assert result is False

    @patch.dict("os.environ", {"WANDB_API_KEY": "test-key"}, clear=False)
    @patch("app.utils.weave_observability.WEAVE_AVAILABLE", True)
    def test_successful_initialization(self) -> None:
        from app.utils.weave_observability import init_weave_if_needed

        mock_weave = patch("app.utils.weave_observability.weave").start()
        mock_weave.init.return_value = None

        result = init_weave_if_needed()
        assert result is True
        mock_weave.init.assert_called_once()
        patch.stopall()

    @patch.dict("os.environ", {"WANDB_API_KEY": "test-key"}, clear=False)
    @patch("app.utils.weave_observability.WEAVE_AVAILABLE", True)
    def test_idempotent_second_call_is_noop(self) -> None:
        from app.utils.weave_observability import init_weave_if_needed

        mock_weave = patch("app.utils.weave_observability.weave").start()
        mock_weave.init.return_value = None

        init_weave_if_needed()
        init_weave_if_needed()
        # Only one call to weave.init regardless of how many times we call
        mock_weave.init.assert_called_once()
        patch.stopall()

    @patch.dict("os.environ", {"WANDB_API_KEY": "test-key"}, clear=False)
    @patch("app.utils.weave_observability.WEAVE_AVAILABLE", True)
    def test_graceful_degradation_when_init_raises(self) -> None:
        from app.utils.weave_observability import init_weave_if_needed

        mock_weave = patch("app.utils.weave_observability.weave").start()
        mock_weave.init.side_effect = RuntimeError("connection failed")

        result = init_weave_if_needed()
        assert result is False
        patch.stopall()

    @patch.dict("os.environ", {}, clear=True)
    @patch("app.utils.weave_observability.WEAVE_AVAILABLE", False)
    def test_required_raises_when_weave_not_installed(self) -> None:
        from app.utils.weave_observability import init_weave_if_needed

        with pytest.raises(RuntimeError, match="not installed"):
            init_weave_if_needed(required=True)

    @patch.dict("os.environ", {}, clear=True)
    @patch("app.utils.weave_observability.WEAVE_AVAILABLE", True)
    def test_required_raises_when_api_key_missing(self) -> None:
        from app.utils.weave_observability import init_weave_if_needed

        with patch("app.utils.weave_observability.weave"):
            with patch(
                "shared.secrets.get_env_or_secret", return_value=None
            ):
                with pytest.raises(RuntimeError, match="WANDB_API_KEY"):
                    init_weave_if_needed(required=True)

    @patch.dict("os.environ", {"WANDB_API_KEY": "test-key"}, clear=False)
    @patch("app.utils.weave_observability.WEAVE_AVAILABLE", True)
    def test_required_raises_when_init_fails(self) -> None:
        from app.utils.weave_observability import init_weave_if_needed

        mock_weave = patch("app.utils.weave_observability.weave").start()
        mock_weave.init.side_effect = ConnectionError("network down")

        with pytest.raises(RuntimeError, match="network down"):
            init_weave_if_needed(required=True)
        patch.stopall()


class TestSafeWeaveOp:
    """Tests for safe_weave_op conditional decorator."""

    @patch("app.utils.weave_observability.WEAVE_AVAILABLE", False)
    def test_noop_when_weave_unavailable(self) -> None:
        from app.utils.weave_observability import safe_weave_op

        @safe_weave_op(name="test_op")
        def my_func(x: int) -> int:
            return x + 1

        assert my_func(5) == 6

    @patch("app.utils.weave_observability.WEAVE_AVAILABLE", False)
    def test_noop_preserves_function_name(self) -> None:
        from app.utils.weave_observability import safe_weave_op

        @safe_weave_op()
        def my_func() -> str:
            return "hello"

        assert my_func.__name__ == "my_func"
