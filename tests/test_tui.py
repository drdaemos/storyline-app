"""Tests for the terminal UI."""

import asyncio
from collections.abc import AsyncIterator

import pytest
from pydantic_ai import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.messages import ModelMessage, RetryPromptPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel
from textual.widgets import Static

from storyline.agent import create_writer_agent, turn_prompt, visible_prompt_text
from storyline.tui.message_log import AgentReply, ChatMessage, MessageLog, ToolLogEntry
from storyline.tui.models import MessageKind, TuiConfig
from storyline.tui.prompt import PromptBlock
from storyline.tui.session import INTERRUPTED_NOTICE, StorylineTui
from storyline.tui.status_line import NEW_MESSAGES_STATUS, StatusLine
from storyline.workspace.file import CONVERSATION_HISTORY_FILENAME, FileWorkspace


@pytest.mark.asyncio
async def test_model_command_updates_the_active_model(tmp_path) -> None:
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/model openrouter:example/model")

        assert "openrouter:example/model" in app.query_one(PromptBlock).placeholder
        assert "Model set to: openrouter:example/model" in _bodies(app, MessageKind.SYSTEM)


@pytest.mark.asyncio
async def test_unknown_command_is_reported(tmp_path) -> None:
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/nope now")

        assert any("Unknown command: /nope" in body for body in _bodies(app, MessageKind.ERROR))


@pytest.mark.asyncio
async def test_help_lists_every_command(tmp_path) -> None:
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/help")

        help_text = _bodies(app, MessageKind.SYSTEM)[-1]
        for name in ("/help", "/model", "/script", "/lore", "/clear", "/quit"):
            assert name in help_text


