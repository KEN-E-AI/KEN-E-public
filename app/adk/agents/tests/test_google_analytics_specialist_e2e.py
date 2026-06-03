"""End-to-end tests for the Google Analytics Specialist (AH-PRD-03).

AH-27 — code execution verification (AC #6):
    Builds a ``LlmAgent`` from the GA specialist config with
    ``code_executor=BuiltInCodeExecutor()`` and verifies that numerical queries
    produce ``executable_code`` + ``code_execution_result(OUTCOME_OK)`` parts in
    the ADK event stream. Bypasses Firestore/MCP to isolate code-execution
    behaviour.

AH-28 — OAuth error handling (AC #9):
    Exercises ``ga_oauth_after_tool_callback`` directly to assert that a 401
    response from GA MCP sets ``_requires_reauth=True`` and
    ``_reauth_service="google-analytics"`` in session state and returns a
    user-visible error message. Does not require a live model.

AH-29 — Multi-tenant OAuth isolation (AC #10):
    Two concurrent sessions with different ``ga_credentials`` each use their
    own OAuth tokens via ``_make_header_provider("ga_oauth")``. Verifies
    ``McpToolsetPool`` keys on ``(kind, server_id, account_id,
    sha256(mcp_creds))`` and that no cross-session header bleed occurs.

Marking convention:
    Tests that require a live Gemini model are marked ``@pytest.mark.llm``
    so CI can opt-in without breaking the default fast suite. AH-28 and
    AH-29 tests do NOT require a live model call.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections.abc import AsyncIterator
from contextlib import ExitStack
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from google.adk.agents import LlmAgent
from google.adk.code_executors import BuiltInCodeExecutor
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.function_tool import FunctionTool
from google.genai import types as genai_types
from google.genai.errors import ClientError
from google.genai.types import Content, FunctionCall, Outcome, Part

from app.adk.agents.agent_factory import specialist_runtime as sr
from app.adk.agents.agent_factory import sub_agent_attacher as attacher
from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
from app.adk.agents.agent_factory.header_provider import _make_header_provider
from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool
from app.adk.security.hooks import ga_oauth_after_tool_callback

_GEMINI_CREDS_AVAILABLE = bool(
    os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_CLOUD_PROJECT")
)

# ---------------------------------------------------------------------------
# Stub LLMs (AH-29)
# ---------------------------------------------------------------------------


class _TransferToGaSpecialistStubLlm(BaseLlm):
    """Root LLM that emits transfer_to_agent(agent_name='google_analytics_specialist')."""

    model: str = "transfer_to_ga_specialist_stub"

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["transfer_to_ga_specialist_stub"]

    async def generate_content_async(  # type: ignore[override]
        self,
        llm_request: Any,
        stream: bool = False,
    ) -> AsyncIterator[LlmResponse]:
        func_call = FunctionCall(
            name="transfer_to_agent",
            args={"agent_name": "google_analytics_specialist"},
        )
        content = Content(role="model", parts=[Part(function_call=func_call)])
        yield LlmResponse(content=content, turn_complete=False)


class _GaSpecialistStubLlm(BaseLlm):
    """Specialist LLM that emits a single deterministic text response."""

    model: str = "ga_specialist_stub"

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["ga_specialist_stub"]

    async def generate_content_async(  # type: ignore[override]
        self,
        llm_request: Any,
        stream: bool = False,
    ) -> AsyncIterator[LlmResponse]:
        content = Content(
            role="model", parts=[Part.from_text(text="GA specialist response")]
        )
        yield LlmResponse(content=content, turn_complete=True)


# ---------------------------------------------------------------------------
# GA specialist instruction + stub tools (AH-27)
# ---------------------------------------------------------------------------

_GA_TEST_INSTRUCTION = """You are a Google Analytics specialist.

Use Gemini code execution for ALL numerical analysis — percentage changes, trend
calculations, averages, and any arithmetic. Never compute numbers in-context.

When numerical data is provided in the question, write and execute Python code
to compute the result, then present the answer.

