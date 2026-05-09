"""Integration tests for trace metadata completeness across span levels.

These tests are the audit half of Story 1.1.2-2: they assert that the
fields the trace-structure-spec §4 declares as required at each span level
actually flow into ``weave.attributes()`` (and ``call.summary``) at the
right callback / orchestrator site.

Validator unit tests live in ``test_compliance.py`` — those check the
*validator*. These check the *producers*: the chatbot callbacks, the tool
hooks, and the strategy orchestrator.

We mock ``weave`` rather than a live trace because the goal is to capture
exactly which dict gets passed to ``weave.attributes()`` — that's the
contract MER-E's validator reads later.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.adk.tracking.compliance import (
    REQUIRED_FIELDS,
    validate_trace_compliance,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _required_field_names() -> set[str]:
    return set(REQUIRED_FIELDS.keys())


def _root_spec_fields() -> set[str]:
    """Fields the spec requires at the root/L1 level (per §4.1-4.2)."""
    return {
        "agent_id",
        "agent_version",
        "account_id",
        "session_id",
        "environment",
        "rollout_percentage",
        "experiment_id",
        "variant_name",
    }


# ---------------------------------------------------------------------------
# Chatbot L1: weave_before_agent_callback
# ---------------------------------------------------------------------------


class TestChatbotL1Metadata:
    """The chatbot agent's L1 span must carry the full root metadata block."""

    @patch("app.adk.tracking.callbacks._get_chatbot_config_metadata")
    @patch("app.adk.tracking.callbacks._weave_call_context")
    @patch("app.adk.tracking.callbacks._weave_get_client")
    @patch("app.adk.tracking.callbacks.init_weave_if_needed")
    @patch("app.adk.tracking.callbacks.weave")
    def test_before_callback_passes_full_root_metadata(
        self,
        mock_weave: MagicMock,
        mock_init: MagicMock,
        mock_get_client: MagicMock,
        mock_call_ctx: MagicMock,
        mock_get_cfg: MagicMock,
    ) -> None:
        from app.adk.tracking.callbacks import weave_before_agent_callback

        # Pin a deterministic Firestore config snapshot.
        mock_get_cfg.return_value = {
            "version": "v1.2.3",
            "experiment_id": "rollout-q2",
            "variant_name": "treatment-a",
            "model": "gemini-2.5-pro",
        }

        mock_client = MagicMock()
        mock_client.create_call.return_value = MagicMock()
        mock_get_client.return_value = mock_client

        mock_attrs_ctx = MagicMock()
        mock_weave.attributes.return_value = mock_attrs_ctx

        # Build a CallbackContext with realistic state. account_id comes
        # from session state (set by the API in routers/chat.py); session_id
        # and user_id come from the ADK invocation_context.
        ctx = MagicMock()
        ctx.state = {"account_id": "acc_abc123"}
        ctx._invocation_context.session.id = "session_xyz789"
        ctx._invocation_context.user_id = "user_42"
        part = MagicMock()
        part.text = "What's our top traffic source?"
        content = MagicMock()
        content.parts = [part]
        ctx.user_content = content

        weave_before_agent_callback(ctx)

        mock_weave.attributes.assert_called_once()
        attrs = mock_weave.attributes.call_args[0][0]

        # Every spec-required root/L1 field must be present.
        missing = _root_spec_fields() - set(attrs.keys())
        assert not missing, f"Missing required L1 fields: {missing}"

        # Field values must come from the right sources.
        assert attrs["account_id"] == "acc_abc123"
        assert attrs["session_id"] == "session_xyz789"
        assert attrs["user_id"] == "user_42"
        assert attrs["agent_id"] == "ken_e_chatbot"
        assert attrs["agent_version"] == "v1.2.3"
        assert attrs["experiment_id"] == "rollout-q2"
        assert attrs["variant_name"] == "treatment-a"
        assert attrs["model_used"] == "gemini-2.5-pro"
        assert isinstance(attrs["rollout_percentage"], int)

    @patch("app.adk.tracking.callbacks._get_chatbot_config_metadata")
    @patch("app.adk.tracking.callbacks._weave_call_context")
    @patch("app.adk.tracking.callbacks._weave_get_client")
    @patch("app.adk.tracking.callbacks.init_weave_if_needed")
    @patch("app.adk.tracking.callbacks.weave")
    def test_emitted_metadata_passes_compliance_validator(
        self,
        mock_weave: MagicMock,
        mock_init: MagicMock,
        mock_get_client: MagicMock,
        mock_call_ctx: MagicMock,
        mock_get_cfg: MagicMock,
    ) -> None:
        """The dict the chatbot callback emits should pass the MER-E validator.

        This is the contract test: producer (callback) ↔ validator.
        """
        from app.adk.tracking.callbacks import weave_before_agent_callback

        mock_get_cfg.return_value = {
            "version": "v1.0.0",
            "experiment_id": "baseline",
            "variant_name": "baseline",
            "model": "gemini-2.5-pro",
        }
        mock_get_client.return_value.create_call.return_value = MagicMock()
        mock_weave.attributes.return_value = MagicMock()

        ctx = MagicMock()
        ctx.state = {"account_id": "acc_abc"}
        ctx._invocation_context.session.id = "session_xyz"
        ctx._invocation_context.user_id = "user_1"
        ctx.user_content = None  # No goal — simpler attrs dict

        weave_before_agent_callback(ctx)

        attrs = mock_weave.attributes.call_args[0][0]
        result = validate_trace_compliance(attrs)
        assert result.is_compliant, (
            f"Chatbot L1 metadata failed compliance: "
            f"{[str(i) for i in result.issues]}"
        )