@pytest.mark.asyncio
async def test_script_and_lore_commands_show_the_workspace(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    await workspace.append_script(text="INT. ROOM")
    await workspace.write_lore(filename="city.md", content="---\nsummary: The city.\nkeywords: city\n---\n")
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/script")
        await _submit(pilot, app, "/lore")

        script_text, lore_text = _bodies(app, MessageKind.SYSTEM)[-2:]
        assert "INT. ROOM" in script_text
        assert "city.md" in lore_text and "The city." in lore_text


@pytest.mark.asyncio
async def test_clear_command_starts_a_new_conversation(tmp_path) -> None:
    await FileWorkspace(tmp_path).write_message_history(message_history=[_user_request("Old prompt.")])
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/clear")

        assert _bodies(app, MessageKind.USER) == []
        assert await FileWorkspace(tmp_path).read_message_history() == []


@pytest.mark.asyncio
async def test_quit_command_exits(tmp_path) -> None:
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/quit")

    assert app.return_code == 0


@pytest.mark.asyncio
async def test_slash_opens_the_command_list_and_tab_completes(tmp_path) -> None:
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        prompt = app.query_one(PromptBlock)
        prompt.value = "/"
        await pilot.pause()
        assert prompt.command_count == 6

        prompt.value = "/mo"
        await pilot.pause()
        await pilot.press("tab")
        await pilot.pause()

        assert prompt.value == "/model "
        assert prompt.cursor_position == len(prompt.value)


@pytest.mark.asyncio
async def test_shift_enter_inserts_a_line_break_without_submitting(tmp_path) -> None:
    app = _build_submission_app(tmp_path)

    async with app.run_test() as pilot:
        prompt = app.query_one(PromptBlock)
        prompt.value = "First line"
        prompt.focus_input()
        await pilot.press("shift+enter")
        await pilot.pause()

        assert prompt.value == "First line\n"
        assert app.submitted_prompts == []

        prompt.value = "First line\nSecond line"
        await pilot.press("enter")
        await pilot.pause()

        assert app.submitted_prompts == ["First line\nSecond line"]


@pytest.mark.asyncio
async def test_restored_history_is_shown_on_startup(tmp_path) -> None:
    history: list[ModelMessage] = [
        _user_request("Add an opening."),
        ModelResponse(parts=[ToolCallPart(tool_name="edit_script", args={"replacement": "FADE IN:"}, tool_call_id="c1")]),
        ModelRequest(parts=[ToolReturnPart(tool_name="edit_script", content="Updated.", tool_call_id="c1")]),
        ModelResponse(parts=[TextPart(content="Added an **opening**.")]),
    ]
    await FileWorkspace(tmp_path).write_message_history(message_history=history)
    app = _build_app(tmp_path)

    async with app.run_test():
        assert app._state.message_history == history
        assert _bodies(app, MessageKind.USER) == ["Add an opening."]
        assert [entry.title for entry in app.query(ToolLogEntry)] == ["edit_script · success"]
        assert [reply.body for reply in app.query(AgentReply)] == ["Added an **opening**."]


@pytest.mark.asyncio
async def test_restored_prompts_hide_the_story_snapshot(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    await workspace.append_script(text="Secret opening.")
    prompt = await turn_prompt(workspace, "Continue.")
    await workspace.write_message_history(message_history=[ModelRequest(parts=[UserPromptPart(content=prompt)])])
    app = _build_app(tmp_path)

    async with app.run_test():
        assert _bodies(app, MessageKind.USER) == ["Continue."]


@pytest.mark.asyncio
async def test_unreadable_history_is_archived_and_reported(tmp_path) -> None:
    (tmp_path / CONVERSATION_HISTORY_FILENAME).write_text("not json", encoding="utf-8")
    app = _build_app(tmp_path)

    async with app.run_test():
        assert app._state.message_history == []
        assert any("started a new conversation" in body for body in _bodies(app, MessageKind.ERROR))
        assert not (tmp_path / CONVERSATION_HISTORY_FILENAME).exists()
        assert len(list(tmp_path.glob("*.broken.json"))) == 1


@pytest.mark.asyncio
async def test_message_log_pauses_auto_scroll_and_marks_unseen_messages(tmp_path) -> None:
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        messages = app.query_one(MessageLog)
        status = app.query_one(StatusLine)
        for index in range(100):
            await messages.add_message(MessageKind.SYSTEM, f"Message {index}")
        await pilot.pause()
        messages.scroll_home(animate=False)
        await pilot.pause()

        assert not messages.is_vertical_scroll_end

        await messages.add_message(MessageKind.SYSTEM, "Newest message")
        await pilot.pause()

        assert not messages.is_vertical_scroll_end
        assert NEW_MESSAGES_STATUS in str(status.render())

        messages.scroll_end(animate=False)
        await pilot.pause()

        assert NEW_MESSAGES_STATUS not in str(status.render())


@pytest.mark.asyncio
async def test_tool_call_and_result_share_one_expandable_log_entry(tmp_path) -> None:
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        messages = app.query_one(MessageLog)
        entry = await messages.add_tool_call(
            tool_call_id="call-123",
            tool_name="edit_script",
            arguments='{"replacement": "[bold]FADE IN:[/bold]"}',
        )
        messages.complete_tool_call(tool_call_id="call-123", result="Updated 8 characters.", outcome="success")

        assert len(messages.query(ToolLogEntry)) == 1
        assert entry.title == "edit_script · success"
        assert entry.collapsed

        entry.collapsed = False
        await pilot.pause()

        details = str(entry.query_one(".tool-details", Static).render())
        assert "[bold]FADE IN:[/bold]" in details
        assert "Updated 8 characters." in details


@pytest.mark.asyncio
async def test_agent_turn_streams_a_markdown_reply_and_persists_history(tmp_path) -> None:
    async def stream_response(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        yield "## Scene\n"
        yield "Done."

    app = _build_app(tmp_path)
    with app._config.agent.override(model=FunctionModel(stream_function=stream_response)):
        async with app.run_test() as pilot:
            await _submit(pilot, app, "Continue.")
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert [reply.body for reply in app.query(AgentReply)] == ["## Scene\nDone."]
            assert await FileWorkspace(tmp_path).read_message_history() == app._state.message_history
            assert len(app._state.message_history) == 2


@pytest.mark.asyncio
async def test_invalid_tool_arguments_are_retried_without_ending_the_turn(tmp_path) -> None:
    async def stream_response(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        if any(isinstance(part, RetryPromptPart) for message in messages for part in message.parts):
            yield "Recovered."
            return
        yield {0: DeltaToolCall(name="edit_lore", json_args='{"filename": "a.md", "action": "rewrite"}', tool_call_id="c1")}

    app = _build_app(tmp_path)
    with app._config.agent.override(model=FunctionModel(stream_function=stream_response)):
        async with app.run_test() as pilot:
            await _submit(pilot, app, "Fix the lore.")
            await app.workers.wait_for_complete()

            assert [entry.title for entry in app.query(ToolLogEntry)] == ["edit_lore · retry"]
            assert _bodies(app, MessageKind.ERROR) == []
            assert [reply.body for reply in app.query(AgentReply)] == ["Recovered."]


@pytest.mark.asyncio
async def test_prompts_sent_while_the_agent_works_reach_it_at_the_next_step(tmp_path) -> None:
    release_first_step = asyncio.Event()
    seen_prompts: list[list[str]] = []

    async def stream_response(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        seen_prompts.append(_user_prompts(messages))
        if len(seen_prompts) == 1:
            await release_first_step.wait()
            yield {0: DeltaToolCall(name="list_lore", json_args="{}", tool_call_id="c1")}
        else:
            yield "Added rain."

    app = _build_app(tmp_path)
    with app._config.agent.override(model=FunctionModel(stream_function=stream_response)):
        async with app.run_test() as pilot:
            prompt = app.query_one(PromptBlock)
            await _submit(pilot, app, "Write the opening.")
            await _submit(pilot, app, "Also make it rain.")

            assert prompt.queued == ("Also make it rain.",)
            assert _bodies(app, MessageKind.USER) == ["Write the opening."]

            release_first_step.set()
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert seen_prompts == [["Write the opening."], ["Write the opening.", "Also make it rain."]]
            assert prompt.queued == ()
            assert _bodies(app, MessageKind.USER) == ["Write the opening.", "Also make it rain."]
            assert len(seen_prompts) == 2


@pytest.mark.asyncio
async def test_escape_interrupts_the_agent_and_returns_unread_prompts_to_the_input(tmp_path) -> None:
    never = asyncio.Event()

    async def stream_response(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        yield "Starting"
        await never.wait()
        yield "never shown"

    app = _build_app(tmp_path)
    with app._config.agent.override(model=FunctionModel(stream_function=stream_response)):
        async with app.run_test() as pilot:
            prompt = app.query_one(PromptBlock)
            await _submit(pilot, app, "Write the opening.")
            await _submit(pilot, app, "Make it rain.")
            await pilot.press("escape")
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert INTERRUPTED_NOTICE in _bodies(app, MessageKind.SYSTEM)
            assert prompt.value == "Make it rain."
            assert prompt.queued == ()
            saved = await FileWorkspace(tmp_path).read_message_history()
            assert _user_prompts(saved) == ["Write the opening."]


async def _submit(pilot, app: StorylineTui, text: str) -> None:
    app.query_one(PromptBlock).value = text
    await pilot.press("enter")
    await pilot.pause()


def _bodies(app: StorylineTui, kind: MessageKind) -> list[str]:
    return [message.body for message in app.query(ChatMessage) if message.kind == kind]


def _user_request(text: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=text)])


def _user_prompts(messages: list[ModelMessage]) -> list[str]:
    texts = [
        visible_prompt_text(part.content)
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, UserPromptPart)
    ]
    return [text for text in texts if text]


def _build_app(workspace_path) -> StorylineTui:
    workspace = FileWorkspace(workspace_path)
    config = TuiConfig(workspace=workspace, agent=create_writer_agent())
    return StorylineTui(config)


class SubmissionRecordingTui(StorylineTui):
    """A terminal app that records submitted prompts without starting an agent run."""

    def __init__(self, config: TuiConfig) -> None:
        super().__init__(config)
        self.submitted_prompts: list[str] = []

    async def on_prompt_block_submitted(self, message: PromptBlock.Submitted) -> None:
        self.submitted_prompts.append(message.value)


def _build_submission_app(workspace_path) -> SubmissionRecordingTui:
    workspace = FileWorkspace(workspace_path)
    config = TuiConfig(workspace=workspace, agent=create_writer_agent())
    return SubmissionRecordingTui(config)