Available tools:
- get_account_summaries_mt - list GA accounts (no required params)
- run_report_mt - run analytics reports (params: property_id, date_ranges, metrics)
"""


def get_account_summaries_mt() -> str:
    """List all Google Analytics accounts and properties."""
    return '{"accounts": [{"displayName": "Test Account", "propertySummaries": [{"property": "properties/123456789", "displayName": "Test Property"}]}]}'


def run_report_mt(
    property_id: str,
    date_ranges: list,
    metrics: list | None = None,
    dimensions: list | None = None,
) -> str:
    """Run a GA analytics report."""
    return '{"rows": [{"metricValues": [{"value": "4823"}]}, {"metricValues": [{"value": "5391"}]}]}'


_NUMERICAL_QUERIES = [
    (
        "percentage",
        "Property 123456789: sessions were 4823 last week and 5391 this week. "
        "What is the percentage change week-over-week?",
    ),
    (
        "trend",
        "Property 123456789: daily sessions for the last 7 days are "
        "[421, 489, 510, 478, 502, 521, 548]. What is the week-over-week trend?",
    ),
    (
        "average",
        "Property 123456789: bounce rates for the past 7 days are "
        "[0.42, 0.38, 0.45, 0.41, 0.39, 0.40, 0.43]. What is the average bounce rate?",
    ),
]

# ---------------------------------------------------------------------------
# Shared helpers (AH-29)
# ---------------------------------------------------------------------------


def _make_ga_specialist_agent() -> LlmAgent:
    """Return an LlmAgent named 'google_analytics_specialist' backed by the stub LLM."""
    return LlmAgent(
        name="google_analytics_specialist",
        model=_GaSpecialistStubLlm(),
        instruction="Google Analytics specialist",
        disallow_transfer_to_parent=True,
    )


def _make_ga_config() -> MergedAgentConfig:
    """Return a MergedAgentConfig for the GA specialist (pure-mock variant)."""
    return MergedAgentConfig(
        instruction="You are a Google Analytics specialist.",
        model="ga_specialist_stub",
        description="Google Analytics specialist",
        mcp_servers=["google_analytics_mcp"],
        ken_e_sub_agent=True,
    )


def _compute_creds_hash(mcp_creds: dict[str, Any]) -> str:
    """Reproduce the creds_hash logic from specialist_runtime._build_specialist."""
    return hashlib.sha256(
        json.dumps(mcp_creds, sort_keys=True, default=str).encode()
    ).hexdigest()


async def _run_ga_specialist_for_session(
    *,
    account_id: str,
    ga_credentials: dict[str, Any],
    mcp_creds: dict[str, Any],
    specialist_agent: LlmAgent,
) -> list[Any]:
    """Spin up a Runner for one session and return all events."""
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    root = LlmAgent(
        name="root_agent",
        model=_TransferToGaSpecialistStubLlm(),
        instruction="Route queries.",
        tools=[],
        before_agent_callback=[attacher.attach_specialists_before_agent_callback],
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=f"mt_isolation_test_{account_id}",
        user_id=f"user_{account_id}",
        state={
            "account_id": account_id,
            "ga_credentials": ga_credentials,
            "mcp_creds_google_analytics_mcp": mcp_creds,
        },
    )
    runner = Runner(
        agent=root,
        app_name=f"mt_isolation_test_{account_id}",
        session_service=session_service,
    )

    events: list[Any] = []
    ga_config = _make_ga_config()
    with (
        patch.object(
            attacher,
            "list_account_agent_configs_cached",
            return_value=["google_analytics_specialist"],
        ),
        patch.object(attacher, "resolve_config", return_value=ga_config),
        patch.object(attacher, "resolve_agent", return_value=specialist_agent),
    ):
        async for event in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=genai_types.Content(
                role="user",
                parts=[Part.from_text(text="Show me GA data")],
            ),
        ):
            events.append(event)

    return events


# ---------------------------------------------------------------------------
# Shared test infrastructure (AH-28)
# ---------------------------------------------------------------------------


@dataclass
class _MockState:
    """Dict-like mock of ADK session state."""

    _data: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data


@dataclass
class _MockToolContext:
    """Minimal mock of ADK ToolContext."""

    state: _MockState = field(default_factory=_MockState)


def _make_tool(name: str = "list_ga_accounts") -> MagicMock:
    t = MagicMock()
    t.name = name
    return t


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_caches() -> Any:
    """Reset specialist/config/fingerprint caches before and after every test."""
    from app.adk.agents.utils.config_cache import clear_config_cache

    sr._specialists_cache.clear()
    sr._clear_block_cache_for_tests()
    sr._clear_list_cache_for_tests()
    attacher._reset_applied_state_for_tests()
    clear_config_cache()
    yield
    sr._specialists_cache.clear()
    sr._clear_block_cache_for_tests()
    sr._clear_list_cache_for_tests()
    attacher._reset_applied_state_for_tests()
    clear_config_cache()


# ---------------------------------------------------------------------------
# AH-27: code execution E2E tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("query_name,query_text", _NUMERICAL_QUERIES)
@pytest.mark.parametrize("trial", [1, 2, 3])
@pytest.mark.llm
@pytest.mark.skipif(
    not _GEMINI_CREDS_AVAILABLE,
    reason=(
        "Live Gemini credentials not configured — set GOOGLE_API_KEY "
        "or GOOGLE_CLOUD_PROJECT"
    ),
)
@pytest.mark.asyncio
async def test_ga_numerical_query_uses_code_execution(
    trial: int, query_name: str, query_text: str
) -> None:
    """AC #6 (AH-PRD-03 §7): numerical queries must produce executable_code +
    code_execution_result(OUTCOME_OK) parts in the ADK event stream.
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    agent = LlmAgent(
        name="google_analytics_specialist",
        model="gemini-2.0-flash",
        instruction=_GA_TEST_INSTRUCTION,
        code_executor=BuiltInCodeExecutor(),
        tools=[FunctionTool(get_account_summaries_mt), FunctionTool(run_report_mt)],
        disallow_transfer_to_parent=True,
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="ga_specialist_e2e", user_id="test_user"
    )
    runner = Runner(
        agent=agent,
        app_name="ga_specialist_e2e",
        session_service=session_service,
    )

    all_parts: list[Part] = []
    try:
        async for event in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text=query_text)],
            ),
        ):
            if event.content and event.content.parts:
                all_parts.extend(event.content.parts)
    except ClientError as exc:
        if exc.code == 403:
            pytest.skip(
                f"Gemini credentials lack required permission (HTTP 403). "
                f"To run this test grant `roles/aiplatform.user` to the "
                f"service account, or set GOOGLE_API_KEY for the Google AI "
                f"API path. Original error: {exc!s:.160}"
            )
        if exc.code == 404:
            pytest.skip(
                f"Model {agent.model!r} is not available in this Vertex "
                f"project/region (HTTP 404). gemini-2.0-flash is absent on some "
                f"projects (e.g. ken-e-dev/us-central1); run where it is enabled "
                f"or update the pinned model. Original error: {exc!s:.160}"
            )
        raise

    has_exec_code = any(
        p.executable_code and p.executable_code.code for p in all_parts
    )
    has_exec_result = any(
        p.code_execution_result
        and p.code_execution_result.outcome == Outcome.OUTCOME_OK
        for p in all_parts
    )

    assert has_exec_code, (
        f"[{query_name} trial {trial}] No executable_code part in response. "
        f"Parts collected: {[type(p).__name__ for p in all_parts]}"
    )
    assert has_exec_result, (
        f"[{query_name} trial {trial}] No OUTCOME_OK code_execution_result in response. "
        f"Parts collected: {[type(p).__name__ for p in all_parts]}"
    )


