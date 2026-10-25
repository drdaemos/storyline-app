"""Tests for the terminal UI."""

import asyncio
from collections.abc import AsyncIterator

import pydantic_ai
import pytest
from pydantic_ai import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.messages import ModelMessage, RetryPromptPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel
from textual.widgets import Static

from storyline.agent import create_writer_agent, turn_prompt, visible_prompt_text
from storyline.registry import MECHANICS
from storyline.tui.message_log import ActivityLine, AgentReply, ChatMessage, MessageLog, ToolLogEntry
from storyline.tui.models import MessageKind, TuiConfig
from storyline.tui.prompt import PromptBlock
from storyline.tui.session import INTERRUPTED_NOTICE, StorylineTui
from storyline.tui.status_line import NEW_MESSAGES_STATUS, StatusLine
from storyline.workspace import StoryLibrary
from storyline.workspace.file_story import CONVERSATION_HISTORY_FILENAME, SETUP_FILENAME, FileStory
from storyline.workspace.file_workspace import FileWorkspace

STORY_NAME = "noir"


@pytest.mark.asyncio
async def test_model_command_updates_the_active_model(tmp_path) -> None:
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/model openrouter:example/model")

        assert "openrouter:example/model" in app.query_one(PromptBlock).placeholder
        assert "Model set to: openrouter:example/model" in _bodies(app, MessageKind.SYSTEM)


@pytest.mark.asyncio
async def test_model_command_refuses_a_name_no_turn_could_run_on(tmp_path) -> None:
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        before = app._state.model_name
        await _submit(pilot, app, "/model not-a-valid-model")

        assert any("not-a-valid-model" in body for body in _bodies(app, MessageKind.ERROR))
        assert app._state.model_name == before


@pytest.mark.asyncio
async def test_unknown_command_is_reported(tmp_path) -> None:
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/nope now")

        assert any("Unknown command: /nope" in body for body in _bodies(app, MessageKind.ERROR))


@pytest.mark.asyncio
async def test_a_story_that_cannot_be_opened_is_reported_instead_of_opened(tmp_path) -> None:
    (tmp_path / STORY_NAME).mkdir()
    (tmp_path / STORY_NAME / SETUP_FILENAME).write_text('{"preset": "no-such-preset"}', encoding="utf-8")
    app = StorylineTui(_config(tmp_path))

    async with app.run_test() as pilot:
        await pilot.pause()

        assert any(STORY_NAME in body and "no-such-preset" in body for body in _bodies(app, MessageKind.ERROR))
        assert app._state.room is None


@pytest.mark.asyncio
async def test_help_lists_every_command(tmp_path) -> None:
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/help")

        help_text = _bodies(app, MessageKind.SYSTEM)[-1]
        for name in ("/help", "/model", "/stories", "/story", "/new", "/script", "/lore", "/undo", "/clear", "/quit"):
            assert name in help_text


@pytest.mark.asyncio
async def test_script_and_lore_commands_show_the_active_story(tmp_path) -> None:
    story = _story(tmp_path)
    await story.append_script(text="INT. ROOM")
    await story.write_lore(filename="city.md", content="---\nsummary: The city.\nkeywords: city\n---\n")
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/script")
        await _submit(pilot, app, "/lore")

        script_text, lore_text = _bodies(app, MessageKind.SYSTEM)[-2:]
        assert "INT. ROOM" in script_text
        assert "city.md" in lore_text and "The city." in lore_text


@pytest.mark.asyncio
async def test_lore_command_with_a_filename_shows_that_file_or_explains_why_not(tmp_path) -> None:
    await _story(tmp_path).write_lore(filename="city.md", content="---\nsummary: The city.\nkeywords: city\n---\nBuffalo, 1970s.\n")
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/lore city.md")
        await _submit(pilot, app, "/lore missing.md")

        assert "Buffalo, 1970s." in _bodies(app, MessageKind.SYSTEM)[-1]
        assert len(_bodies(app, MessageKind.ERROR)) == 1
        assert "missing.md" in _bodies(app, MessageKind.ERROR)[0]


@pytest.mark.asyncio
async def test_clear_command_starts_a_new_conversation(tmp_path) -> None:
    await _story(tmp_path).write_message_history(message_history=[_user_request("Old prompt.")])
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/clear")

        assert _bodies(app, MessageKind.USER) == []
        assert await _story(tmp_path).read_message_history() == []


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
        assert prompt.command_count == 12

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
    await _story(tmp_path).write_message_history(message_history=history)
    app = _build_app(tmp_path)

    async with app.run_test():
        assert await _story(tmp_path).read_message_history() == history
        assert _bodies(app, MessageKind.USER) == ["Add an opening."]
        assert [entry.title for entry in app.query(ToolLogEntry)] == ["edit_script · success"]
        assert [reply.body for reply in app.query(AgentReply)] == ["Added an **opening**."]


