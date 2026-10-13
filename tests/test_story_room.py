"""Tests for a story's room, driven through its operations with scripted models and a real story on disk."""

import asyncio
import json
from collections.abc import AsyncIterator, Coroutine

import pytest
from pydantic_ai import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.messages import ModelMessage, UserPromptPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel

from storyline.agent import create_writer_agent, visible_prompt_text
from storyline.room import (
    ActivityChanged,
    AgendaChanged,
    ConversationReplaced,
    DraftRestored,
    MessageEntry,
    ModelChanged,
    Notice,
    QueueChanged,
    ReplyDelta,
    ReplyFinished,
    ReplyStarted,
    RoomBusyError,
    RoomEvent,
    RoomSnapshot,
    StoryFilesChanged,
    StoryRoom,
    ToolCallEntry,
    ToolCallFinished,
    ToolCallStarted,
    TurnFinished,
    UserMessageAdded,
    transcript_entries,
)
from storyline.workspace import AgendaItem
from storyline.workspace.file_story import AGENDA_FILENAME, FileStory

DEFAULT_MODEL = "openrouter:default/model"
LORE = "---\nsummary: The city.\nkeywords: city\n---\nBuffalo.\n"


class Recorder:
    """A room listener that keeps every event, and can wake a test when a given event arrives."""

    def __init__(self) -> None:
        self.events: list[RoomEvent] = []
        self._waiting: list[tuple[type, asyncio.Event]] = []

    async def __call__(self, event: RoomEvent) -> None:
        self.events.append(event)
        for event_type, arrived in self._waiting:
            if isinstance(event, event_type):
                arrived.set()

    async def wait_for(self, event_type: type) -> None:
        """Return once an event of ``event_type`` has been recorded."""
        if any(isinstance(event, event_type) for event in self.events):
            return
        arrived = asyncio.Event()
        self._waiting.append((event_type, arrived))
        await asyncio.wait_for(arrived.wait(), timeout=5)

    def summary(self) -> list[str]:
        """The events in order, one short readable string each, with the stream of reply deltas as they came."""
        return [_summarize(event) for event in self.events]

    def of[E](self, event_type: type[E]) -> list[E]:
        return [event for event in self.events if isinstance(event, event_type)]


def _summarize(event: RoomEvent) -> str:
    match event:
        case UserMessageAdded():
            return f"user: {event.text}"
        case ActivityChanged():
            return f"activity: {event.activity}" + (f" {event.tool_name}" if event.tool_name else "")
        case ReplyStarted():
            return "reply started"
        case ReplyDelta():
            return f"delta: {event.text}"
        case ReplyFinished():
            return "reply finished"
        case ToolCallStarted():
            return f"tool started: {event.tool_name}"
        case ToolCallFinished():
            return f"tool finished: {event.outcome}"
        case TurnFinished():
            return f"turn: {event.outcome}"
        case QueueChanged():
            return f"queue: {list(event.prompts)}"
        case DraftRestored():
            return f"draft: {event.text}"
        case AgendaChanged():
            return f"agenda: {[item.title for item in event.items]}"
        case StoryFilesChanged():
            return f"files: script={event.script} lore={event.lore}"
        case _:
            return event.type


def _story(tmp_path) -> FileStory:
    tmp_path.mkdir(exist_ok=True)
    return FileStory(tmp_path)


async def _open_room(story: FileStory, model: FunctionModel | None = None, *, recorder: Recorder | None = None, entry_limit: int = 40) -> StoryRoom:
    room = await StoryRoom.open(story=story, agent=create_writer_agent(), default_model_name=DEFAULT_MODEL, model=model, entry_limit=entry_limit)
    if recorder is not None:
        room.add_listener(recorder)
    return room


def _model(stream_function) -> FunctionModel:
    return FunctionModel(stream_function=stream_function)


