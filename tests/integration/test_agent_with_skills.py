"""Integration test — agent build → skill load → spans emitted (@pytest.mark.llm).

SK-30: Verifies that a factory-built agent with ``SkillToolset`` attached emits
the three expected Weave spans (``skill.list``, ``skill.load``,
``skill.load_resource``) with correct attributes when driven by a deterministic
fake LLM.

Run with::

    uv run pytest tests/integration/test_agent_with_skills.py -m llm -v

Gated by ``@pytest.mark.llm`` so it is excluded from the default CI suite
(which has no live Gemini endpoint).

Design notes
------------
* ``_FakeSkillLlm`` (pattern ``^fake-skill-.*``) is a ``BaseLlm`` subclass
  registered with ``LLMRegistry``.  It drains a module-level FIFO queue so
  tests control the full LLM response sequence.
* ``_FakeWeaveClient`` subclasses ``WeaveClient`` but skips ``__init__`` so no
  trace server is needed.  Its ``create_call`` creates real ``weave.trace.weave_client.Call``
  dataclass objects; ``finish_call`` resolves via MRO to ``WeaveClient.finish_call``,
  which ``TraceCapture`` intercepts at the class level.
* ``WeaveClient.finish_call`` is stubbed with a no-op via ``monkeypatch`` *before*
  ``TraceCapture.__enter__``, so ``TraceCapture._original_finish`` is the stub
  and never attempts to reach the Weave backend.
* The ``kene_api.services.skill_loader`` module is injected into ``sys.modules``
  via ``monkeypatch.setitem``; no real ``kene_api`` package is needed.
"""

from __future__ import annotations

import asyncio
import sys
import types
import uuid
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import MagicMock

import pytest

# ── neo4j mock — must precede any app imports ─────────────────────────────────
_neo4j_mock = MagicMock()
_neo4j_mock.exceptions = MagicMock()
_neo4j_mock.exceptions.ServiceUnavailable = Exception
_neo4j_mock.exceptions.SessionExpired = Exception
sys.modules.setdefault("neo4j", _neo4j_mock)
sys.modules.setdefault("neo4j.exceptions", _neo4j_mock.exceptions)

# ── Imports ────────────────────────────────────────────────────────────────────
from google.adk.models.base_llm import BaseLlm  # noqa: E402
from google.adk.models.llm_response import LlmResponse  # noqa: E402
from google.adk.models.registry import LLMRegistry  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types as genai_types  # noqa: E402
from weave.trace.weave_client import Call, WeaveClient  # noqa: E402

import app.adk.tracking.skill_spans as _skill_spans_module  # noqa: E402
from app.adk.agents.agent_factory.builder import build_agent  # noqa: E402
from app.adk.agents.agent_factory.config_loader import MergedAgentConfig  # noqa: E402
from tests.integration.stability.weave_trace_capture import TraceCapture  # noqa: E402

# ── FakeLlm ────────────────────────────────────────────────────────────────────

_skill_response_queue: list[LlmResponse] = []