# ---------------------------------------------------------------------------
# AH-28: GA OAuth 401 → _requires_reauth integration tests
# ---------------------------------------------------------------------------


class TestGaOauth401ErrorHandling:
    """Integration tests for the OAuth-expiry error-handling path (AH-28).

    These tests do NOT require a live model — they exercise
    ``ga_oauth_after_tool_callback`` directly to reproduce the full session-
    state mutation that PRD §7 AC #9 requires.
    """

    @pytest.mark.asyncio
    async def test_401_response_sets_requires_reauth_flag(self) -> None:
        """AC #9 (part 1): _requires_reauth is True in session state after 401."""
        ctx = _MockToolContext()
        tool = _make_tool()
        mcp_401_response = {"error": True, "message": "401 Unauthorized from GA MCP"}

        await ga_oauth_after_tool_callback(tool, {}, ctx, mcp_401_response)

        assert ctx.state["_requires_reauth"] is True

    @pytest.mark.asyncio
    async def test_401_response_sets_reauth_service(self) -> None:
        """_reauth_service is set to 'google-analytics' after 401."""
        ctx = _MockToolContext()
        tool = _make_tool()
        mcp_401_response = {"error": True, "message": "token expired"}

        await ga_oauth_after_tool_callback(tool, {}, ctx, mcp_401_response)

        assert ctx.state["_reauth_service"] == "google-analytics"

    @pytest.mark.asyncio
    async def test_401_response_returns_user_visible_message(self) -> None:
        """AC #9 (part 2): response contains a clear, user-visible message."""
        ctx = _MockToolContext()
        tool = _make_tool()
        mcp_401_response = {"error": True, "message": "invalid_grant"}

        result = await ga_oauth_after_tool_callback(tool, {}, ctx, mcp_401_response)

        assert result is not None, "Callback must return a non-None replacement dict"
        assert "Please reconnect Google Analytics" in result["message"]

    @pytest.mark.asyncio
    async def test_401_message_contains_no_token_internals(self) -> None:
        """AC #9: error message must not leak token bytes or stack traces."""
        ctx = _MockToolContext()
        tool = _make_tool()
        mcp_401_response = {
            "error": True,
            "message": "token has been revoked",
            "_raw_token": "ya29.secret_access_token_bytes",
        }

        result = await ga_oauth_after_tool_callback(tool, {}, ctx, mcp_401_response)

        assert result is not None
        assert "ya29" not in result["message"]
        assert "secret_access_token_bytes" not in result["message"]
        assert "Traceback" not in result["message"]

    @pytest.mark.asyncio
    async def test_specialist_does_not_silent_retry_on_401(self) -> None:
        """AC: callback returns non-None to prevent silent retry."""
        ctx = _MockToolContext()
        tool = _make_tool()
        mcp_401_response = {"error": True, "message": "401 Unauthorized"}

        result = await ga_oauth_after_tool_callback(tool, {}, ctx, mcp_401_response)

        assert result is not None
        assert result["error"] == "authentication_required"

    @pytest.mark.asyncio
    async def test_token_expiry_variants_all_trigger_reauth(self) -> None:
        """Multiple real-world 401 response shapes from GA MCP all set _requires_reauth."""
        real_world_responses = [
            {"error": True, "message": "Request had invalid authentication credentials. "
             "Expected OAuth 2 access token, login cookie or other valid authentication "
             "credential. See https://developers.google.com/identity/sign-in/web/devconsole-project. "
             "401"},
            {"isError": True, "message": "invalid_grant: Token has been expired or revoked."},
            {"_error": "HTTPStatusError: 401 Unauthorized"},
            "token has been revoked by the user",
        ]

        for response in real_world_responses:
            ctx = _MockToolContext()
            result = await ga_oauth_after_tool_callback(_make_tool(), {}, ctx, response)
            assert ctx.state.get("_requires_reauth") is True, (
                f"Expected _requires_reauth=True for response: {response!r}"
            )
            assert result is not None, f"Expected non-None result for response: {response!r}"

    @pytest.mark.asyncio
    async def test_successful_ga_response_does_not_set_reauth(self) -> None:
        """A successful GA MCP response must not trigger reauth."""
        ctx = _MockToolContext()
        tool = _make_tool()
        success_response = {
            "rows": [{"dimensions": ["2024-01-01"], "metrics": [{"values": ["1000"]}]}],
            "totals": [{"values": ["7000"]}],
        }

        result = await ga_oauth_after_tool_callback(tool, {}, ctx, success_response)

        assert result is None
        assert "_requires_reauth" not in ctx.state._data

    @pytest.mark.asyncio
    async def test_permission_denied_does_not_set_reauth(self) -> None:
        """Non-401 errors (e.g. permission_denied) must not set _requires_reauth."""
        ctx = _MockToolContext()
        tool = _make_tool()
        permission_denied = {"error": "permission_denied", "message": "User lacks access"}

        result = await ga_oauth_after_tool_callback(tool, {}, ctx, permission_denied)

        assert result is None
        assert "_requires_reauth" not in ctx.state._data


