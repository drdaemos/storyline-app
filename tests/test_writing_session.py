"""Tests for a story's conversation with the writer, driven by scripted models."""

import asyncio
from collections.abc import AsyncIterator

import pytest
from pydantic_ai import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.messages import ModelMessage, UserPromptPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel

from storyline.agent import PromptDelivered, TurnOutcome, WritingSession, WritingTurn, create_writer_agent, visible_prompt_text
from storyline.workspace.file_story import CONVERSATION_HISTORY_FILENAME, FileStory

DEFAULT_MODEL = "openrouter:default/model"


def _story(tmp_path) -> FileStory:
    tmp_path.mkdir(exist_ok=True)
    return FileStory(tmp_path)


def _user_request(text: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=text)])


def _user_prompts(messages: list[ModelMessage]) -> list[str]:
    texts = [visible_prompt_text(part.content) for message in messages if isinstance(message, ModelRequest) for part in message.parts if isinstance(part, UserPromptPart)]
    return [text for text in texts if text]


def _is_actionable(messages: list[ModelMessage]) -> bool:
    calls = {part.tool_call_id for message in messages if isinstance(message, ModelResponse) for part in message.parts if isinstance(part, ToolCallPart)}
    results = {part.tool_call_id for message in messages if isinstance(message, ModelRequest) for part in message.parts if isinstance(part, ToolReturnPart)}
    return calls == results