# ---------------------------------------------------------------------------
# Chatbot L3: tool span attributes (hooks.adk_before_tool_callback)
# ---------------------------------------------------------------------------


class TestChatbotToolSpanAttrs:
    """L3 tool spans must carry tool_name, context_agent_id, and the context block."""

    @pytest.mark.asyncio
    @patch("app.adk.security.hooks.before_tool_execution_hook")
    @patch("app.adk.security.hooks._refresh_ga_token_if_needed")
    @patch("app.adk.security.hooks.weave")
    @patch("app.adk.security.hooks.init_weave_if_needed")
    async def test_before_tool_attaches_tool_name_and_agent_id(
        self,
        mock_init: MagicMock,
        mock_weave: MagicMock,
        mock_refresh: MagicMock,
        mock_perm_hook: MagicMock,
    ) -> None:
        from app.adk.security.hooks import adk_before_tool_callback

        # Permission allowed
        mock_result = MagicMock()
        mock_result.allowed = True
        mock_perm_hook.return_value = mock_result

        async def _noop(*_a, **_k):
            return None

        mock_refresh.side_effect = _noop

        mock_attrs_ctx = MagicMock()
        mock_weave.attributes.return_value = mock_attrs_ctx

        tool = MagicMock()
        tool.name = "ga_get_metrics"

        tool_context = MagicMock()
        tool_context.state = {}
        tool_context.user_content = None

        await adk_before_tool_callback(tool, {"property_id": "12345"}, tool_context)

        mock_weave.attributes.assert_called_once()
        attrs = mock_weave.attributes.call_args[0][0]
        assert attrs["tool_name"] == "ga_get_metrics"
        assert attrs["context_agent_id"] == "ken_e_chatbot"
        # context_previous_tool_calls is always set (even if empty)
        assert "context_previous_tool_calls" in attrs


# ---------------------------------------------------------------------------
# Strategy L2: _build_l2_span_attrs helper (called at sub-agent execution sites)
# ---------------------------------------------------------------------------


class TestStrategyL2Metadata:
    """Strategy sub-agent L2 spans must carry agent_id/version per Decision A2.

    After Feature 1.13 (PR #236) landed `_STRATEGY_STEP_METADATA` and call-site
    `weave.attributes()` blocks around `_execute_single_strategy`, Decision A2
    is implemented by extending those call-site blocks via the
    `_build_l2_span_attrs` helper. This test targets that helper directly —
    it's a pure function so mocking `weave` is unnecessary.
    """

    def test_helper_combines_workflow_step_and_agent_identity(self) -> None:
        from app.adk.agents.strategy_agent.orchestrator import _build_l2_span_attrs

        strategy_config = {
            "name": "business_strategy",
            "researcher_doc_id": "business_researcher",
            "researcher_meta": {
                "version": "v2.1.0",
                "experiment_id": "baseline",
                "variant_name": "baseline",
            },
        }

        attrs = _build_l2_span_attrs(strategy_config)

        # Agent identity from researcher_meta (Decision A2)
        assert attrs["agent_id"] == "business_researcher"
        assert attrs["agent_version"] == "v2.1.0"
        assert attrs["experiment_id"] == "baseline"
        assert attrs["variant_name"] == "baseline"

        # Step metadata from Feature 1.13 (_STRATEGY_STEP_METADATA)
        assert attrs["step_type"] == "research"
        assert attrs["step_index"] == 0
        assert attrs["depends_on_steps"] == []

    def test_helper_uses_marketing_dependency_on_business(self) -> None:
        """Marketing strategy depends on business (consumes product_category_names).

        Validates that the step metadata from Feature 1.13 flows through
        `_build_l2_span_attrs` untouched — the agent-identity merge doesn't
        clobber step_type or depends_on_steps.
        """
        from app.adk.agents.strategy_agent.orchestrator import _build_l2_span_attrs

        attrs = _build_l2_span_attrs(
            {
                "name": "marketing_strategy",
                "researcher_doc_id": "marketing_researcher",
                "researcher_meta": {
                    "version": "v1.3.0",
                    "experiment_id": "Increasing detail around ICP's",
                    "variant_name": "multi-part-search",
                },
            }
        )

        assert attrs["step_type"] == "generation"
        assert attrs["step_index"] == 1
        assert attrs["depends_on_steps"] == ["business_strategy"]
        assert attrs["agent_id"] == "marketing_researcher"
        assert attrs["agent_version"] == "v1.3.0"
        # Real experiment metadata flows from Firestore via researcher_meta
        assert attrs["experiment_id"] == "Increasing detail around ICP's"
        assert attrs["variant_name"] == "multi-part-search"

    def test_helper_falls_back_to_default_version_when_meta_missing(self) -> None:
        """If researcher_meta is empty, fall back to DEFAULT_VERSION (valid semver),
        not 'unknown' — the validator's semver regex would reject 'unknown'."""
        from app.adk.agents.strategy_agent.orchestrator import _build_l2_span_attrs
        from shared.trace_metadata import DEFAULT_VERSION

        attrs = _build_l2_span_attrs(
            {
                "name": "brand_guidelines",
                "researcher_doc_id": "brand_researcher",
                # No researcher_meta at all
            }
        )

        assert attrs["agent_version"] == DEFAULT_VERSION
        # And DEFAULT_VERSION must itself be valid semver per the validator
        from app.adk.tracking.compliance import REQUIRED_FIELDS, _validate_field

        version_issues = _validate_field(
            "agent_version",
            DEFAULT_VERSION,
            REQUIRED_FIELDS["agent_version"],
        )
        assert not version_issues

