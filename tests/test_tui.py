"""Tests for the terminal UI."""

from collections.abc import AsyncIterator

import pytest
from pydantic_ai import ModelRequest
from pydantic_ai.messages import ModelMessage, RetryPromptPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel
from rich.markdown import Markdown
from textual.widgets import Static

from storyline.agent import create_writer_agent
from storyline.tui.message_log import ChatMessage, MessageLog, ToolLogEntry
from storyline.tui.models import MessageKind, TuiConfig
from storyline.tui.prompt import PromptBlock
from storyline.tui.session import StorylineTui
from storyline.tui.status_line import NEW_MESSAGES_STATUS, StatusLine
from storyline.workspace.file import FileWorkspace


@pytest.mark.asyncio
async def test_model_command_updates_the_active_model(tmp_path) -> None:
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        prompt = app.query_one(PromptBlock)
        prompt.value = "/model openrouter:example/model"
        await pilot.press("enter")
        await pilot.pause()

        assert "openrouter:example/model" in prompt.placeholder
        assert any("Model set to: openrouter:example/model" in message.body for message in app.query(ChatMessage))


@pytest.mark.asyncio
async def test_unknown_command_is_reported(tmp_path) -> None:
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        app.query_one(PromptBlock).value = "/nope now"
        await pilot.press("enter")
        await pilot.pause()

        errors = [message.body for message in app.query(ChatMessage) if message.kind == MessageKind.ERROR]
        assert errors == ["Unknown command: /nope"]


@pytest.mark.asyncio
async def test_slash_opens_the_command_list_and_tab_completes(tmp_path) -> None:
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        prompt = app.query_one(PromptBlock)
        prompt.value = "/"
        await pilot.pause()

        assert prompt.command_count == 1
        await pilot.press("tab")
        await pilot.pause()

        assert prompt.value == "/model "
        assert prompt.cursor_position == len(prompt.value)


@pytest.mark.asyncio
async def test_agent_messages_render_as_markdown(tmp_path) -> None:
    app = _build_app(tmp_path)

    async with app.run_test():
        message = await app.query_one(MessageLog).add_message(MessageKind.AGENT, "## Scene")

        assert isinstance(message.content, Markdown)


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
async def test_tui_restores_persisted_history_on_startup(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    history = [ModelRequest(parts=[UserPromptPart(content="Continue the scene.")])]
    await workspace.write_message_history(message_history=history)
    app = _build_app(tmp_path)

    async with app.run_test():
        assert app._state.message_history == history


@pytest.mark.asyncio
async def test_message_log_pauses_auto_scroll_and_marks_unseen_messages(tmp_path) -> None:
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        messages = app.query_one(MessageLog)
        status = app.query_one(StatusLine)
        for index in range(100):
            await messages.add_message(MessageKind.AGENT, f"Message {index}")
        messages.scroll_home(animate=False)
        await pilot.pause()

        assert not messages.is_vertical_scroll_end

        await messages.add_message(MessageKind.AGENT, "Newest message")
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
        messages.complete_tool_call(tool_call_id="call-123", content="Updated 8 characters.", outcome="success")

        assert len(messages.query(ToolLogEntry)) == 1
        assert entry.title == "edit_script · success"
        assert entry.collapsed

        entry.collapsed = False
        await pilot.pause()

        details = str(entry.query_one(".tool-details", Static).render())
        assert "[bold]FADE IN:[/bold]" in details
        assert "Updated 8 characters." in details


@pytest.mark.asyncio
async def test_agent_turn_streams_a_reply_and_persists_history(tmp_path) -> None:
    app = _build_app(tmp_path)

    async def stream_response(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        yield "Done"
        yield "."

    async with app.run_test():
        with app._config.agent.override(model=FunctionModel(stream_function=stream_response)):
            await app._run_turn("Continue.")

        replies = [message.body for message in app.query(ChatMessage) if message.kind == MessageKind.AGENT]
        assert replies == ["Done."]
        assert await FileWorkspace(tmp_path).read_message_history() == app._state.message_history
        assert app._state.message_history


@pytest.mark.asyncio
async def test_invalid_tool_arguments_are_retried_without_ending_the_turn(tmp_path) -> None:
    app = _build_app(tmp_path)

    async def stream_response(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        already_retried = any(isinstance(part, RetryPromptPart) for message in messages for part in message.parts)
        if already_retried:
            yield "Recovered."
            return
        yield {0: DeltaToolCall(name="edit_lore", json_args='{"filename": "a.md", "action": "rewrite"}', tool_call_id="c1")}

    async with app.run_test():
        with app._config.agent.override(model=FunctionModel(stream_function=stream_response)):
            await app._run_turn("Fix the lore.")

        assert [entry.title for entry in app.query(ToolLogEntry)] == ["edit_lore · retry"]
        assert not [message for message in app.query(ChatMessage) if message.kind == MessageKind.ERROR]
        assert [message.body for message in app.query(ChatMessage)][-1] == "Recovered."


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
