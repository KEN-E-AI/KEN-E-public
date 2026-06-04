"""Unit tests for ga_oauth_after_tool_callback (AH-28).

Verifies:
* 401 indicator detection across all recognised signal shapes.
* Session-state mutation (_requires_reauth, _reauth_service).
* Canonical replacement response shape.
* Non-detection paths: success, non-401 errors, missing fields.
* Graceful degradation when detection logic itself raises.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.adk.security.hooks import (
    _GA_REAUTH_MESSAGE,
    _GA_REAUTH_RESPONSE,
    _is_ga_401,
    ga_oauth_after_tool_callback,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _MockState:
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
    state: _MockState = field(default_factory=_MockState)


def _tool() -> MagicMock:
    t = MagicMock()
    t.name = "run_report_mt"
    return t


def _ctx() -> _MockToolContext:
    return _MockToolContext()


# ---------------------------------------------------------------------------
# Tests for _is_ga_401 (pure unit — no async)
# ---------------------------------------------------------------------------


class TestIsGa401:
    def test_dict_with_error_flag_and_401_message(self) -> None:
        assert _is_ga_401({"error": True, "message": "401 Unauthorized"}) is True

    def test_dict_with_is_error_flag_and_token_expired_message(self) -> None:
        assert _is_ga_401({"isError": True, "message": "Token expired"}) is True

    def test_dict_with_is_error_and_unauthorized_message(self) -> None:
        assert _is_ga_401({"isError": True, "message": "unauthorized access"}) is True

    def test_dict_with_token_has_been_revoked(self) -> None:
        assert (
            _is_ga_401({"error": True, "message": "Token has been revoked"}) is True
        )

    def test_dict_with_invalid_grant(self) -> None:
        assert _is_ga_401({"error": True, "message": "invalid_grant"}) is True

    def test_dict_with_authentication_required_error(self) -> None:
        assert (
            _is_ga_401({"error": "authentication_required", "message": "expired"})
            is True
        )

    def test_dict_with_adk_error_sentinel_401(self) -> None:
        assert _is_ga_401({"_error": "HTTPError 401 Unauthorized"}) is True

    def test_dict_with_adk_error_sentinel_unauthorized(self) -> None:
        assert _is_ga_401({"_error": "unauthorized request"}) is True

    def test_plain_string_with_only_weak_indicator_returns_false(self) -> None:
        # "401" is a weak indicator — plain string path only matches strong indicators
        # to avoid false positives (e.g. log lines mentioning HTTP 401 codes that
        # are not OAuth token expiry errors).
        assert _is_ga_401("Error: 401 from GA MCP") is False

    def test_plain_string_token_expired(self) -> None:
        assert _is_ga_401("token expired") is True

    # Non-detection paths
    def test_success_dict_returns_false(self) -> None:
        assert _is_ga_401({"data": [{"sessions": 100}]}) is False

    def test_permission_denied_error_returns_false(self) -> None:
        assert _is_ga_401({"error": "permission_denied", "message": "Forbidden"}) is False

    def test_empty_dict_returns_false(self) -> None:
        assert _is_ga_401({}) is False

    def test_none_returns_false(self) -> None:
        assert _is_ga_401(None) is False

    def test_integer_returns_false(self) -> None:
        assert _is_ga_401(42) is False

    def test_list_returns_false(self) -> None:
        assert _is_ga_401([1, 2, 3]) is False

    def test_success_string_returns_false(self) -> None:
        assert _is_ga_401("All good") is False

    def test_error_flag_false_with_unrelated_message(self) -> None:
        # error=False means not an error
        assert _is_ga_401({"error": False, "message": "ok"}) is False

    def test_message_only_no_error_flag_with_strong_indicator(self) -> None:
        # message path without an error/isError key — strong indicator matches
        assert _is_ga_401({"message": "invalid_grant from provider"}) is True

    def test_message_only_no_indicator_returns_false(self) -> None:
        assert _is_ga_401({"message": "some data returned"}) is False

    def test_message_only_weak_indicator_without_error_flag_returns_false(self) -> None:
        # "401" is a weak indicator — must NOT match in the message-only path
        # to avoid false positives on GA data like "Processed 401 rows" or
        # property IDs containing "401".
        assert _is_ga_401({"message": "Processed 401 rows"}) is False

    def test_message_only_unauthorized_without_error_flag_returns_false(self) -> None:
        # "unauthorized" is a weak indicator — must NOT match in message-only path
        assert _is_ga_401({"message": "property unauthorized for reporting"}) is False

    def test_weak_indicator_with_error_flag_still_matches(self) -> None:
        # "401" IS still matched when the error flag is present
        assert _is_ga_401({"error": True, "message": "HTTP 401 response from GA"}) is True

    def test_plain_string_weak_indicator_returns_false(self) -> None:
        # "401" alone as a plain string is a weak indicator — no match on plain strings
        assert _is_ga_401("401") is False

    def test_plain_string_strong_indicator_matches(self) -> None:
        # Strong indicators still match in plain string path
        assert _is_ga_401("invalid_grant: token revoked") is True


# ---------------------------------------------------------------------------
# Tests for ga_oauth_after_tool_callback
# ---------------------------------------------------------------------------


class TestGaOauthAfterToolCallback:
    @pytest.mark.asyncio
    async def test_sets_requires_reauth_on_401(self) -> None:
        """AC: _requires_reauth and _reauth_service set on 401 response."""
        ctx = _ctx()
        response = {"error": True, "message": "401 Unauthorized"}

        await ga_oauth_after_tool_callback(_tool(), {}, ctx, response)

        assert ctx.state["_requires_reauth"] is True
        assert ctx.state["_reauth_service"] == "google-analytics"

    @pytest.mark.asyncio
    async def test_returns_canonical_response_shape_on_401(self) -> None:
        """AC: replacement dict matches the canonical authentication_required shape."""
        ctx = _ctx()
        response = {"error": True, "message": "token expired"}

        result = await ga_oauth_after_tool_callback(_tool(), {}, ctx, response)

        assert result is not None
        assert result["error"] == "authentication_required"
        assert result["requires_reauth"] is True
        assert _GA_REAUTH_MESSAGE in result["message"]

    @pytest.mark.asyncio
    async def test_returns_none_on_success_response(self) -> None:
        """AC: passthrough (None) on success responses."""
        ctx = _ctx()
        response = {"data": [{"sessions": 1000}]}

        result = await ga_oauth_after_tool_callback(_tool(), {}, ctx, response)

        assert result is None
        assert "_requires_reauth" not in ctx.state._data

    @pytest.mark.asyncio
    async def test_returns_none_on_permission_denied(self) -> None:
        """AC: detection does not fire on non-401 errors like permission_denied."""
        ctx = _ctx()
        response = {"error": "permission_denied", "message": "Forbidden"}

        result = await ga_oauth_after_tool_callback(_tool(), {}, ctx, response)

        assert result is None
        assert "_requires_reauth" not in ctx.state._data

    @pytest.mark.asyncio
    async def test_returns_none_when_detection_logic_raises(self) -> None:
        """AC: graceful degradation — returns None (passthrough) when detection raises."""
        ctx = _ctx()

        with patch(
            "app.adk.security.hooks._is_ga_401",
            side_effect=RuntimeError("unexpected"),
        ):
            result = await ga_oauth_after_tool_callback(_tool(), {}, ctx, {"error": True})

        assert result is None
        assert "_requires_reauth" not in ctx.state._data

    @pytest.mark.asyncio
    async def test_idempotent_on_double_detection(self) -> None:
        """Second write of _requires_reauth is a no-op (same value)."""
        ctx = _ctx()
        ctx.state["_requires_reauth"] = True
        ctx.state["_reauth_service"] = "google-analytics"
        response = {"error": True, "message": "401 Unauthorized"}

        result = await ga_oauth_after_tool_callback(_tool(), {}, ctx, response)

        assert ctx.state["_requires_reauth"] is True
        assert ctx.state["_reauth_service"] == "google-analytics"
        assert result is not None  # still returns the replacement dict

    @pytest.mark.asyncio
    async def test_response_dict_is_a_fresh_copy(self) -> None:
        """Returned dict is a copy of _GA_REAUTH_RESPONSE, not the sentinel itself."""
        ctx = _ctx()
        response = {"error": True, "message": "token expired"}

        result = await ga_oauth_after_tool_callback(_tool(), {}, ctx, response)

        assert result is not _GA_REAUTH_RESPONSE
        assert result == _GA_REAUTH_RESPONSE

    @pytest.mark.asyncio
    async def test_all_indicator_strings_trigger_detection_with_error_flag(self) -> None:
        """AC: all six indicator strings trigger detection when an error flag is present.

        Weak indicators ("401", "unauthorized", "authentication_required") only
        match when the response carries an explicit error or isError flag.  When
        the flag is present (as here), all six indicators must still fire.
        """
        indicators = [
            "401",
            "unauthorized",
            "token expired",
            "token has been revoked",
            "invalid_grant",
            "authentication_required",
        ]
        for ind in indicators:
            ctx = _ctx()
            response = {"error": True, "message": ind}
            result = await ga_oauth_after_tool_callback(_tool(), {}, ctx, response)
            assert result is not None, f"Expected detection for indicator {ind!r}"
            assert ctx.state["_requires_reauth"] is True

    @pytest.mark.asyncio
    async def test_detection_is_case_insensitive(self) -> None:
        """Indicator matching is case-insensitive."""
        ctx = _ctx()
        response = {"error": True, "message": "TOKEN EXPIRED"}

        result = await ga_oauth_after_tool_callback(_tool(), {}, ctx, response)

        assert result is not None
        assert ctx.state["_requires_reauth"] is True

    @pytest.mark.asyncio
    async def test_plain_string_tool_response(self) -> None:
        """Plain string response with a strong indicator triggers detection."""
        ctx = _ctx()

        result = await ga_oauth_after_tool_callback(
            _tool(), {}, ctx, "token has been revoked by the authorization server"
        )

        assert result is not None
        assert ctx.state["_requires_reauth"] is True

    @pytest.mark.asyncio
    async def test_adk_error_sentinel_triggers_detection(self) -> None:
        """ADK exception sentinel (_error key) triggers detection."""
        ctx = _ctx()
        response = {"_error": "HTTPError: 401 Unauthorized from GA MCP"}

        result = await ga_oauth_after_tool_callback(_tool(), {}, ctx, response)

        assert result is not None
        assert ctx.state["_requires_reauth"] is True
