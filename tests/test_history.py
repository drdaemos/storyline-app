"""Tests for keeping saved conversations actionable."""

from pydantic_ai import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.messages import NativeToolCallPart, NativeToolReturnPart, RetryPromptPart, UserPromptPart

from storyline.agent import actionable_history, without_last_turn


def _prompt(text: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=text)])


def test_complete_history_is_unchanged() -> None:
    history = [
        _prompt("Continue."),
        ModelResponse(parts=[TextPart(content="Reading."), ToolCallPart(tool_name="read_lore", args={"filename": "a.md"}, tool_call_id="c1")]),
        ModelRequest(parts=[ToolReturnPart(tool_name="read_lore", content="A.", tool_call_id="c1")]),
        ModelResponse(parts=[TextPart(content="Done.")]),
    ]

    assert actionable_history(history) == history


def test_unanswered_tool_calls_are_dropped_and_the_rest_of_the_reply_kept() -> None:
    history = [
        _prompt("Try again."),
        ModelResponse(parts=[TextPart(content="Loading research."), ToolCallPart(tool_name="load_capability", args={"id": "research"}, tool_call_id="c1")]),
    ]

    repaired = actionable_history(history)

    assert repaired[0] == history[0]
    assert repaired[1].parts == [TextPart(content="Loading research.")]
    assert len(repaired) == 2


def test_a_reply_left_empty_is_dropped() -> None:
    history = [_prompt("Go."), ModelResponse(parts=[ToolCallPart(tool_name="set_agenda", args={}, tool_call_id="c1")])]

    assert actionable_history(history) == [history[0]]


def test_results_and_retries_without_their_call_are_dropped() -> None:
    history = [
        _prompt("Go."),
        ModelRequest(
            parts=[
                ToolReturnPart(tool_name="read_lore", content="A.", tool_call_id="gone"),
                RetryPromptPart(content="Bad args.", tool_name="edit_lore", tool_call_id="gone-too"),
                UserPromptPart(content="Still here."),
            ]
        ),
    ]

    repaired = actionable_history(history)

    assert repaired[0] == history[0]
    assert [part.content for part in repaired[1].parts] == ["Still here."]
    assert len(repaired) == 2


def test_a_retried_call_counts_as_answered() -> None:
    history = [
        _prompt("Go."),
        ModelResponse(parts=[ToolCallPart(tool_name="edit_lore", args={}, tool_call_id="c1")]),
        ModelRequest(parts=[RetryPromptPart(content="Bad args.", tool_name="edit_lore", tool_call_id="c1")]),
    ]

    assert actionable_history(history) == history


def test_native_calls_need_their_result_in_the_same_reply() -> None:
    searched = ModelResponse(
        parts=[
            NativeToolCallPart(tool_name="web_search", args={"query": "vampires"}, tool_call_id="s1"),
            NativeToolReturnPart(tool_name="web_search", content="results", tool_call_id="s1"),
            NativeToolCallPart(tool_name="web_search", args={"query": "cut off"}, tool_call_id="s2"),
            TextPart(content="Found some."),
        ]
    )

    (_, repaired) = actionable_history([_prompt("Research."), searched])

    assert [part.tool_call_id for part in repaired.parts if isinstance(part, NativeToolCallPart)] == ["s1"]


def _turn_start(text: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=["<story-snapshot>\nThe story is empty.\n</story-snapshot>", text])])


def test_removing_the_last_turn_returns_what_the_user_wrote() -> None:
    first = [_turn_start("Plan it."), ModelResponse(parts=[TextPart(content="Planned.")])]
    last = [
        _turn_start("Write the opening."),
        ModelResponse(parts=[ToolCallPart(tool_name="read_lore", args={}, tool_call_id="c1")]),
        ModelRequest(parts=[ToolReturnPart(tool_name="read_lore", content="A.", tool_call_id="c1"), UserPromptPart(content="Make it rain.")]),
        ModelResponse(parts=[TextPart(content="Wrote it.")]),
    ]

    removed = without_last_turn([*first, *last])

    assert removed is not None
    assert removed.history == first
    assert removed.prompt == "Write the opening.\n\nMake it rain."


def test_an_empty_conversation_has_no_turn_to_remove() -> None:
    assert without_last_turn([]) is None


def test_histories_without_snapshots_remove_from_the_last_user_message() -> None:
    history = [_prompt("One."), ModelResponse(parts=[TextPart(content="A.")]), _prompt("Two."), ModelResponse(parts=[TextPart(content="B.")])]

    removed = without_last_turn(history)

    assert removed is not None
    assert removed.history == history[:2]
    assert removed.prompt == "Two."
