"""Test helper: RecordingWeaveClient and recording_weave_client() context manager.

Intercepts Weave's create_call / finish_call API calls and reconstructs a
parent/child span tree so integration tests can assert the full span hierarchy
without a live W&B SaaS connection.

Usage::

    from app.adk.tracking.tests._weave_recording import recording_weave_client

    with recording_weave_client() as client:
        some_function_that_emits_weave_spans()
        tree = client.tree_root()
        assert tree["name"] == "my_root_op"
        assert len(tree["children"]) == 2

When the ``weave`` package is not importable, ``recording_weave_client()`` is a
no-op context manager that yields ``None``.
"""

from __future__ import annotations

import contextlib
from collections.abc import Generator
from typing import Any

try:
    import weave as _weave_module

    _WEAVE_AVAILABLE = True
except ImportError:
    _weave_module = None  # type: ignore[assignment]
    _WEAVE_AVAILABLE = False


# ---------------------------------------------------------------------------
# Internal call record
# ---------------------------------------------------------------------------


class _RecordedCall:
    """Represents a single intercepted Weave span."""

    def __init__(
        self,
        name: str,
        summary: dict[str, Any] | None,
        attributes: dict[str, Any] | None,
        inputs: dict[str, Any] | None,
    ) -> None:
        self.name: str = name
        self.summary: dict[str, Any] = summary if summary is not None else {}
        self.attributes: dict[str, Any] = attributes if attributes is not None else {}
        self.inputs: dict[str, Any] = inputs if inputs is not None else {}
        self.output: Any = None
        self.children: list[_RecordedCall] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "summary": self.summary,
            "attributes": self.attributes,
            "inputs": self.inputs,
            "output": self.output,
            "children": [c.to_dict() for c in self.children],
        }


# ---------------------------------------------------------------------------
# RecordingWeaveClient
# ---------------------------------------------------------------------------


class RecordingWeaveClient:
    """A fake Weave client that records create_call / finish_call pairs and
    reconstructs the parent/child call tree.

    Call ``create_call`` / ``finish_call`` explicitly in tests (or let the
    context manager intercept Weave's global ``get_current_call``).

    The ``tree_root()`` method returns the top-level span as a plain dict once
    all calls have been finished.
    """

    def __init__(self) -> None:
        self._stack: list[_RecordedCall] = []
        self._roots: list[_RecordedCall] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_call(
        self,
        op: str,
        inputs: dict[str, Any] | None = None,
        attributes: dict[str, Any] | None = None,
        use_stack: bool | None = None,
        **kwargs: Any,
    ) -> _RecordedCall:
        """Record the start of a span.

        Args:
            op: Operation / span name.
            inputs: Optional inputs dict attached to the span.
            attributes: Optional attributes dict attached to the span.
            use_stack: Ignored; accepted for API compatibility.
            **kwargs: Any extra keyword arguments are silently ignored.

        Returns:
            The ``_RecordedCall`` object representing the new span.
        """
        recorded = _RecordedCall(
            name=op,
            summary=None,
            attributes=attributes,
            inputs=inputs,
        )
        if self._stack:
            self._stack[-1].children.append(recorded)
        else:
            self._roots.append(recorded)
        self._stack.append(recorded)
        return recorded

    def finish_call(
        self,
        call: _RecordedCall,
        output: Any = None,
        **kwargs: Any,
    ) -> None:
        """Record the end of a span.

        Args:
            call: The ``_RecordedCall`` returned by the matching ``create_call``.
            output: Optional output value attached to the span.
            **kwargs: Any extra keyword arguments are silently ignored.

        Raises:
            AssertionError: If the stack is empty or the top of the stack does
                not match ``call`` (unbalanced calls).
        """
        assert self._stack, (
            "finish_call called with an empty stack — more finish_call() calls "
            "than create_call() calls."
        )
        top = self._stack[-1]
        assert top is call, (
            f"finish_call call mismatch: expected '{top.name}' at top of stack, "
            f"got '{call.name}'."
        )
        top.output = output
        self._stack.pop()

    def current_call(self) -> _RecordedCall | None:
        """Return the active (most-recently-created, not-yet-finished) call or None."""
        return self._stack[-1] if self._stack else None

    def tree_root(self) -> dict[str, Any] | None:
        """Return the root span as a plain dict, or None if no calls were made.

        Raises:
            AssertionError: If there are unfinished calls (stack non-empty).
        """
        if not self._roots and not self._stack:
            return None
        assert not self._stack, (
            f"tree_root() called with {len(self._stack)} unfinished call(s): "
            + ", ".join(c.name for c in self._stack)
        )
        return self._roots[0].to_dict()


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def recording_weave_client() -> Generator[RecordingWeaveClient | None, None, None]:
    """Context manager that patches ``weave.get_current_call`` and yields a
    ``RecordingWeaveClient``.

    The patch makes calls to ``weave.get_current_call()`` return the currently
    active ``_RecordedCall`` from the client's stack.  Test code (or production
    code under test) can call ``client.create_call`` / ``client.finish_call``
    explicitly; ``review_pipeline_tracing.py`` helpers that call
    ``weave.get_current_call()`` will receive the correct in-flight call object.

    When ``weave`` is not importable, yields ``None`` without patching anything.

    Yields:
        ``RecordingWeaveClient`` instance, or ``None`` if Weave is unavailable.
    """
    if not _WEAVE_AVAILABLE or _weave_module is None:
        yield None
        return

    client: RecordingWeaveClient = RecordingWeaveClient()

    from unittest.mock import patch

    with patch(
        "weave.get_current_call",
        side_effect=lambda: client.current_call(),
    ):
        yield client