# ---------------------------------------------------------------------------
# AH-29 — Multi-tenant OAuth isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_google_analytics_specialist_multi_tenant_isolation() -> None:
    """AC #10 (AH-PRD-03 §7): two concurrent sessions with different ``ga_credentials``
    each use their own OAuth tokens; ``McpToolsetPool`` returns distinct entries
    keyed on ``(server_id, account_id, sha256(mcp_creds))``; no cross-session
    header bleed.
    """
    ACCOUNT_A = "acct_a_tenant_isolation"
    ACCOUNT_B = "acct_b_tenant_isolation"

    GA_CREDS_A: dict[str, Any] = {"access_token": "tok_A", "tenant_id": "tenant_A"}
    GA_CREDS_B: dict[str, Any] = {"access_token": "tok_B", "tenant_id": "tenant_B"}

    MCP_CREDS_A: dict[str, Any] = {"refresh_signature": "sig_A"}
    MCP_CREDS_B: dict[str, Any] = {"refresh_signature": "sig_B"}

    # --- Assertion 1: closure isolation ------------------------------------
    provider = _make_header_provider("ga_oauth")

    ctx_a: MagicMock = MagicMock()
    ctx_a.state = {"ga_credentials": GA_CREDS_A}

    ctx_b: MagicMock = MagicMock()
    ctx_b.state = {"ga_credentials": GA_CREDS_B}

    headers_a = provider(ctx_a)
    headers_b = provider(ctx_b)

    assert headers_a.get("Authorization") == "Bearer tok_A", (
        f"Session A header provider must return tok_A; got {headers_a}"
    )
    assert headers_a.get("X-Tenant-ID") == "tenant_A", (
        f"Session A header provider must return tenant_A; got {headers_a}"
    )
    assert headers_b.get("Authorization") == "Bearer tok_B", (
        f"Session B header provider must return tok_B; got {headers_b}"
    )
    assert headers_b.get("X-Tenant-ID") == "tenant_B", (
        f"Session B header provider must return tenant_B; got {headers_b}"
    )
    assert headers_a != headers_b
    assert "tok_B" not in headers_a.values()
    assert "tok_A" not in headers_b.values()

    # --- Assertion 2 & 3: pool isolation via _build_specialist -------------
    shared_pool = McpToolsetPool()
    toolset_calls: list[str] = []

    def _tracking_build_toolset(server_id: str, _doc: Any, **_kw: Any) -> MagicMock:
        toolset_calls.append(server_id)
        return MagicMock(name=f"toolset_{server_id}_{len(toolset_calls)}")

    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "app.adk.agents.agent_factory.specialist_runtime._DEFAULT_MCP_POOL",
                new=shared_pool,
            )
        )
        from app.adk.agents.agent_factory.tests.test_specialist_runtime import (
            _FakeFirestoreDb,
        )

        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "google_analytics_mcp"): {"enabled": True}}
        )
        stack.enter_context(
            patch(
                "app.adk.agents.agent_factory.mcp._build_firestore_client",
                return_value=fake_db,
            )
        )
        stack.enter_context(
            patch(
                "app.adk.agents.agent_factory.mcp.build_toolset_for_doc",
                side_effect=_tracking_build_toolset,
            )
        )
        stack.enter_context(
            patch(
                "app.adk.tools.registry.function_tool_registry.resolve_default_global_tools",
                return_value=[],
            )
        )
        stack.enter_context(
            patch(
                "app.adk.tools.registry.tool_registry.get_default_registry",
                return_value=MagicMock(name="fake_registry"),
            )
        )
        stack.enter_context(
            patch(
                "app.adk.agents.agent_factory.builder.build_agent",
                side_effect=lambda config, *, name, tools=None, **_kw: MagicMock(
                    name=f"llmagent_{name}", tools=tools or []
                ),
            )
        )

        ga_config = _make_ga_config()

        async def _build_for(account_id: str, session_state: dict[str, Any]) -> Any:
            return await asyncio.to_thread(
                sr._build_specialist,
                ga_config,
                "google_analytics_specialist",
                account_id,
                session_state=session_state,
                mcp_pool=shared_pool,
            )

        specialist_a, specialist_b = await asyncio.gather(
            _build_for(
                ACCOUNT_A,
                {"ga_credentials": GA_CREDS_A, "mcp_creds_google_analytics_mcp": MCP_CREDS_A},
            ),
            _build_for(
                ACCOUNT_B,
                {"ga_credentials": GA_CREDS_B, "mcp_creds_google_analytics_mcp": MCP_CREDS_B},
            ),
        )

    assert len(shared_pool._pool) == 2, (
        f"Shared pool must have exactly 2 entries; got {len(shared_pool._pool)}"
    )

    pool_keys = list(shared_pool._pool.keys())
    assert all(len(k) == 4 for k in pool_keys)

    kinds = {k[0] for k in pool_keys}
    server_ids = {k[1] for k in pool_keys}
    account_ids_in_keys = {k[2] for k in pool_keys}
    creds_hashes = {k[3] for k in pool_keys}

    assert kinds == {"cloud_run"}
    assert server_ids == {"google_analytics_mcp"}
    assert account_ids_in_keys == {ACCOUNT_A, ACCOUNT_B}
    assert len(creds_hashes) == 2, (
        f"Pool keys must have two distinct creds_hashes; got {creds_hashes}"
    )

    expected_hash_a = _compute_creds_hash(MCP_CREDS_A)
    expected_hash_b = _compute_creds_hash(MCP_CREDS_B)
    assert creds_hashes == {expected_hash_a, expected_hash_b}

    assert len(toolset_calls) == 2, (
        f"build_toolset_for_doc must be called exactly twice; got {len(toolset_calls)}"
    )
    assert all(s == "google_analytics_mcp" for s in toolset_calls)
    assert specialist_a is not specialist_b

    headers_a_again = provider(ctx_a)
    headers_b_again = provider(ctx_b)
    assert headers_a_again == headers_a
    assert headers_b_again == headers_b
