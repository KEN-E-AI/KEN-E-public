"""Unit tests for chat.py function-event filtering helpers."""

import json

import pytest
from src.kene_api.routers.chat import (
    _contains_function_event_str,
    _is_function_event_json,
    _is_function_event_part,
)


class TestIsFunctionEventPart:
    """Tests for _is_function_event_part."""

    @pytest.mark.parametrize(
        "part",
        [
            {"function_call": {"name": "search", "args": {}}},
            {"function_response": {"name": "search", "output": "result"}},
            {"function_call": {}, "function_response": {}},
        ],
        ids=["function_call", "function_response", "both_keys"],
    )
    def test_returns_true_for_function_events(self, part: dict) -> None:
        assert _is_function_event_part(part) is True

    @pytest.mark.parametrize(
        "part",
        [
            {"text": "Hello"},
            {"content": "some content"},
            {},
        ],
        ids=["text_part", "content_part", "empty_dict"],
    )
    def test_returns_false_for_non_function_parts(self, part: dict) -> None:
        assert _is_function_event_part(part) is False


class TestIsFunctionEventJson:
    """Tests for _is_function_event_json."""

    def test_returns_true_for_json_function_call(self) -> None:
        chunk = json.dumps({"function_call": {"name": "tool", "args": {}}})
        assert _is_function_event_json(chunk) is True

    def test_returns_true_for_json_function_response(self) -> None:
        chunk = json.dumps({"function_response": {"name": "tool", "output": "ok"}})
        assert _is_function_event_json(chunk) is True

    def test_returns_false_for_text_json(self) -> None:
        chunk = json.dumps({"text": "hello world"})
        assert _is_function_event_json(chunk) is False

    def test_returns_false_for_non_json_string(self) -> None:
        assert _is_function_event_json("plain text") is False

    def test_returns_false_for_invalid_json(self) -> None:
        assert _is_function_event_json("{broken json") is False

    def test_handles_whitespace_padding(self) -> None:
        chunk = '  {"function_call": {"name": "x"}}  '
        assert _is_function_event_json(chunk) is True

    def test_returns_false_for_empty_string(self) -> None:
        assert _is_function_event_json("") is False


class TestContainsFunctionEventStr:
    """Tests for _contains_function_event_str."""

    @pytest.mark.parametrize(
        "text",
        [
            "{'function_call': {'name': 'search'}}some text",
            "{'function_response': {'name': 'search'}}",
            '{"function_call": {"name": "search"}}',
            '{"function_response": {"name": "search"}}',
            "prefix{'function_call': {}}suffix",
        ],
        ids=["python_call", "python_response", "json_call", "json_response", "embedded"],
    )
    def test_returns_true_when_function_event_present(self, text: str) -> None:
        assert _contains_function_event_str(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "Hello, this is a normal response",
            '{"text": "hello"}',
            "",
            "function_call without braces",
        ],
        ids=["normal_text", "json_text", "empty_string", "no_braces"],
    )
    def test_returns_false_when_no_function_event(self, text: str) -> None:
        assert _contains_function_event_str(text) is False