class _FakeSkillLlm(BaseLlm):
    """Drains ``_skill_response_queue`` FIFO; pattern ``^fake-skill-.*``.

    Registered at module level so the pattern is available for the entire
    test session.  Disjoint from ``^fake-it-.*`` (review-loop tests) and
    ``^fake-behavioral-.*`` (unit tests) to prevent cross-contamination when
    multiple suites run in the same process.
    """

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"^fake-skill-.*"]

    async def generate_content_async(
        self, llm_request: object, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        if _skill_response_queue:
            yield _skill_response_queue.pop(0)
        else:
            yield LlmResponse(
                content=genai_types.Content(
                    role="model",
                    parts=[genai_types.Part(text="(no response queued)")],
                )
            )


LLMRegistry.register(_FakeSkillLlm)

# ── Response helpers ────────────────────────────────────────────────────────────


def _func_call(name: str, args: dict[str, Any]) -> LlmResponse:
    return LlmResponse(
        content=genai_types.Content(
            role="model",
            parts=[
                genai_types.Part(
                    function_call=genai_types.FunctionCall(name=name, args=args)
                )
            ],
        )
    )


def _text_response(text: str) -> LlmResponse:
    return LlmResponse(
        content=genai_types.Content(
            role="model",
            parts=[genai_types.Part(text=text)],
        )
    )


# ── Fixtures ────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_skill_queue() -> None:
    _skill_response_queue.clear()
    yield
    _skill_response_queue.clear()


# ── FakeWeaveClient ─────────────────────────────────────────────────────────────


class _FakeWeaveClient(WeaveClient):
    """Minimal WeaveClient subclass for test span capture.

    Skips ``WeaveClient.__init__`` so no trace-server connection is attempted.
    ``create_call`` returns real ``Call`` dataclass objects so ``TraceCapture``
    can read ``call.attributes``, ``call.op_name``, etc.  ``finish_call``
    inherits from ``WeaveClient`` — when ``TraceCapture`` is active it patches
    ``WeaveClient.finish_call`` at the class level, so calls through any
    instance's MRO are intercepted.
    """

    def __init__(self) -> None:
        # Intentionally skips WeaveClient.__init__() — no trace-server
        # connection wanted in tests.  Only _anonymous_ops is needed so
        # create_call can be called without AttributeError.
        self._anonymous_ops: dict[str, Any] = {}

    def create_call(
        self,
        op: str | object,
        inputs: dict[str, Any],
        parent: object = None,
        attributes: dict[str, Any] | None = None,
        display_name: object = None,
        *,
        use_stack: bool = True,
    ) -> Call:
        return Call(
            _op_name=op if isinstance(op, str) else str(op),
            trace_id="test-trace-skills-001",
            project_id="test-project",
            parent_id=None,
            inputs=inputs or {},
            id=str(uuid.uuid4()),
            attributes=dict(attributes) if attributes else {},
        )


# ── Fake loader module factory ──────────────────────────────────────────────────


def _make_fake_loader_module(
    skills_by_id: dict[str, Any],
) -> types.ModuleType:
    """Create a ``kene_api.services.skill_loader`` stand-in for injection into sys.modules."""

    class _SkillNotFoundError(Exception):
        pass

    class _SkillCorruptError(Exception):
        pass

    async def load_skill(account_id: str, skill_id: str, **kwargs: Any) -> Any:
        if skill_id in skills_by_id:
            return skills_by_id[skill_id]
        raise _SkillNotFoundError(
            f"Skill {skill_id!r} not found (account={account_id!r})"
        )

    mod = types.ModuleType("kene_api.services.skill_loader")
    mod.load_skill = load_skill  # type: ignore[attr-defined]
    mod.SkillNotFoundError = _SkillNotFoundError  # type: ignore[attr-defined]
    mod.SkillCorruptError = _SkillCorruptError  # type: ignore[attr-defined]
    return mod


# ── Async runner helper ─────────────────────────────────────────────────────────


async def _run_agent_turn(agent: Any, query: str) -> None:
    """Drive one agent turn with ``account_id`` seeded in session state."""
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="test-skills-app",
        user_id="test-user",
        session_id="test-session",
        state={"account_id": "acc_test_skills"},
    )
    runner = Runner(
        agent=agent,
        app_name="test-skills-app",
        session_service=session_service,
    )
    async for _ in runner.run_async(
        user_id="test-user",
        session_id="test-session",
        new_message=genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=query)],
        ),
    ):
        pass


# ── Tests ───────────────────────────────────────────────────────────────────────


