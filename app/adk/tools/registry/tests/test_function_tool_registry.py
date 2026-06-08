"""Unit tests for ``function_tool_registry`` (AH-PRD-06 PR-C).

The registry is the bridge between the static catalogue (``tools.yaml``
``function_tools:`` entries) and the actual ``FunctionTool`` callables that
the agent factory passes to each specialist. These tests use stub callables
rather than depending on AH-PRD-04's ``create_visualization`` (which doesn't
exist yet) so the wiring is verifiable today.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.adk.tools.function_tool import FunctionTool

from app.adk.tools.registry.function_tool_registry import (
    clear_function_tool_registry,
    get_function_tool,
    register_function_tool,
    resolve_default_global_tools,
    restore_function_tool_registry,
    snapshot_function_tool_registry,
)


@pytest.fixture(autouse=True)
def _clean_registry_between_tests() -> Generator[None, None, None]:
    """Give each test a clean registry, then restore the prior contents.

    The registry is a process-global singleton; restoring the snapshot on
    teardown (rather than clearing) keeps this suite from stranding an empty
    registry for later suites.
    """
    snapshot = snapshot_function_tool_registry()
    clear_function_tool_registry()
    yield
    restore_function_tool_registry(snapshot)


def _stub_callable() -> str:
    """Trivial function used to exercise the ``FunctionTool(callable)`` path."""
    return "stub"


class TestRegisterFunctionTool:
    def test_wraps_a_bare_callable_in_function_tool(self) -> None:
        register_function_tool("stub", _stub_callable)
        registered = get_function_tool("stub")
        assert isinstance(registered, FunctionTool)

    def test_accepts_a_pre_constructed_function_tool(self) -> None:
        ft = FunctionTool(_stub_callable)
        register_function_tool("stub", ft)
        assert get_function_tool("stub") is ft

    def test_stamps_registered_name_onto_function_tool(self) -> None:
        """The roster filter matches on ``FunctionTool.name`` against
        ``function.{name}`` entries in ``tool_ids``. If the registry let the
        callable's ``__name__`` win, registering ``"create_visualization"``
        with an underlying ``def _create_viz_impl(...)`` would silently
        drop the tool when ``tool_ids`` lists ``function.create_visualization``.
        Asserting the rename explicitly so this contract is locked in."""
        register_function_tool("create_visualization", _stub_callable)
        registered = get_function_tool("create_visualization")
        assert registered.name == "create_visualization"
        # The underlying callable's __name__ is intentionally different —
        # this is the case the rename protects against.
        assert _stub_callable.__name__ == "_stub_callable"

    def test_stamps_name_onto_pre_constructed_function_tool(self) -> None:
        ft = FunctionTool(_stub_callable)
        register_function_tool("create_visualization", ft)
        assert ft.name == "create_visualization"

    def test_underlying_func_name_matches_registered_name(self) -> None:
        """Critical alignment: ADK builds the ``FunctionDeclaration``
        advertised to Gemini from ``self.func.__name__``, while the agent
        dispatches via the tools-dict key ``FunctionTool.name``. If the
        two diverge, every tool call silently misses. This test pins the
        contract that the rename touches both."""
        register_function_tool("create_visualization", _stub_callable)
        registered = get_function_tool("create_visualization")
        assert registered.name == "create_visualization"
        assert registered.func.__name__ == "create_visualization"

    def test_rename_does_not_mutate_original_callable(self) -> None:
        """The rename is a closure, not a mutation of the caller's
        function object. Important when the callable is also used
        elsewhere in the codebase under its original name."""
        original_name = _stub_callable.__name__
        register_function_tool("create_visualization", _stub_callable)
        assert _stub_callable.__name__ == original_name

    def test_function_declaration_advertises_registered_name(self) -> None:
        """End-to-end of the alignment contract: ADK's ``_get_declaration``
        must emit a ``FunctionDeclaration`` whose ``name`` matches the
        registered identity. This is the exact field Gemini receives —
        ensures we wouldn't ship a tool-call mismatch in production."""
        register_function_tool("create_visualization", _stub_callable)
        registered = get_function_tool("create_visualization")
        decl = registered._get_declaration()
        assert decl is not None
        assert decl.name == "create_visualization"

    def test_matching_name_skips_wrapping(self) -> None:
        """Optimization: a callable already named correctly is registered
        as-is (no closure overhead). The registered ``FunctionTool.func``
        is identical to the input."""

        def create_visualization() -> str:
            return "matched"

        register_function_tool("create_visualization", create_visualization)
        registered = get_function_tool("create_visualization")
        assert registered.func is create_visualization

    def test_pre_constructed_function_tool_func_is_renamed(self) -> None:
        """When the caller passes a pre-constructed FunctionTool whose
        ``.func.__name__`` differs from the registered name, the
        registry replaces ``.func`` with the renamed closure so the
        FunctionDeclaration matches the dict key. Without this, Gemini
        would see the original name and dispatch would miss."""
        ft = FunctionTool(_stub_callable)
        assert ft.func.__name__ == "_stub_callable"

        register_function_tool("create_visualization", ft)

        assert ft.name == "create_visualization"
        assert ft.func.__name__ == "create_visualization"
        # The renamed wrapper still delegates to the original callable.
        assert ft.func() == "stub"

    def test_overwriting_logs_at_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Duplicate registration is almost always a real bug in production
        (two modules colliding on a catalogue name), so the overwrite logs
        at WARNING — DEBUG would let it slip past most operators."""
        register_function_tool("stub", _stub_callable)
        first = get_function_tool("stub")
        with caplog.at_level(logging.WARNING):
            register_function_tool("stub", _stub_callable)
        second = get_function_tool("stub")
        assert first is not second
        assert any(
            "is being re-registered" in r.message and r.levelname == "WARNING"
            for r in caplog.records
        )


class TestGetFunctionTool:
    def test_returns_none_for_unknown_name(self) -> None:
        assert get_function_tool("nonexistent") is None


class TestResolveDefaultGlobalTools:
    """``resolve_default_global_tools`` is the resolver hierarchy.py calls."""

    def _registry_with_catalogue(self, names: list[str]) -> MagicMock:
        """Build a fake ToolRegistry whose ``list_default_global_tools``
        returns ToolDefinition stand-ins for the given names.

        ``SimpleNamespace`` rather than ``MagicMock`` for the entries because
        MagicMock's ``name`` kwarg is reserved for the mock's display name
        and can't double as a payload attribute.
        """
        registry = MagicMock()
        registry.list_default_global_tools.return_value = [
            SimpleNamespace(name=n) for n in names
        ]
        return registry

    def test_returns_registered_tools_in_catalogue_order(self) -> None:
        register_function_tool("alpha", _stub_callable)
        register_function_tool("beta", _stub_callable)
        registry = self._registry_with_catalogue(["alpha", "beta"])

        resolved = resolve_default_global_tools(registry)

        assert len(resolved) == 2
        # Catalogue order is preserved — this matters because tool order
        # influences agent prompt construction and we want it deterministic.
        assert resolved[0] is get_function_tool("alpha")
        assert resolved[1] is get_function_tool("beta")

    def test_skips_catalogue_entries_with_no_registered_callable(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        register_function_tool("alpha", _stub_callable)
        registry = self._registry_with_catalogue(
            ["alpha", "missing_callable", "beta_also_missing"]
        )

        with caplog.at_level(logging.WARNING):
            resolved = resolve_default_global_tools(registry)

        assert len(resolved) == 1
        assert resolved[0] is get_function_tool("alpha")
        # One warning per missing entry — operator should see both gaps,
        # not just the first.
        warning_messages = [
            r.message for r in caplog.records if r.levelname == "WARNING"
        ]
        assert any("missing_callable" in m for m in warning_messages)
        assert any("beta_also_missing" in m for m in warning_messages)

    def test_returns_empty_list_when_catalogue_has_no_default_global(self) -> None:
        register_function_tool("registered_but_not_catalogued", _stub_callable)
        registry = self._registry_with_catalogue([])

        resolved = resolve_default_global_tools(registry)

        assert resolved == []

    def test_returns_empty_list_when_catalogue_lists_nothing_registered(self) -> None:
        # Today's production state: catalogue lists ``create_visualization``
        # but AH-PRD-04 hasn't registered the callable yet. The resolver
        # should return [] and the warning surfaces the gap rather than the
        # factory deploying with no tools and no signal.
        registry = self._registry_with_catalogue(["create_visualization"])

        resolved = resolve_default_global_tools(registry)

        assert resolved == []


class TestClearFunctionToolRegistry:
    def test_clears_all_registrations(self) -> None:
        register_function_tool("alpha", _stub_callable)
        register_function_tool("beta", _stub_callable)

        clear_function_tool_registry()

        assert get_function_tool("alpha") is None
        assert get_function_tool("beta") is None