async def _say_done(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
    yield "Done."


async def _open(story: FileStory) -> WritingSession:
    return await WritingSession.open(story=story, agent=create_writer_agent(), default_model_name=DEFAULT_MODEL)


async def _consume(turn: WritingTurn) -> None:
    async for _ in turn.events():
        pass


def _blocks_after_a_tool_call(started: asyncio.Event):
    """A model that calls a tool, then waits forever for its next step."""
    never = asyncio.Event()

    async def stream_response(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        if any(isinstance(message, ModelResponse) for message in messages):
            started.set()
            await never.wait()
        yield {0: DeltaToolCall(name="list_lore", json_args="{}", tool_call_id="c1")}

    return FunctionModel(stream_function=stream_response)


@pytest.mark.asyncio
async def test_a_turn_saves_the_conversation_and_remembers_the_model(tmp_path) -> None:
    story = _story(tmp_path)
    agent = create_writer_agent()
    session = await WritingSession.open(story=story, agent=agent, default_model_name=DEFAULT_MODEL)
    with agent.override(model=FunctionModel(stream_function=_say_done)):
        turn = session.turn("Continue.")
        await _consume(turn)

    assert turn.outcome is TurnOutcome.COMPLETED
    assert turn.reply == "Done."
    assert turn.usage.requests == 1
    assert await story.read_message_history() == session.message_history
    assert len(session.message_history) == 2
    assert await story.read_model_name() == DEFAULT_MODEL


@pytest.mark.asyncio
async def test_a_failed_turn_reports_its_error(tmp_path) -> None:
    agent = create_writer_agent()
    session = await WritingSession.open(story=_story(tmp_path), agent=agent, default_model_name=DEFAULT_MODEL)

    async def explode(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        raise RuntimeError("provider down")
        yield ""

    with agent.override(model=FunctionModel(stream_function=explode)):
        turn = session.turn("Continue.")
        await _consume(turn)

    assert turn.outcome is TurnOutcome.FAILED
    assert str(turn.error) == "provider down"


@pytest.mark.asyncio
async def test_a_failed_turn_keeps_the_users_message_in_an_actionable_history(tmp_path) -> None:
    story = _story(tmp_path)
    agent = create_writer_agent()
    session = await WritingSession.open(story=story, agent=agent, default_model_name=DEFAULT_MODEL)

    async def explode(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        raise RuntimeError("provider down")
        yield ""

    with agent.override(model=FunctionModel(stream_function=explode)):
        turn = session.turn("Set up the agenda.")
        await _consume(turn)

    saved = await story.read_message_history()
    assert turn.outcome is TurnOutcome.FAILED
    assert _user_prompts(saved) == ["Set up the agenda."]
    assert _is_actionable(saved)
    assert session.message_history == saved


@pytest.mark.asyncio
async def test_open_repairs_a_history_with_an_unanswered_tool_call_and_writes_it_back(tmp_path) -> None:
    story = _story(tmp_path)
    await story.write_message_history(
        message_history=[
            _user_request("Try again."),
            ModelResponse(parts=[TextPart(content="Loading."), ToolCallPart(tool_name="load_capability", args={}, tool_call_id="c1")]),
        ]
    )

    session = await _open(story)

    for messages in (session.message_history, await story.read_message_history()):
        assert not any(isinstance(part, ToolCallPart) for message in messages for part in message.parts)
        assert len(messages) == 2


@pytest.mark.asyncio
async def test_unreadable_history_is_archived_and_reported(tmp_path) -> None:
    story = _story(tmp_path)
    (tmp_path / CONVERSATION_HISTORY_FILENAME).write_text("not json", encoding="utf-8")

    session = await _open(story)

    assert session.message_history == []
    assert session.archived_history is not None
    assert (tmp_path / session.archived_history.archive_name).exists()
    assert not (tmp_path / CONVERSATION_HISTORY_FILENAME).exists()


@pytest.mark.asyncio
async def test_the_model_remembered_in_the_story_wins_over_the_default(tmp_path) -> None:
    story = _story(tmp_path)
    fresh = await _open(story)
    assert (fresh.model_name, fresh.model_from_story) == (DEFAULT_MODEL, False)

    await story.write_model_name(model_name="openrouter:story/model")
    remembered = await _open(story)

    assert (remembered.model_name, remembered.model_from_story) == ("openrouter:story/model", True)


@pytest.mark.asyncio
async def test_set_model_is_remembered_in_the_story(tmp_path) -> None:
    story = _story(tmp_path)
    session = await _open(story)

    await session.set_model("openrouter:other/model")

    assert session.model_name == "openrouter:other/model"
    assert await story.read_model_name() == "openrouter:other/model"


@pytest.mark.asyncio
async def test_clear_starts_a_new_conversation(tmp_path) -> None:
    story = _story(tmp_path)
    agent = create_writer_agent()
    session = await WritingSession.open(story=story, agent=agent, default_model_name=DEFAULT_MODEL)
    with agent.override(model=FunctionModel(stream_function=_say_done)):
        await _consume(session.turn("Continue."))
    assert session.message_history

    await session.clear()

    assert session.message_history == []
    assert await story.read_message_history() == []


@pytest.mark.asyncio
async def test_cancelling_a_turn_leaves_an_actionable_history_and_reports_it_interrupted(tmp_path) -> None:
    story = _story(tmp_path)
    agent = create_writer_agent()
    session = await WritingSession.open(story=story, agent=agent, default_model_name=DEFAULT_MODEL)
    started = asyncio.Event()

    with agent.override(model=_blocks_after_a_tool_call(started)):
        turn = session.turn("Write the opening.")
        task = asyncio.create_task(_consume(turn))
        await started.wait()
        turn.cancel()
        await task

    assert turn.outcome is TurnOutcome.INTERRUPTED
    saved = await story.read_message_history()
    assert _user_prompts(saved) == ["Write the opening."]
    assert _is_actionable(saved)
    assert session.message_history == saved


@pytest.mark.asyncio
async def test_cancelling_the_task_running_a_turn_still_saves_an_actionable_history(tmp_path) -> None:
    story = _story(tmp_path)
    agent = create_writer_agent()
    session = await WritingSession.open(story=story, agent=agent, default_model_name=DEFAULT_MODEL)
    started = asyncio.Event()

    with agent.override(model=_blocks_after_a_tool_call(started)):
        turn = session.turn("Write the opening.")
        task = asyncio.create_task(_consume(turn))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert turn.outcome is TurnOutcome.INTERRUPTED
    saved = await story.read_message_history()
    assert _user_prompts(saved) == ["Write the opening."]
    assert _is_actionable(saved)


@pytest.mark.asyncio
async def test_prompts_enqueued_before_the_run_starts_are_delivered(tmp_path) -> None:
    agent = create_writer_agent()
    session = await WritingSession.open(story=_story(tmp_path), agent=agent, default_model_name=DEFAULT_MODEL)
    seen: list[list[str]] = []

    async def stream_response(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        seen.append(_user_prompts(messages))
        if len(seen) == 1:
            yield {0: DeltaToolCall(name="list_lore", json_args="{}", tool_call_id="c1")}
        else:
            yield "Added rain."

    with agent.override(model=FunctionModel(stream_function=stream_response)):
        turn = session.turn("Write the opening.")
        enqueue_id = turn.enqueue("Also make it rain.")
        events = [event async for event in turn.events()]

    assert [event.enqueue_id for event in events if isinstance(event, PromptDelivered)] == [enqueue_id]
    assert "Also make it rain." in seen[-1]
    assert turn.undelivered_prompts == ()
    assert turn.outcome is TurnOutcome.COMPLETED


@pytest.mark.asyncio
async def test_prompts_the_agent_never_read_are_reported_in_order(tmp_path) -> None:
    agent = create_writer_agent()
    session = await WritingSession.open(story=_story(tmp_path), agent=agent, default_model_name=DEFAULT_MODEL)
    started = asyncio.Event()

    with agent.override(model=_blocks_after_a_tool_call(started)):
        turn = session.turn("Write the opening.")
        task = asyncio.create_task(_consume(turn))
        await started.wait()
        turn.cancel()
        turn.enqueue("First.")
        turn.enqueue("Second.")
        await task

    assert turn.outcome is TurnOutcome.INTERRUPTED
    assert turn.undelivered_prompts == ("First.", "Second.")


@pytest.mark.asyncio
async def test_undoing_the_last_turn_saves_the_shorter_conversation_and_returns_the_prompt(tmp_path) -> None:
    story = _story(tmp_path)
    agent = create_writer_agent()
    session = await WritingSession.open(story=story, agent=agent, default_model_name=DEFAULT_MODEL)
    with agent.override(model=FunctionModel(stream_function=_say_done)):
        for prompt in ("First.", "Second."):
            await _consume(session.turn(prompt))

    assert await session.undo_last_turn() == "Second."
    assert _user_prompts(await story.read_message_history()) == ["First."]
    assert _user_prompts(session.message_history) == ["First."]

    assert await session.undo_last_turn() == "First."
    assert await session.undo_last_turn() is None
