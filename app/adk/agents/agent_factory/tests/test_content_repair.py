"""Tests for the orphaned-function-call history repair (mixed-turn FC drop).

ADK 2.0's chat-mode task-dispatch wrapper breaks out of the agent's event
generator on detecting task-delegation FunctionCalls, discarding the
function-response event of any REGULAR tool the model called in the same
parallel turn. The session then holds a model turn with N function calls and
fewer than N responses; the next request replaying that history is rejected by
Gemini (400 "number of function response parts ... equal to ... function call
parts") and the session is permanently poisoned. The repair callback pads
synthetic responses for historical orphans — and must never touch the live
trailing turn.
"""

from unittest.mock import MagicMock

from google.adk.models.llm_request import LlmRequest
from google.genai import types

from app.adk.agents.agent_factory.content_repair import (
    repair_orphaned_function_calls_before_model,
)


def _fc(name: str, fc_id: str | None = None) -> types.Part:
    return types.Part(
        function_call=types.FunctionCall(name=name, args={}, id=fc_id)
    )


def _fr(name: str, fr_id: str | None = None) -> types.Part:
    return types.Part(
        function_response=types.FunctionResponse(
            name=name, response={"result": "ok"}, id=fr_id
        )
    )


def _txt(s: str) -> types.Part:
    return types.Part(text=s)


def _repair(contents: list[types.Content]) -> LlmRequest:
    req = LlmRequest(contents=contents)
    result = repair_orphaned_function_calls_before_model(MagicMock(), req)
    assert result is None
    return req


def _fr_names(content: types.Content) -> list[str]:
    return [
        p.function_response.name
        for p in (content.parts or [])
        if p.function_response is not None
    ]


class TestPadsPoisonedHistory:
    def test_pads_missing_fr_in_poisoned_pair(self) -> None:
        # The live staging shape: model turn with set_todo_list + 2 GA task
        # dispatches, answered by only the 2 synthesized task FRs.
        contents = [
            types.Content(role="user", parts=[_txt("analyse my site")]),
            types.Content(
                role="model",
                parts=[
                    _txt("plan"),
                    _fc("set_todo_list"),
                    _fc("google_analytics_specialist"),
                    _fc("google_analytics_specialist"),
                ],
            ),
            types.Content(
                role="user",
                parts=[
                    _fr("google_analytics_specialist"),
                    _fr("google_analytics_specialist"),
                ],
            ),
        ]

        req = _repair(contents)

        names = _fr_names(req.contents[2])
        assert sorted(names) == [
            "google_analytics_specialist",
            "google_analytics_specialist",
            "set_todo_list",
        ]
        padded = next(
            p.function_response
            for p in req.contents[2].parts
            if p.function_response is not None
            and p.function_response.name == "set_todo_list"
        )
        assert "interrupted" in str(padded.response).lower()

    def test_pads_by_id_when_ids_present(self) -> None:
        contents = [
            types.Content(
                role="model",
                parts=[_fc("ga", "id-a"), _fc("ga", "id-b"), _fc("todo", "id-c")],
            ),
            types.Content(role="user", parts=[_fr("ga", "id-a"), _fr("ga", "id-b")]),
            types.Content(role="model", parts=[_txt("done")]),
        ]

        req = _repair(contents)

        frs = [
            p.function_response
            for p in req.contents[1].parts
            if p.function_response is not None
        ]
        assert len(frs) == 3
        padded = next(fr for fr in frs if fr.name == "todo")
        assert padded.id == "id-c"

    def test_pads_same_name_multiplicity_without_ids(self) -> None:
        contents = [
            types.Content(role="model", parts=[_fc("ga"), _fc("ga")]),
            types.Content(role="user", parts=[_fr("ga")]),
            types.Content(role="user", parts=[_txt("next question")]),
        ]

        req = _repair(contents)

        assert _fr_names(req.contents[1]) == ["ga", "ga"]

    def test_inserts_fr_content_when_responses_fully_dropped(self) -> None:
        contents = [
            types.Content(role="model", parts=[_fc("set_todo_list")]),
            types.Content(role="model", parts=[_txt("final answer")]),
        ]

        req = _repair(contents)

        assert len(req.contents) == 3
        inserted = req.contents[1]
        assert inserted.role == "user"
        assert _fr_names(inserted) == ["set_todo_list"]


class TestLeavesValidHistoryAlone:
    def test_live_trailing_fc_turn_untouched(self) -> None:
        # The trailing model turn's responses are legitimately still pending.
        contents = [
            types.Content(role="user", parts=[_txt("hi")]),
            types.Content(role="model", parts=[_fc("ga"), _fc("set_todo_list")]),
        ]

        req = _repair(contents)

        assert len(req.contents) == 2
        assert _fr_names(req.contents[1]) == []

    def test_balanced_history_is_noop(self) -> None:
        contents = [
            types.Content(role="user", parts=[_txt("hi")]),
            types.Content(role="model", parts=[_fc("ga", "x")]),
            types.Content(role="user", parts=[_fr("ga", "x")]),
            types.Content(role="model", parts=[_txt("answer")]),
        ]

        req = _repair(contents)

        assert len(req.contents) == 4
        assert _fr_names(req.contents[2]) == ["ga"]

    def test_idempotent(self) -> None:
        contents = [
            types.Content(role="model", parts=[_fc("todo"), _fc("ga")]),
            types.Content(role="user", parts=[_fr("ga")]),
            types.Content(role="model", parts=[_txt("answer")]),
        ]

        req = _repair(contents)
        first = [c.model_dump() for c in req.contents]
        req2 = LlmRequest(contents=req.contents)
        repair_orphaned_function_calls_before_model(MagicMock(), req2)

        assert [c.model_dump() for c in req2.contents] == first

    def test_empty_contents_noop(self) -> None:
        req = LlmRequest(contents=[])
        assert (
            repair_orphaned_function_calls_before_model(MagicMock(), req) is None
        )


class TestSupervisorInstructionForbidsMixedTurns:
    def test_fragment_contains_no_mixing_rule(self) -> None:
        from app.adk.agents.orchestration.supervisor import (
            SUPERVISOR_INSTRUCTION_FRAGMENT,
        )

        assert (
            "Never combine `set_todo_list`, `update_todo_list`,"
            in SUPERVISOR_INSTRUCTION_FRAGMENT
        )
