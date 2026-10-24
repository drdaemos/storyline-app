"""The web interface offers every operation of the room protocol and carries every event of it."""

import re

import pytest
from fastapi import FastAPI

from storyline.room import (
    EVENT_TYPES,
    ActivityChanged,
    AgendaChanged,
    ConversationReplaced,
    DraftRestored,
    MessageEntry,
    ModelChanged,
    Notice,
    Operation,
    QueueChanged,
    ReplyDelta,
    ReplyFinished,
    ReplyStarted,
    RoomSnapshot,
    StoryFilesChanged,
    ToolCallEntry,
    ToolCallFinished,
    ToolCallStarted,
    TurnFinished,
    UserMessageAdded,
    event_type_name,
)
from storyline.web.operations import OPERATION_ROUTES
from storyline.web.sse import event_message, snapshot_message
from storyline.workspace import AgendaItem
from tests.web_support import EVENT_ADAPTER, local_app, parse_sse

SAMPLE_EVENTS = (
    UserMessageAdded(text="Begin.\nWith a second line."),
    ReplyStarted(reply_id="r1"),
    ReplyDelta(reply_id="r1", text="Fog\r\nrolled   in."),
    ReplyFinished(reply_id="r1"),
    ToolCallStarted(tool_call_id="c1", tool_name="append_script", arguments='{"text": "Fog."}', sealed=True),
    ToolCallFinished(tool_call_id="c1", result="Added 4 characters.", outcome="ok", sealed=True),
    ActivityChanged(activity="using_tool", tool_name="append_script"),
    QueueChanged(prompts=("Also this.", "And this.")),
    AgendaChanged(items=(AgendaItem(id="a1", title="Name the harbor", status="working"),)),
    StoryFilesChanged(script=True, lore=False),
    TurnFinished(outcome="failed", error="provider down"),
    ConversationReplaced(
        entries=(MessageEntry(role="user", text="Hello."), ToolCallEntry(tool_call_id="c1", tool_name="list_lore", arguments="{}", result="[]", outcome="ok")),
        hidden_entries=3,
    ),
    DraftRestored(text="Undone prompt."),
    ModelChanged(model_name="openrouter:other/model"),
    Notice(level="error", text="The agenda is broken."),
)


def test_every_operation_has_a_route_and_only_operations_do() -> None:
    assert set(OPERATION_ROUTES) == set(Operation)


def _documented(path: str) -> str:
    """The path as OpenAPI documents it: without the converter of a path parameter, e.g. ``{filename:path}``."""
    return re.sub(r"\{(\w+):\w+\}", r"{\1}", path)


def _served_routes(app: FastAPI) -> set[tuple[str, str]]:
    """The (method, path template) pairs the app documents in its OpenAPI schema."""
    return {(method.upper(), path) for path, methods in app.openapi()["paths"].items() for method in methods}


def test_every_operation_route_is_registered_in_the_app(tmp_path) -> None:
    registered = _served_routes(local_app(tmp_path))

    for operation, (method, path) in OPERATION_ROUTES.items():
        assert (method, _documented(path)) in registered, f"{operation} is not served at {method} {path}"


def test_the_app_serves_no_api_route_that_is_not_an_operation(tmp_path) -> None:
    served = {(method, path) for method, path in _served_routes(local_app(tmp_path)) if path.startswith("/api")}

    assert served == {(method, _documented(path)) for method, path in OPERATION_ROUTES.values()}


def test_the_samples_cover_exactly_the_event_types_of_the_protocol() -> None:
    assert {type(event) for event in SAMPLE_EVENTS} == set(EVENT_TYPES)
    assert len(SAMPLE_EVENTS) == len(EVENT_TYPES)


@pytest.mark.parametrize("event", SAMPLE_EVENTS, ids=lambda event: type(event).__name__)
def test_every_event_survives_encoding_to_a_message_and_decoding_back(event) -> None:
    encoded = event_message(event)

    (message,) = parse_sse(encoded)
    assert message.event == event_type_name(type(event))
    assert "\n" not in message.data
    assert EVENT_ADAPTER.validate_json(message.data) == event
    assert message.room_event() == event


def test_the_snapshot_survives_encoding_to_a_message_and_decoding_back() -> None:
    snapshot = RoomSnapshot(
        story="harbor",
        preset="co-writing",
        model_name="openrouter:default/model",
        model_from_story=True,
        entries=(MessageEntry(role="writer", text="Fog.\nMore fog.", reply_id="r1"),),
        hidden_entries=2,
        agenda=(AgendaItem(id="a1", title="Name the harbor"),),
        activity="writing",
        queue=("Next.",),
    )

    (message,) = parse_sse(snapshot_message(snapshot))

    assert message.event == "snapshot"
    assert message.snapshot() == snapshot
