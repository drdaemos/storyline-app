"""Tests for what the room tells interfaces about sealed work: the story's preset and which tool calls are sealed."""

import json
from collections.abc import AsyncIterator

import pytest
from pydantic_ai.messages import ModelMessage, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel

from storyline.agent import create_writer_agent
from storyline.room import RoomEvent, StoryFilesChanged, StoryRoom, ToolCallEntry, ToolCallFinished, ToolCallStarted, transcript_entries
from storyline.workspace import StorySetup
from storyline.workspace.file_story import FileStory

LORE = "---\nsummary: {summary}\nkeywords: k\n---\nBody.\n"


class Events:
    def __init__(self) -> None:
        self.events: list[RoomEvent] = []

    async def __call__(self, event: RoomEvent) -> None:
        self.events.append(event)

    def of[E](self, event_type: type[E]) -> list[E]:
        return [event for event in self.events if isinstance(event, event_type)]


def _calls_then_done(*calls: tuple[str, dict[str, object]]) -> FunctionModel:
    """A model that makes the given tool calls in order, one per request, and then says it is done."""

    async def stream(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        made = sum(isinstance(part, ToolReturnPart) for message in messages for part in message.parts)
        if made < len(calls):
            name, arguments = calls[made]
            yield {0: DeltaToolCall(name=name, json_args=json.dumps(arguments), tool_call_id=f"call-{made}")}
        else:
            yield "Done."

    return FunctionModel(stream_function=stream)


async def _story(tmp_path, *, mechanics: tuple[str, ...] = ("sealed",)) -> FileStory:
    story = FileStory(tmp_path)
    await story.write_setup(setup=StorySetup(mechanics=mechanics))
    await story.write_lore(filename="city.md", content=LORE.format(summary="The city."))
    await story.write_lore(filename="sealed/vera.md", content=LORE.format(summary="What Vera wants."))
    return story


async def _run(story: FileStory, model: FunctionModel) -> tuple[StoryRoom, Events]:
    room = await StoryRoom.open(story=story, agent=create_writer_agent(), model=model)
    events = Events()
    room.add_listener(events)
    await room.send_prompt("Go.")
    await room.wait_until_idle()
    return room, events


@pytest.mark.asyncio
async def test_the_snapshot_names_the_stories_preset(tmp_path) -> None:
    room = await StoryRoom.open(story=FileStory(tmp_path), agent=create_writer_agent())

    assert room.snapshot().preset == "co-writing"


@pytest.mark.asyncio
async def test_tool_events_and_entries_are_sealed_when_the_call_touches_a_sealed_file(tmp_path) -> None:
    story = await _story(tmp_path)
    model = _calls_then_done(("read_lore", {"filename": "sealed/vera.md"}), ("read_lore", {"filename": "city.md"}), ("list_lore", {}))

    room, events = await _run(story, model)

    assert [(started.tool_name, started.sealed) for started in events.of(ToolCallStarted)] == [("read_lore", True), ("read_lore", False), ("list_lore", True)]
    assert [finished.sealed for finished in events.of(ToolCallFinished)] == [True, False, True]
    entries = [entry for entry in room.snapshot().entries if isinstance(entry, ToolCallEntry)]
    assert [entry.sealed for entry in entries] == [True, False, True]


@pytest.mark.asyncio
async def test_live_entries_are_sealed_while_the_tool_is_still_working(tmp_path) -> None:
    story = await _story(tmp_path)
    room = await StoryRoom.open(story=story, agent=create_writer_agent(), model=_calls_then_done(("read_lore", {"filename": "sealed/vera.md"})))
    seen: list[bool] = []

    async def watch(event: RoomEvent) -> None:
        if isinstance(event, ToolCallStarted):
            live = [entry for entry in room.snapshot().entries if isinstance(entry, ToolCallEntry)]
            seen.extend(entry.sealed for entry in live)

    room.add_listener(watch)
    await room.send_prompt("Go.")
    await room.wait_until_idle()

    assert seen == [True]


@pytest.mark.asyncio
async def test_listing_the_lore_is_not_sealed_in_a_story_without_the_sealed_mechanic(tmp_path) -> None:
    story = await _story(tmp_path, mechanics=())

    _, events = await _run(story, _calls_then_done(("list_lore", {}), ("read_lore", {"filename": "sealed/vera.md"})))

    assert [started.sealed for started in events.of(ToolCallStarted)] == [False, True]


@pytest.mark.asyncio
async def test_the_restored_transcript_carries_the_same_flags(tmp_path) -> None:
    story = await _story(tmp_path)
    model = _calls_then_done(("read_lore", {"filename": "sealed/vera.md"}), ("read_lore", {"filename": "city.md"}))
    await _run(story, model)

    reopened = await StoryRoom.open(story=story, agent=create_writer_agent())
    entries = [entry for entry in reopened.snapshot().entries if isinstance(entry, ToolCallEntry)]

    assert [(entry.tool_name, entry.sealed) for entry in entries] == [("read_lore", True), ("read_lore", False)]
    history = await story.read_message_history()
    assert [entry.sealed for entry in transcript_entries(history) if isinstance(entry, ToolCallEntry)] == [False, False]
    assert [entry.sealed for entry in transcript_entries(history, lambda name, arguments: name == "read_lore") if isinstance(entry, ToolCallEntry)] == [True, True]


@pytest.mark.asyncio
async def test_a_lore_write_on_a_sealed_file_still_tells_listeners_the_lore_changed(tmp_path) -> None:
    story = await _story(tmp_path)
    content = LORE.format(summary="Vera, rewritten.")

    _, events = await _run(story, _calls_then_done(("write_lore", {"filename": "sealed/vera.md", "content": content})))

    assert events.of(ToolCallStarted)[0].sealed is True
    assert StoryFilesChanged(script=False, lore=True) in events.events
    assert "rewritten" in await story.read_lore(filename="sealed/vera.md")