@pytest.mark.asyncio
async def test_restored_prompts_hide_the_story_snapshot(tmp_path, registry=MECHANICS) -> None:
    story = _story(tmp_path)
    await story.append_script(text="Secret opening.")
    prompt = await turn_prompt(story, "Continue.", registry=MECHANICS)
    await story.write_message_history(message_history=[ModelRequest(parts=[UserPromptPart(content=prompt)])])
    app = _build_app(tmp_path)

    async with app.run_test():
        assert _bodies(app, MessageKind.USER) == ["Continue."]


@pytest.mark.asyncio
async def test_unreadable_history_is_archived_and_reported(tmp_path) -> None:
    app = _build_app(tmp_path)
    (tmp_path / STORY_NAME / CONVERSATION_HISTORY_FILENAME).write_text("not json", encoding="utf-8")

    async with app.run_test():
        assert await _story(tmp_path).read_message_history() == []
        assert any("started a new conversation" in body for body in _bodies(app, MessageKind.ERROR))
        assert not (tmp_path / STORY_NAME / CONVERSATION_HISTORY_FILENAME).exists()
        assert len(list((tmp_path / STORY_NAME).glob("*.broken.json"))) == 1


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
            assert len(await _story(tmp_path).read_message_history()) == 2


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
async def test_agent_activity_is_shown_as_the_last_log_entry_while_it_works(tmp_path) -> None:
    release = asyncio.Event()

    async def stream_response(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        yield "Starting"
        await release.wait()
        yield " the scene."

    app = _build_app(tmp_path)
    with app._config.agent.override(model=FunctionModel(stream_function=stream_response)):
        async with app.run_test() as pilot:
            await _submit(pilot, app, "Write the opening.")
            await pilot.pause()

            log = app.query_one(MessageLog)
            activity = app.query_one(ActivityLine)
            assert log.children[-1] is activity
            assert activity.display
            assert "Writing" in str(activity.render())

            release.set()
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert log.children[-1] is activity
            assert not activity.display


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
            saved = await _story(tmp_path).read_message_history()
            assert _user_prompts(saved) == ["Write the opening."]


@pytest.mark.asyncio
async def test_an_empty_workspace_asks_for_a_story_before_writing(tmp_path) -> None:
    app = StorylineTui(_config(tmp_path))

    async with app.run_test() as pilot:
        assert "no stories yet" in _bodies(app, MessageKind.SYSTEM)[-1]
        assert "no story" in app.query_one(PromptBlock).placeholder

        await _submit(pilot, app, "Write the opening.")
        assert app.query_one(PromptBlock).value == "Write the opening."
        await _submit(pilot, app, "/script")

        assert _bodies(app, MessageKind.USER) == []
        assert all("No story is open" in body for body in _bodies(app, MessageKind.ERROR))
        assert len(_bodies(app, MessageKind.ERROR)) == 2


@pytest.mark.asyncio
async def test_new_command_creates_a_story_and_switches_to_it(tmp_path) -> None:
    app = StorylineTui(_config(tmp_path))

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/new harbor")
        await _submit(pilot, app, "/new harbor")
        await _submit(pilot, app, "/new")

        assert (tmp_path / "harbor").is_dir()
        assert "harbor" in app.query_one(PromptBlock).placeholder
        assert "Created harbor." in _bodies(app, MessageKind.SYSTEM)
        errors = _bodies(app, MessageKind.ERROR)
        assert "already exists" in errors[0]
        assert "/new <name>" in errors[1]


@pytest.mark.asyncio
async def test_several_stories_without_an_active_one_are_listed_for_choice(tmp_path) -> None:
    (tmp_path / "attic").mkdir()
    (tmp_path / "harbor").mkdir()
    app = StorylineTui(_config(tmp_path))

    async with app.run_test():
        choice = _bodies(app, MessageKind.SYSTEM)[-1]
        assert "Choose a story" in choice
        assert "attic" in choice and "harbor" in choice
        assert app._state.story is None


@pytest.mark.asyncio
async def test_switching_stories_shows_and_extends_each_storys_own_conversation(tmp_path) -> None:
    await _story(tmp_path, "attic").write_message_history(message_history=[_user_request("Attic prompt.")])
    await _story(tmp_path, "harbor").write_message_history(message_history=[_user_request("Harbor prompt.")])

    async def stream_response(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        yield "Done."

    app = StorylineTui(_config(tmp_path, requested_story="attic"))
    with app._config.agent.override(model=FunctionModel(stream_function=stream_response)):
        async with app.run_test() as pilot:
            assert _bodies(app, MessageKind.USER) == ["Attic prompt."]

            await _submit(pilot, app, "/story harbor")
            await _submit(pilot, app, "Continue the harbor.")
            await app.workers.wait_for_complete()

            assert _bodies(app, MessageKind.USER) == ["Harbor prompt.", "Continue the harbor."]
            assert "Switched to harbor." in _bodies(app, MessageKind.SYSTEM)
            assert "harbor" in app.query_one(PromptBlock).placeholder

    assert _user_prompts(await _story(tmp_path, "attic").read_message_history()) == ["Attic prompt."]
    assert _user_prompts(await _story(tmp_path, "harbor").read_message_history()) == [
        "Harbor prompt.",
        "Continue the harbor.",
    ]
    resumed = StorylineTui(_config(tmp_path))
    async with resumed.run_test():
        assert resumed._state.story is not None and resumed._state.story.name == "harbor"


@pytest.mark.asyncio
async def test_story_and_stories_commands_describe_the_workspace(tmp_path) -> None:
    (tmp_path / "attic").mkdir()
    (tmp_path / STORY_NAME).mkdir()
    app = StorylineTui(_config(tmp_path, requested_story=STORY_NAME))

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/stories")
        await _submit(pilot, app, "/story")
        await _submit(pilot, app, f"/story {STORY_NAME}")
        await _submit(pilot, app, "/story cellar")

        listing, active, already = _bodies(app, MessageKind.SYSTEM)[-3:]
        assert "  attic" in listing and f"* {STORY_NAME}" in listing
        assert active == f"Active story: {STORY_NAME}"
        assert already == f"Already working on {STORY_NAME}."
        assert "no story named 'cellar'" in _bodies(app, MessageKind.ERROR)[-1]
        assert app._state.story is not None and app._state.story.name == STORY_NAME


@pytest.mark.asyncio
async def test_a_requested_story_that_does_not_exist_is_reported(tmp_path) -> None:
    (tmp_path / "attic").mkdir()
    app = StorylineTui(_config(tmp_path, requested_story="cellar"))

    async with app.run_test():
        assert "no story named 'cellar'" in _bodies(app, MessageKind.ERROR)[0]
        assert app._state.story is None


@pytest.mark.asyncio
async def test_stories_cannot_change_while_the_agent_works(tmp_path) -> None:
    (tmp_path / "attic").mkdir()
    (tmp_path / STORY_NAME).mkdir()
    release = asyncio.Event()

    async def stream_response(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        await release.wait()
        yield "Done."

    app = StorylineTui(_config(tmp_path, requested_story=STORY_NAME))
    with app._config.agent.override(model=FunctionModel(stream_function=stream_response)):
        async with app.run_test() as pilot:
            await _submit(pilot, app, "Write the opening.")
            await _submit(pilot, app, "/story attic")
            await _submit(pilot, app, "/new cellar")
            release.set()
            await app.workers.wait_for_complete()

            assert len([body for body in _bodies(app, MessageKind.ERROR) if "agent is working" in body]) == 2
            assert app._state.story is not None and app._state.story.name == STORY_NAME
            assert not (tmp_path / "cellar").exists()


async def _submit(pilot, app: StorylineTui, text: str) -> None:
    app.query_one(PromptBlock).value = text
    await pilot.press("enter")
    await pilot.pause()


def _bodies(app: StorylineTui, kind: MessageKind) -> list[str]:
    return [message.body for message in app.query(ChatMessage) if message.kind == kind]


def _user_request(text: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=text)])


def _user_prompts(messages: list[ModelMessage]) -> list[str]:
    texts = [visible_prompt_text(part.content) for message in messages if isinstance(message, ModelRequest) for part in message.parts if isinstance(part, UserPromptPart)]
    return [text for text in texts if text]


def _story(workspace_path, name: str = STORY_NAME) -> FileStory:
    return FileStory(workspace_path / name)


def _config(workspace_path, *, requested_story: str | None = None) -> TuiConfig:
    return TuiConfig(
        library=StoryLibrary(FileWorkspace(workspace_path)),
        agent=create_writer_agent(),
        requested_story=requested_story,
    )


def _build_app(workspace_path) -> StorylineTui:
    """Build an app whose workspace holds a single story, which it opens on startup."""
    (workspace_path / STORY_NAME).mkdir(exist_ok=True)
    return StorylineTui(_config(workspace_path))


class SubmissionRecordingTui(StorylineTui):
    """A terminal app that records submitted prompts without starting an agent run."""

    def __init__(self, config: TuiConfig) -> None:
        super().__init__(config)
        self.submitted_prompts: list[str] = []

    async def on_prompt_block_submitted(self, message: PromptBlock.Submitted) -> None:
        self.submitted_prompts.append(message.value)


def _build_submission_app(workspace_path) -> SubmissionRecordingTui:
    return SubmissionRecordingTui(_config(workspace_path))


def test_session_turns_off_the_pydantic_ai_banner_that_would_draw_over_the_tui() -> None:
    assert pydantic_ai.BANNER_ENABLED is False


@pytest.mark.asyncio
async def test_a_story_remembers_the_model_it_was_last_used_with(tmp_path) -> None:
    async def stream_response(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        yield "Done."

    app = _build_app(tmp_path)
    with app._config.agent.override(model=FunctionModel(stream_function=stream_response)):
        async with app.run_test() as pilot:
            await _submit(pilot, app, "Continue.")
            await app.workers.wait_for_complete()
    assert await _story(tmp_path).read_model_name() == app._config.initial_model_name

    restarted = StorylineTui(_config(tmp_path))
    async with restarted.run_test() as pilot:
        await _submit(pilot, restarted, "/model openrouter:example/model")
    assert await _story(tmp_path).read_model_name() == "openrouter:example/model"

    resumed = StorylineTui(_config(tmp_path))
    async with resumed.run_test():
        assert resumed._state.model_name == "openrouter:example/model"
        assert "openrouter:example/model" in resumed.query_one(PromptBlock).placeholder


@pytest.mark.asyncio
async def test_switching_stories_switches_to_each_storys_model(tmp_path) -> None:
    await _story(tmp_path, "attic").write_model_name(model_name="openrouter:attic/model")
    (tmp_path / "harbor").mkdir()

    app = StorylineTui(_config(tmp_path, requested_story="attic"))
    async with app.run_test() as pilot:
        assert app._state.model_name == "openrouter:attic/model"
        assert any("openrouter:attic/model" in body for body in _bodies(app, MessageKind.SYSTEM))

        await _submit(pilot, app, "/story harbor")
        assert app._state.model_name == "openrouter:attic/model"

        await _submit(pilot, app, "/model openrouter:harbor/model")
        await _submit(pilot, app, "/story attic")
        assert app._state.model_name == "openrouter:attic/model"

    assert await _story(tmp_path, "harbor").read_model_name() == "openrouter:harbor/model"


@pytest.mark.asyncio
async def test_a_history_ending_in_an_unanswered_tool_call_is_repaired_on_open(tmp_path) -> None:
    (tmp_path / STORY_NAME).mkdir()
    broken = [
        _user_request("Try again."),
        ModelResponse(parts=[TextPart(content="Loading research."), ToolCallPart(tool_name="load_capability", args={"id": "research"}, tool_call_id="c1")]),
    ]
    await _story(tmp_path).write_message_history(message_history=broken)

    async def stream_response(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        yield "Done."

    app = StorylineTui(_config(tmp_path))
    with app._config.agent.override(model=FunctionModel(stream_function=stream_response)):
        async with app.run_test() as pilot:
            await _submit(pilot, app, "Go ahead.")
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert not _bodies(app, MessageKind.ERROR)
            assert [reply.body for reply in app.query(AgentReply)][-1] == "Done."

    saved = await _story(tmp_path).read_message_history()
    assert not any(isinstance(part, ToolCallPart) for message in saved for part in message.parts)


@pytest.mark.asyncio
async def test_undo_removes_the_last_exchange_and_returns_the_message_to_the_input(tmp_path) -> None:
    async def stream_response(_: list[ModelMessage], __: AgentInfo) -> AsyncIterator[str]:
        yield "Done."

    app = _build_app(tmp_path)
    with app._config.agent.override(model=FunctionModel(stream_function=stream_response)):
        async with app.run_test() as pilot:
            for prompt in ("First.", "Second."):
                await _submit(pilot, app, prompt)
                await app.workers.wait_for_complete()
                await pilot.pause()

            await _submit(pilot, app, "/undo")

            assert app.query_one(PromptBlock).value == "Second."
            assert _bodies(app, MessageKind.USER) == ["First."]
            assert len(list(app.query(AgentReply))) == 1
            assert any("Story files are unchanged" in body for body in _bodies(app, MessageKind.SYSTEM))

    assert _user_prompts(await _story(tmp_path).read_message_history()) == ["First."]


@pytest.mark.asyncio
async def test_undo_with_nothing_to_remove_says_so(tmp_path) -> None:
    app = _build_app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/undo")

        assert any("Nothing to undo" in body for body in _bodies(app, MessageKind.SYSTEM))
