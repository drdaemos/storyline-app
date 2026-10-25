"""Tests for the room protocol and the conversation entries derived from saved history."""

from pathlib import Path
from typing import get_args

import pytest
from pydantic import TypeAdapter
from pydantic_ai import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.messages import RetryPromptPart, UserPromptPart

from storyline.agent import turn_prompt
from storyline.registry import MECHANICS
from storyline.room import (
    EVENT_TYPES,
    ConversationReplaced,
    MessageEntry,
    RoomEvent,
    RoomSnapshot,
    ToolCallEntry,
    event_type_name,
    protocol_schema,
    transcript_entries,
)
from storyline.room.export import FRONTEND_PROTOCOL_PATH, protocol_document
from storyline.workspace.file_story import FileStory

REPOSITORY_ROOT = Path(__file__).parent.parent


def test_the_checked_in_protocol_description_matches_the_protocol() -> None:
    checked_in = (REPOSITORY_ROOT / FRONTEND_PROTOCOL_PATH).read_text(encoding="utf-8")

    assert checked_in == protocol_document(), "frontend/src/protocol/protocol.json is out of date; run `uv run python -m storyline.room.export` and commit the result."


def test_every_event_type_is_in_the_event_union_and_every_union_member_is_an_event_type() -> None:
    union, _ = get_args(RoomEvent.__value__)

    assert set(get_args(union)) == set(EVENT_TYPES)
    assert len(EVENT_TYPES) == len(set(EVENT_TYPES))


def test_event_type_names_are_unique() -> None:
    names = [event_type_name(event_type) for event_type in EVENT_TYPES]

    assert len(names) == len(set(names))
    assert protocol_schema()["events"] == names


def test_events_and_snapshots_survive_a_trip_through_json() -> None:
    event = ConversationReplaced(entries=(MessageEntry(role="user", text="Hi."), ToolCallEntry(tool_call_id="c1", tool_name="list_lore", arguments="{}", result="None.", outcome="success")))
    snapshot = RoomSnapshot(story="noir", preset="co-writing", model_name="m", model_from_story=False, entries=event.entries, hidden_entries=2, agenda=())

    assert TypeAdapter(RoomEvent).validate_json(event.model_dump_json()) == event
    assert RoomSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot


def _user_request(text: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=text)])


def test_a_conversation_becomes_user_writer_and_tool_call_entries_in_order() -> None:
    history = [
        _user_request("Add an opening."),
        ModelResponse(parts=[TextPart(content="On it."), ToolCallPart(tool_name="edit_script", args={"replacement": "FADE IN:"}, tool_call_id="c1")]),
        ModelRequest(parts=[ToolReturnPart(tool_name="edit_script", content="Updated.", tool_call_id="c1")]),
        ModelResponse(parts=[TextPart(content="Added an **opening**.")]),
    ]

    assert transcript_entries(history) == [
        MessageEntry(role="user", text="Add an opening."),
        MessageEntry(role="writer", text="On it."),
        ToolCallEntry(tool_call_id="c1", tool_name="edit_script", arguments='{"replacement":"FADE IN:"}', result="Updated.", outcome="success"),
        MessageEntry(role="writer", text="Added an **opening**."),
    ]


def test_a_tool_call_without_a_result_is_marked_interrupted() -> None:
    history = [_user_request("Go."), ModelResponse(parts=[ToolCallPart(tool_name="list_lore", args={}, tool_call_id="c1")])]

    [_, call] = transcript_entries(history)

    assert isinstance(call, ToolCallEntry)
    assert (call.result, call.outcome) == (None, "interrupted")


def test_a_retried_tool_call_shows_the_retry_message_as_its_result() -> None:
    history = [
        _user_request("Fix the lore."),
        ModelResponse(parts=[ToolCallPart(tool_name="edit_lore", args={"filename": "a.md"}, tool_call_id="c1")]),
        ModelRequest(parts=[RetryPromptPart(content="Missing field: find", tool_name="edit_lore", tool_call_id="c1")]),
    ]

    [_, call] = transcript_entries(history)

    assert isinstance(call, ToolCallEntry)
    assert call.outcome == "retry"
    assert call.result is not None and "Missing field: find" in call.result


def test_blank_writer_text_is_left_out() -> None:
    history = [_user_request("Go."), ModelResponse(parts=[TextPart(content="  \n")])]

    assert transcript_entries(history) == [MessageEntry(role="user", text="Go.")]


@pytest.mark.asyncio
async def test_prompts_show_what_the_user_wrote_without_the_story_snapshot(tmp_path, registry=MECHANICS) -> None:
    story = FileStory(tmp_path)
    await story.append_script(text="Secret opening.")
    prompt = await turn_prompt(story, "Continue.", registry=MECHANICS)

    entries = transcript_entries([_user_request(prompt)])

    assert entries == [MessageEntry(role="user", text="Continue.")]