@pytest.mark.llm
def test_agent_skill_tool_calls_emit_spans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Build agent with SkillToolset; drive list/load/load_resource; assert spans.

    AC-7 (SK-30): Verifies that ``skill_spans_before_tool_callback`` /
    ``skill_spans_after_tool_callback`` emit ``skill.list``, ``skill.load``,
    and ``skill.load_resource`` Weave spans with the correct attributes
    (``account_id``, ``skill_id``, ``skill_name`` / ``rel_path``,
    ``skill_owner_type``) when the factory-built agent processes the three
    SkillToolset tool calls.
    """
    from google.adk.skills import models as adk_skill_models

    # ── 1. Build a fake seo-checklist ADK Skill with a reference resource ──
    seo_skill = adk_skill_models.Skill(
        frontmatter=adk_skill_models.Frontmatter(
            name="seo-checklist",
            description="SEO optimization checklist skill.",
        ),
        instructions="# SEO Checklist\nOptimize content for search engines.",
        resources=adk_skill_models.Resources(
            references={
                # LoadSkillResourceTool strips "references/" from the path,
                # so the key here is the filename only.
                "style-guide.md": "# SEO Style Guide\nKey rules for SEO content."
            }
        ),
    )

    # ── 2. Inject fake kene_api.services.skill_loader into sys.modules ───────
    # All three entries use monkeypatch.setitem so teardown is symmetric —
    # monkeypatch restores the previous value (or removes the key if it was
    # absent) after the test, preventing permanent sys.modules pollution.
    loader_mod = _make_fake_loader_module({"seo-checklist-id": seo_skill})
    monkeypatch.setitem(
        sys.modules,
        "kene_api",
        sys.modules.get("kene_api", types.ModuleType("kene_api")),
    )
    monkeypatch.setitem(
        sys.modules,
        "kene_api.services",
        sys.modules.get("kene_api.services", types.ModuleType("kene_api.services")),
    )
    monkeypatch.setitem(sys.modules, "kene_api.services.skill_loader", loader_mod)

    # ── 3. Build the agent via the factory ───────────────────────────────────
    config = MergedAgentConfig(
        instruction="Use skill tools to answer questions about SEO.",
        model="fake-skill-driver",
        skill_ids=["seo-checklist-id"],
    )
    agent = build_agent(
        config,
        name="test_skills_agent",
        account_id="acc_test_skills",
    )

    # ── 4. Stub WeaveClient.finish_call with a no-op BEFORE TraceCapture ─────
    # TraceCapture saves whatever WeaveClient.finish_call currently is as its
    # _original_finish. Stubbing here means the stub — not the real backend
    # implementation — is stored, so the patched wrapper never attempts to
    # reach the Weave trace server.
    monkeypatch.setattr(
        WeaveClient,
        "finish_call",
        lambda self, call, output=None, exception=None, *, op=None: None,
    )

    # ── 5. Patch skill_spans._weave_get_client to return our fake client ──────
    # skill_spans.py uses its own module-level _weave_get_client binding (not
    # the one in callbacks.py), so patching here is targeted and safe.
    fake_client = _FakeWeaveClient()
    monkeypatch.setattr(_skill_spans_module, "_weave_get_client", lambda: fake_client)

    # ── 6. Queue the LLM response sequence ───────────────────────────────────
    _skill_response_queue.extend(
        [
            _func_call("list_skills", {}),
            _func_call("load_skill", {"name": "seo-checklist"}),
            _func_call(
                "load_skill_resource",
                {"skill_name": "seo-checklist", "path": "references/style-guide.md"},
            ),
            _text_response("I have reviewed the SEO checklist and style guide."),
        ]
    )

    # ── 7. Drive one agent turn inside TraceCapture ───────────────────────────
    with TraceCapture() as cap:
        asyncio.run(
            _run_agent_turn(agent, "Show me the SEO checklist and style guide.")
        )

    # ── 8. Assert the three skill spans were emitted ──────────────────────────
    traces = cap.traces
    op_names = [t.get("_weave_op_name") for t in traces]

    assert "skill.list" in op_names, f"skill.list span missing; captured: {op_names}"
    assert "skill.load" in op_names, f"skill.load span missing; captured: {op_names}"
    assert "skill.load_resource" in op_names, (
        f"skill.load_resource span missing; captured: {op_names}"
    )

    # ── skill.list ────────────────────────────────────────────────────────────
    list_span = next(t for t in traces if t.get("_weave_op_name") == "skill.list")
    assert list_span["account_id"] == "acc_test_skills"
    assert list_span["skill_count"] == 1
    assert list_span["skill_ids"] == ["seo-checklist-id"]
    assert list_span["skill_owner_type"] == "account"

    # ── skill.load ────────────────────────────────────────────────────────────
    load_span = next(t for t in traces if t.get("_weave_op_name") == "skill.load")
    assert load_span["account_id"] == "acc_test_skills"
    assert load_span["skill_id"] == "seo-checklist-id"
    assert load_span["skill_name"] == "seo-checklist"
    # skill_version is always 0 in v1 — a placeholder until SK-29/SK-PRD-05
    # plumbs the resolved version from the loader API.
    assert load_span["skill_version"] == 0
    assert load_span["skill_owner_type"] == "account"

    # ── skill.load_resource ───────────────────────────────────────────────────
    resource_span = next(
        t for t in traces if t.get("_weave_op_name") == "skill.load_resource"
    )
    assert resource_span["account_id"] == "acc_test_skills"
    assert resource_span["skill_id"] == "seo-checklist-id"
    assert resource_span["rel_path"] == "references/style-guide.md"
    assert resource_span["skill_owner_type"] == "account"