async def _say_done(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
    yield "Done."


def _tool_call(name: str, json_args: str = "{}", call_id: str = "c1") -> DeltaToolCalls:
    return {0: DeltaToolCall(name=name, json_args=json_args, tool_call_id=call_id)}


def _has_tool_result(messages: list[ModelMessage]) -> bool:
    return any(isinstance(part, ToolReturnPart) for message in messages for part in message.parts)


def _user_prompts(messages: list[ModelMessage]) -> list[str]:
    texts = [visible_prompt_text(part.content) for message in messages if isinstance(message, ModelRequest) for part in message.parts if isinstance(part, UserPromptPart)]
    return [text for text in texts if text]


def _is_actionable(messages: list[ModelMessage]) -> bool:
    calls = {part.tool_call_id for message in messages if isinstance(message, ModelResponse) for part in message.parts if isinstance(part, ToolCallPart)}
    results = {part.tool_call_id for message in messages if isinstance(message, ModelRequest) for part in message.parts if isinstance(part, ToolReturnPart)}
    return calls == results


def _user_request(text: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=text)])


async def _say_once_and_hang(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
    yield "Starting"
    await asyncio.Event().wait()
    yield "never shown"


# Turns


@pytest.mark.asyncio
async def test_a_turn_tells_listeners_what_happens_in_order_and_saves_the_conversation(tmp_path) -> None:
    async def stream_response(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        yield "## Scene\n"
        yield "Done."

    story = _story(tmp_path)
    recorder = Recorder()
    room = await _open_room(story, _model(stream_response), recorder=recorder)

    await room.send_prompt("Continue.")
    await room.wait_until_idle()

    assert recorder.summary() == [
        "user: Continue.",
        "activity: thinking",
        "activity: writing",
        "reply started",
        "delta: ## Scene\n",
        "delta: Done.",
        "reply finished",
        "turn: completed",
        "activity: idle",
    ]
    reply_id = recorder.of(ReplyStarted)[0].reply_id
    assert {event.reply_id for event in recorder.of(ReplyDelta) + recorder.of(ReplyFinished)} == {reply_id}
    saved = await story.read_message_history()
    assert _user_prompts(saved) == ["Continue."]
    assert transcript_entries(saved) == [MessageEntry(role="user", text="Continue."), MessageEntry(role="writer", text="## Scene\nDone.")]
    assert not room.busy


@pytest.mark.asyncio
async def test_a_failed_turn_reports_its_error_and_returns_to_idle(tmp_path) -> None:
    async def explode(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        raise RuntimeError("provider down")
        yield ""

    recorder = Recorder()
    room = await _open_room(_story(tmp_path), _model(explode), recorder=recorder)

    await room.send_prompt("Continue.")
    await room.wait_until_idle()

    assert recorder.of(TurnFinished) == [TurnFinished(outcome="failed", error="provider down")]
    assert recorder.summary()[-1] == "activity: idle"
    assert not room.busy


@pytest.mark.asyncio
async def test_tool_calls_start_and_finish_with_their_result_and_outcome(tmp_path) -> None:
    async def stream_response(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        if _has_tool_result(messages):
            yield "Nothing there yet."
        else:
            yield _tool_call("list_lore")

    recorder = Recorder()
    room = await _open_room(_story(tmp_path), _model(stream_response), recorder=recorder)

    await room.send_prompt("What lore do we have?")
    await room.wait_until_idle()

    started, finished = recorder.of(ToolCallStarted)[0], recorder.of(ToolCallFinished)[0]
    assert (started.tool_name, started.arguments) == ("list_lore", "{}")
    assert (finished.tool_call_id, finished.outcome) == (started.tool_call_id, "success")
    assert "No lore files" in finished.result
    assert recorder.summary()[1:6] == ["activity: thinking", "activity: using_tool list_lore", "tool started: list_lore", "activity: thinking", "tool finished: success"]


@pytest.mark.asyncio
async def test_invalid_tool_arguments_finish_as_a_retry_without_ending_the_turn(tmp_path) -> None:
    async def stream_response(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        if any(part.part_kind == "retry-prompt" for message in messages for part in message.parts):
            yield "Recovered."
        else:
            yield _tool_call("edit_lore", '{"filename": "a.md", "action": "rewrite"}')

    recorder = Recorder()
    room = await _open_room(_story(tmp_path), _model(stream_response), recorder=recorder)

    await room.send_prompt("Fix the lore.")
    await room.wait_until_idle()

    assert [event.outcome for event in recorder.of(ToolCallFinished)] == ["retry"]
    assert recorder.of(TurnFinished) == [TurnFinished(outcome="completed")]
    assert recorder.of(StoryFilesChanged) == []


# Agenda and story files


@pytest.mark.asyncio
async def test_agenda_tools_tell_listeners_the_new_agenda(tmp_path) -> None:
    async def stream_response(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        if _has_tool_result(messages):
            yield "Done."
        else:
            yield _tool_call("set_agenda", '{"items": [{"title": "The city", "status": "working"}]}')

    story = _story(tmp_path)
    recorder = Recorder()
    room = await _open_room(story, _model(stream_response), recorder=recorder)

    await room.send_prompt("Plan the story.")
    await room.wait_until_idle()

    [changed] = recorder.of(AgendaChanged)
    assert [(item.title, item.status) for item in changed.items] == [("The city", "working")]
    assert room.snapshot().agenda == changed.items
    assert recorder.summary().index("tool finished: success") < recorder.summary().index("agenda: ['The city']")


@pytest.mark.asyncio
async def test_updating_an_agenda_item_tells_listeners_the_changed_agenda(tmp_path) -> None:
    story = _story(tmp_path)
    await story.write_agenda(items=[AgendaItem(id="a1", title="The city")])

    async def stream_response(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        if _has_tool_result(messages):
            yield "Done."
        else:
            yield _tool_call("update_agenda_item", '{"item_id": "a1", "status": "settled", "outcome": "Buffalo"}')

    recorder = Recorder()
    room = await _open_room(story, _model(stream_response), recorder=recorder)
    assert [item.status for item in room.snapshot().agenda] == ["open"]

    await room.send_prompt("Settle the city.")
    await room.wait_until_idle()

    [changed] = recorder.of(AgendaChanged)
    assert [(item.status, item.outcome) for item in changed.items] == [("settled", "Buffalo")]


@pytest.mark.parametrize(
    ("tool", "arguments", "expected"),
    [
        ("append_to_script", '{"text": "INT. ROOM"}', StoryFilesChanged(script=True, lore=False)),
        ("write_lore", json.dumps({"filename": "city.md", "content": LORE}), StoryFilesChanged(script=False, lore=True)),
    ],
)
@pytest.mark.asyncio
async def test_writing_tools_tell_listeners_which_story_files_changed(tmp_path, tool: str, arguments: str, expected: StoryFilesChanged) -> None:
    async def stream_response(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        if _has_tool_result(messages):
            yield "Done."
        else:
            yield _tool_call(tool, arguments)

    recorder = Recorder()
    room = await _open_room(_story(tmp_path), _model(stream_response), recorder=recorder)

    await room.send_prompt("Write something.")
    await room.wait_until_idle()

    assert recorder.of(StoryFilesChanged) == [expected]
    assert recorder.summary().index("tool finished: success") < recorder.summary().index(_summarize(expected))


@pytest.mark.asyncio
async def test_a_writing_tool_that_failed_changes_no_story_files(tmp_path) -> None:
    async def stream_response(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        if _has_tool_result(messages):
            yield "Done."
        else:
            yield _tool_call("edit_script", '{"find": "missing passage", "replace": "x"}')

    recorder = Recorder()
    room = await _open_room(_story(tmp_path), _model(stream_response), recorder=recorder)

    await room.send_prompt("Edit the script.")
    await room.wait_until_idle()

    assert [event.outcome for event in recorder.of(ToolCallFinished)] != ["success"]
    assert recorder.of(StoryFilesChanged) == []


@pytest.mark.asyncio
async def test_an_agenda_that_cannot_be_read_when_the_room_opens_is_reported_in_the_snapshot(tmp_path) -> None:
    story = _story(tmp_path)
    (tmp_path / AGENDA_FILENAME).write_text("not json", encoding="utf-8")

    snapshot = (await _open_room(story)).snapshot()

    assert snapshot.agenda == ()
    assert snapshot.agenda_error is not None and AGENDA_FILENAME in snapshot.agenda_error


@pytest.mark.asyncio
async def test_an_agenda_that_becomes_unreadable_produces_a_notice_and_an_empty_agenda(tmp_path) -> None:
    story = _story(tmp_path)
    await story.write_agenda(items=[AgendaItem(title="The city")])

    async def stream_response(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str]:
        (tmp_path / AGENDA_FILENAME).write_text("not json", encoding="utf-8")
        yield "Done."

    recorder = Recorder()
    room = await _open_room(story, _model(stream_response), recorder=recorder)
    assert len(room.snapshot().agenda) == 1

    await room.send_prompt("Continue.")
    await room.wait_until_idle()

    [notice] = recorder.of(Notice)
    assert notice.level == "error" and AGENDA_FILENAME in notice.text
    assert recorder.of(AgendaChanged) == [AgendaChanged(items=())]
    assert room.snapshot().agenda == () and room.snapshot().agenda_error == notice.text


# Steering queue


@pytest.mark.asyncio
async def test_prompts_sent_while_the_writer_works_are_queued_and_read_at_its_next_step(tmp_path) -> None:
    release = asyncio.Event()
    first_request = asyncio.Event()
    seen_prompts: list[list[str]] = []

    async def stream_response(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        seen_prompts.append(_user_prompts(messages))
        if len(seen_prompts) == 1:
            first_request.set()
            await release.wait()
            yield _tool_call("list_lore")
        else:
            yield "Added rain."

    recorder = Recorder()
    room = await _open_room(_story(tmp_path), _model(stream_response), recorder=recorder)

    await room.send_prompt("Write the opening.")
    await asyncio.wait_for(first_request.wait(), timeout=5)
    await room.send_prompt("Also make it rain.")

    assert recorder.summary() == ["user: Write the opening.", "activity: thinking", "queue: ['Also make it rain.']"]
    assert room.snapshot().queue == ("Also make it rain.",)

    release.set()
    await room.wait_until_idle()

    assert seen_prompts == [["Write the opening."], ["Write the opening.", "Also make it rain."]]
    summary = recorder.summary()
    assert summary[summary.index("tool finished: success") :][:3] == ["tool finished: success", "user: Also make it rain.", "queue: []"]
    assert summary[-2:] == ["turn: completed", "activity: idle"]
    assert room.snapshot().queue == ()


@pytest.mark.asyncio
async def test_a_prompt_that_arrives_too_late_for_the_writer_starts_a_follow_up_turn(tmp_path) -> None:
    seen_prompts: list[list[str]] = []

    async def stream_response(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str]:
        seen_prompts.append(_user_prompts(messages))
        yield f"Reply {len(seen_prompts)}."

    story = _story(tmp_path)
    recorder = Recorder()
    room = await _open_room(story, _model(stream_response), recorder=recorder)
    sent = False

    async def send_when_the_turn_is_over(event: RoomEvent) -> None:
        nonlocal sent
        if isinstance(event, TurnFinished) and not sent:
            sent = True
            await room.send_prompt("Second.")

    room.add_listener(send_when_the_turn_is_over)

    await room.send_prompt("First.")
    await room.wait_until_idle()

    summary = recorder.summary()
    assert summary.count("turn: completed") == 2
    assert summary[summary.index("turn: completed") :][:4] == ["turn: completed", "queue: ['Second.']", "queue: []", "user: Second."]
    assert summary[-2:] == ["turn: completed", "activity: idle"]
    assert summary.count("activity: idle") == 1
    assert seen_prompts == [["First."], ["First.", "Second."]]
    assert _user_prompts(await story.read_message_history()) == ["First.", "Second."]
    assert room.snapshot().queue == ()


@pytest.mark.asyncio
async def test_interrupting_hands_unread_prompts_back_as_a_draft(tmp_path) -> None:
    story = _story(tmp_path)
    recorder = Recorder()
    room = await _open_room(story, _model(_say_once_and_hang), recorder=recorder)

    await room.send_prompt("Write the opening.")
    await recorder.wait_for(ReplyDelta)
    await room.send_prompt("Make it rain.")
    await room.send_prompt("And snow.")
    room.interrupt()
    await room.wait_until_idle()

    assert recorder.of(TurnFinished) == [TurnFinished(outcome="interrupted")]
    assert recorder.of(DraftRestored) == [DraftRestored(text="Make it rain.\n\nAnd snow.")]
    assert recorder.of(QueueChanged)[-1] == QueueChanged(prompts=())
    assert recorder.summary()[-1] == "activity: idle"
    assert room.snapshot().queue == ()
    assert not room.busy


@pytest.mark.asyncio
async def test_an_interrupted_turn_keeps_an_actionable_history(tmp_path) -> None:
    async def stream_response(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        if any(isinstance(message, ModelResponse) for message in messages):
            await asyncio.Event().wait()
        yield _tool_call("list_lore")

    story = _story(tmp_path)
    recorder = Recorder()
    room = await _open_room(story, _model(stream_response), recorder=recorder)

    await room.send_prompt("Write the opening.")
    await recorder.wait_for(ToolCallFinished)
    await asyncio.sleep(0.05)
    room.interrupt()
    await room.wait_until_idle()

    saved = await story.read_message_history()
    assert recorder.of(TurnFinished) == [TurnFinished(outcome="interrupted")]
    assert _user_prompts(saved) == ["Write the opening."]
    assert _is_actionable(saved)
    assert room.snapshot().entries == tuple(transcript_entries(saved))


@pytest.mark.asyncio
async def test_a_prompt_sent_while_idle_is_announced_starts_a_follow_up_turn(tmp_path) -> None:
    story = _story(tmp_path)
    recorder = Recorder()
    room = await _open_room(story, _model(_say_done), recorder=recorder)
    late_prompt_sent = False

    async def send_late_prompt(event: RoomEvent) -> None:
        nonlocal late_prompt_sent
        if isinstance(event, ActivityChanged) and event.activity == "idle" and not late_prompt_sent:
            late_prompt_sent = True
            await room.send_prompt("Late.")

    room.add_listener(send_late_prompt)

    await room.send_prompt("Early.")
    await room.wait_until_idle()

    assert _user_prompts(await story.read_message_history()) == ["Early.", "Late."]
    assert recorder.summary().count("turn: completed") == 2
    assert recorder.summary()[-1] == "activity: idle"
    assert not room.busy


# Interrupt, undo and clear


@pytest.mark.asyncio
async def test_undoing_the_last_turn_replaces_the_conversation_and_restores_the_prompt(tmp_path) -> None:
    story = _story(tmp_path)
    recorder = Recorder()
    room = await _open_room(story, _model(_say_done), recorder=recorder)
    for prompt in ("First.", "Second."):
        await room.send_prompt(prompt)
        await room.wait_until_idle()
    recorder.events.clear()

    assert await room.undo_last_turn() is True

    assert [event.type for event in recorder.events] == ["conversation_replaced", "draft_restored"]
    [replaced] = recorder.of(ConversationReplaced)
    assert replaced.entries == (MessageEntry(role="user", text="First."), MessageEntry(role="writer", text="Done."))
    assert recorder.of(DraftRestored) == [DraftRestored(text="Second.")]
    assert _user_prompts(await story.read_message_history()) == ["First."]
    assert room.snapshot().entries == replaced.entries


@pytest.mark.asyncio
async def test_undo_with_nothing_to_remove_returns_false_and_tells_no_one(tmp_path) -> None:
    recorder = Recorder()
    room = await _open_room(_story(tmp_path), recorder=recorder)

    assert await room.undo_last_turn() is False
    assert recorder.events == []


@pytest.mark.asyncio
async def test_undo_and_clear_are_refused_while_the_writer_works(tmp_path) -> None:
    story = _story(tmp_path)
    await story.write_message_history(message_history=[_user_request("Old prompt.")])
    room = await _open_room(story, _model(_say_once_and_hang))
    recorder = Recorder()
    room.add_listener(recorder)

    await room.send_prompt("Write the opening.")
    await recorder.wait_for(ReplyDelta)

    with pytest.raises(RoomBusyError):
        await room.undo_last_turn()
    with pytest.raises(RoomBusyError):
        await room.clear_conversation()
    assert recorder.of(ConversationReplaced) == []

    room.interrupt()
    await room.wait_until_idle()
    await room.clear_conversation()


@pytest.mark.asyncio
async def test_clearing_starts_a_new_conversation(tmp_path) -> None:
    story = _story(tmp_path)
    await story.write_message_history(message_history=[_user_request("Old prompt.")])
    recorder = Recorder()
    room = await _open_room(story, recorder=recorder)

    await room.clear_conversation()

    assert recorder.events == [ConversationReplaced(entries=(), hidden_entries=0)]
    assert await story.read_message_history() == []
    assert room.snapshot().entries == ()


@pytest.mark.asyncio
async def test_a_replaced_conversation_counts_the_entries_it_leaves_out(tmp_path) -> None:
    story = _story(tmp_path)
    history: list[ModelMessage] = []
    for number in range(1, 4):
        history += [_user_request(f"Prompt {number}."), ModelResponse(parts=[TextPart(content=f"Reply {number}.")])]
    await story.write_message_history(message_history=history)
    recorder = Recorder()
    room = await _open_room(story, recorder=recorder, entry_limit=3)

    await room.undo_last_turn()

    [replaced] = recorder.of(ConversationReplaced)
    assert (len(replaced.entries), replaced.hidden_entries) == (3, 1)


# Model


@pytest.mark.asyncio
async def test_setting_the_model_tells_listeners_and_the_story_remembers_it(tmp_path) -> None:
    story = _story(tmp_path)
    recorder = Recorder()
    room = await _open_room(story, recorder=recorder)

    await room.set_model("openrouter:other/model")

    assert recorder.events == [ModelChanged(model_name="openrouter:other/model")]
    assert room.model_name == "openrouter:other/model"
    assert await story.read_model_name() == "openrouter:other/model"
    assert room.snapshot().model_name == "openrouter:other/model"


@pytest.mark.asyncio
async def test_a_turn_runs_on_the_model_set_for_it_and_the_story_remembers_it(tmp_path) -> None:
    story = _story(tmp_path)
    agent = create_writer_agent()
    room = await StoryRoom.open(story=story, agent=agent, default_model_name=DEFAULT_MODEL)

    with agent.override(model=_model(_say_done)):
        await room.send_prompt("Continue.")
        await room.wait_until_idle()

    assert await story.read_model_name() == DEFAULT_MODEL
    reopened = await StoryRoom.open(story=story, agent=agent, default_model_name="openrouter:another/default")
    assert (reopened.snapshot().model_name, reopened.snapshot().model_from_story) == (DEFAULT_MODEL, True)


# Snapshot


@pytest.mark.asyncio
async def test_a_snapshot_taken_mid_turn_contains_the_partial_reply_and_the_queue(tmp_path) -> None:
    release = asyncio.Event()

    async def stream_response(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        yield "Once upon"
        await release.wait()
        yield " a time."

    story = _story(tmp_path)
    recorder = Recorder()
    room = await _open_room(story, _model(stream_response), recorder=recorder)

    await room.send_prompt("Tell a tale.")
    await recorder.wait_for(ReplyDelta)
    await room.send_prompt("Make it short.")
    mid_turn = room.snapshot()

    [reply_id] = [event.reply_id for event in recorder.of(ReplyStarted)]
    assert mid_turn.entries == (MessageEntry(role="user", text="Tell a tale."), MessageEntry(role="writer", text="Once upon", reply_id=reply_id))
    assert (mid_turn.activity, mid_turn.queue) == ("writing", ("Make it short.",))

    release.set()
    await room.wait_until_idle()
    finished = room.snapshot()

    assert finished.entries[-1] == MessageEntry(role="writer", text="Once upon a time.")
    assert (finished.activity, finished.queue) == ("idle", ())


@pytest.mark.asyncio
async def test_a_snapshot_taken_while_a_tool_runs_contains_the_working_tool_call(tmp_path) -> None:
    async def stream_response(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        if _has_tool_result(messages):
            yield "Done."
        else:
            yield _tool_call("list_lore", call_id="call-1")

    snapshots: dict[str, RoomSnapshot] = {}
    room = await _open_room(_story(tmp_path), _model(stream_response))

    async def take_snapshot(event: RoomEvent) -> None:
        if isinstance(event, ToolCallStarted | ToolCallFinished):
            snapshots[event.type] = room.snapshot()

    room.add_listener(take_snapshot)

    await room.send_prompt("What lore do we have?")
    await room.wait_until_idle()

    working = snapshots["tool_call_started"]
    assert working.entries[-1] == ToolCallEntry(tool_call_id="call-1", tool_name="list_lore", arguments="{}", outcome="working")
    assert (working.activity, working.tool_name) == ("using_tool", "list_lore")
    done = snapshots["tool_call_finished"].entries[-1]
    assert isinstance(done, ToolCallEntry) and (done.outcome, done.result) == ("success", "No lore files found.")


@pytest.mark.asyncio
async def test_a_snapshot_after_a_turn_equals_what_a_freshly_opened_room_reports(tmp_path) -> None:
    async def stream_response(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        if _has_tool_result(messages):
            yield "Planned "
            yield "it."
        else:
            yield "Let me plan."
            yield _tool_call("set_agenda", '{"items": [{"title": "The city"}]}')

    story = _story(tmp_path)
    room = await _open_room(story, _model(stream_response))

    await room.send_prompt("Plan the story.")
    await room.wait_until_idle()
    after_turn = room.snapshot()
    fresh = (await _open_room(story)).snapshot()

    assert [entry.kind for entry in after_turn.entries] == ["message", "message", "tool_call", "message"]
    assert after_turn.entries == fresh.entries
    assert after_turn.agenda == fresh.agenda and len(fresh.agenda) == 1
    assert (after_turn.hidden_entries, after_turn.activity) == (0, "idle")


@pytest.mark.asyncio
async def test_a_snapshot_reports_how_many_entries_it_leaves_out(tmp_path) -> None:
    story = _story(tmp_path)
    history: list[ModelMessage] = []
    for number in range(1, 5):
        history += [_user_request(f"Prompt {number}."), ModelResponse(parts=[TextPart(content=f"Reply {number}.")])]
    await story.write_message_history(message_history=history)

    snapshot = (await _open_room(story, entry_limit=5)).snapshot()

    assert len(snapshot.entries) == 5
    assert snapshot.hidden_entries == 3
    assert snapshot.entries[-1] == MessageEntry(role="writer", text="Reply 4.")


@pytest.mark.asyncio
async def test_a_snapshot_reports_history_that_was_archived_when_the_story_opened(tmp_path) -> None:
    story = _story(tmp_path)
    (tmp_path / ".storyline-history.json").write_text("not json", encoding="utf-8")

    snapshot = (await _open_room(story)).snapshot()

    assert snapshot.entries == ()
    assert snapshot.archived_conversation is not None
    assert (tmp_path / snapshot.archived_conversation.archive_name).exists()


# Listeners and tasks


@pytest.mark.asyncio
async def test_a_listener_that_raises_does_not_break_the_turn_or_other_listeners(tmp_path) -> None:
    async def broken(_: RoomEvent) -> None:
        raise RuntimeError("listener bug")

    story = _story(tmp_path)
    recorder = Recorder()
    room = await _open_room(story, _model(_say_done))
    room.add_listener(broken)
    room.add_listener(recorder)

    await room.send_prompt("Continue.")
    await room.wait_until_idle()

    assert recorder.summary()[-2:] == ["turn: completed", "activity: idle"]
    assert _user_prompts(await story.read_message_history()) == ["Continue."]


@pytest.mark.asyncio
async def test_a_removed_listener_hears_nothing_more(tmp_path) -> None:
    recorder = Recorder()
    room = await _open_room(_story(tmp_path), _model(_say_done))
    remove = room.add_listener(recorder)

    await room.set_model("openrouter:one/model")
    remove()
    remove()
    await room.set_model("openrouter:two/model")

    assert recorder.events == [ModelChanged(model_name="openrouter:one/model")]


@pytest.mark.asyncio
async def test_turns_run_on_the_task_spawner_the_interface_supplies(tmp_path) -> None:
    tasks: list[asyncio.Task[None]] = []

    def spawn(coroutine: Coroutine[None, None, None]) -> asyncio.Task[None]:
        task = asyncio.get_running_loop().create_task(coroutine)
        tasks.append(task)
        return task

    story = _story(tmp_path)
    room = await StoryRoom.open(story=story, agent=create_writer_agent(), default_model_name=DEFAULT_MODEL, model=_model(_say_done), spawn=spawn)

    await room.send_prompt("Continue.")
    assert room.busy and len(tasks) == 1
    await room.wait_until_idle()

    assert tasks[0].done()
    assert _user_prompts(await story.read_message_history()) == ["Continue."]


@pytest.mark.asyncio
async def test_cancelling_the_task_that_runs_a_turn_leaves_the_room_idle_and_the_history_actionable(tmp_path) -> None:
    tasks: list[asyncio.Task[None]] = []

    def spawn(coroutine: Coroutine[None, None, None]) -> asyncio.Task[None]:
        task = asyncio.get_running_loop().create_task(coroutine)
        tasks.append(task)
        return task

    async def stream_response(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        if any(isinstance(message, ModelResponse) for message in messages):
            await asyncio.Event().wait()
        yield _tool_call("list_lore")

    story = _story(tmp_path)
    recorder = Recorder()
    room = await StoryRoom.open(story=story, agent=create_writer_agent(), default_model_name=DEFAULT_MODEL, model=_model(stream_response), spawn=spawn)
    room.add_listener(recorder)

    await room.send_prompt("Write the opening.")
    await room.send_prompt("Queued.")
    await recorder.wait_for(ToolCallFinished)
    await asyncio.sleep(0.05)
    tasks[0].cancel()
    with pytest.raises(asyncio.CancelledError):
        await tasks[0]
    await room.wait_until_idle()

    assert not room.busy
    snapshot = room.snapshot()
    assert (snapshot.activity, snapshot.queue) == ("idle", ())
    assert _is_actionable(await story.read_message_history())
    assert snapshot.entries[0] == MessageEntry(role="user", text="Write the opening.")


# Reading the story


@pytest.mark.asyncio
async def test_the_room_reads_the_script_and_lore_files(tmp_path) -> None:
    story = _story(tmp_path)
    await story.append_script(text="INT. ROOM")
    await story.write_lore(filename="city.md", content=LORE)
    room = await _open_room(story)

    assert "INT. ROOM" in await room.read_script()
    assert [(lore.filename, lore.summary) for lore in await room.list_lore()] == [("city.md", "The city.")]
    assert "Buffalo." in await room.read_lore("city.md")
