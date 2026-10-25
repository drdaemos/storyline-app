"""Tests for the agenda panel in the terminal UI."""

import asyncio
from collections.abc import AsyncIterator

import pytest
from pydantic_ai import ToolReturnPart
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel
from textual.widgets import Static

from storyline.agent import create_writer_agent
from storyline.room import ClocksChanged, ClockView
from storyline.tui.agenda_panel import AgendaPanel, agenda_line, clock_line
from storyline.tui.models import TuiConfig
from storyline.tui.prompt import PromptBlock
from storyline.tui.session import StorylineTui
from storyline.workspace import AgendaItem, Clock, StoryLibrary
from storyline.workspace.file_story import FileStory
from storyline.workspace.file_workspace import FileWorkspace

STORY_NAME = "noir"


@pytest.mark.parametrize(
    ("item", "line"),
    [
        (AgendaItem(title="The city"), "○ The city"),
        (AgendaItem(title="The city", status="working"), "● The city"),
        (AgendaItem(title="Who she is", status="waiting"), "◐ Who she is — waiting on you"),
        (AgendaItem(title="The city", status="settled", outcome="Buffalo"), "✓ The city — Buffalo"),
        (AgendaItem(title="A subplot", status="dropped"), "✗ A subplot"),
    ],
)
def test_agenda_line_shows_each_status(item: AgendaItem, line: str) -> None:
    assert agenda_line(item) == line


@pytest.mark.asyncio
async def test_panel_is_hidden_without_an_agenda_and_lists_items_with_one(tmp_path) -> None:
    items = [AgendaItem(title="The city", status="settled", outcome="Buffalo"), AgendaItem(title="Who she is")]
    await FileStory(tmp_path / STORY_NAME).write_agenda(items=items)
    (tmp_path / "empty").mkdir()
    app = _app(tmp_path)

    async with app.run_test() as pilot:
        panel = app.query_one(AgendaPanel)
        assert panel.display
        assert _lines(panel) == ["✓ The city — Buffalo", "○ Who she is"]

        await _submit(pilot, app, "/story empty")

        assert not panel.display
        assert _lines(panel) == []

        await _submit(pilot, app, f"/story {STORY_NAME}")

        assert panel.display
        assert len(_lines(panel)) == 2


@pytest.mark.asyncio
async def test_panel_refreshes_as_soon_as_the_agent_changes_the_agenda(tmp_path) -> None:
    release = asyncio.Event()

    async def stream_response(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        if any(isinstance(part, ToolReturnPart) for message in messages for part in message.parts):
            await release.wait()
            yield "Done."
        else:
            yield {0: DeltaToolCall(name="set_agenda", json_args='{"items": [{"title": "The city", "status": "working"}]}', tool_call_id="c1")}

    app = _app(tmp_path)
    with app._config.agent.override(model=FunctionModel(stream_function=stream_response)):
        async with app.run_test() as pilot:
            panel = app.query_one(AgendaPanel)
            assert not panel.display

            await _submit(pilot, app, "Plan the story.")
            for _ in range(5):
                await pilot.pause()

            assert app._busy
            assert panel.display
            assert _lines(panel) == ["● The city"]

            release.set()
            await app.workers.wait_for_complete()


def test_clock_line_shows_the_bar_and_marks_a_full_clock() -> None:
    assert clock_line(ClockView(id="a", name="Dawn", segments=6, filled=2)) == "Dawn ■■□□□□ 2/6"
    assert clock_line(ClockView(id="a", name="Dawn", segments=4, filled=4)) == "Dawn ■■■■ 4/4 ✓ full"


@pytest.mark.asyncio
async def test_panel_shows_visible_clocks_and_only_counts_hidden_ones(tmp_path) -> None:
    clocks = [
        Clock(name="Dawn", segments=6, filled=2, visible=True),
        Clock(name="The traitor", segments=4, filled=1, visible=False),
    ]
    await FileStory(tmp_path / STORY_NAME).change_clocks(change=lambda _: clocks)
    app = _app(tmp_path)

    async with app.run_test() as pilot:
        panel = app.query_one(AgendaPanel)
        assert panel.display
        assert _lines(panel) == ["Clocks", "Dawn ■■□□□□ 2/6", "1 hidden"]
        assert "traitor" not in " ".join(_lines(panel))

        (tmp_path / "empty").mkdir()
        await _submit(pilot, app, "/story empty")

        assert not panel.display
        assert _lines(panel) == []


@pytest.mark.asyncio
async def test_panel_follows_clock_events_and_sits_below_the_agenda(tmp_path) -> None:
    await FileStory(tmp_path / STORY_NAME).write_agenda(items=[AgendaItem(title="The city")])
    app = _app(tmp_path)

    async with app.run_test() as pilot:
        panel = app.query_one(AgendaPanel)
        assert _lines(panel) == ["○ The city"]

        await app._show_event(ClocksChanged(clocks=(ClockView(id="a", name="Dawn", segments=3, filled=3),), hidden=0))
        await pilot.pause()
        assert _lines(panel) == ["○ The city", "Clocks", "Dawn ■■■ 3/3 ✓ full"]

        await app._show_event(ClocksChanged(clocks=(), hidden=2))
        await pilot.pause()
        assert _lines(panel) == ["○ The city", "Clocks", "2 hidden"]

        await app._show_event(ClocksChanged(clocks=(), hidden=0))
        await pilot.pause()
        assert _lines(panel) == ["○ The city"]


def _lines(panel: AgendaPanel) -> list[str]:
    return [str(line.render()) for line in panel.query(Static)]


def _app(workspace_path) -> StorylineTui:
    (workspace_path / STORY_NAME).mkdir(exist_ok=True)
    config = TuiConfig(library=StoryLibrary(FileWorkspace(workspace_path)), agent=create_writer_agent(), requested_story=STORY_NAME)
    return StorylineTui(config)


async def _submit(pilot, app: StorylineTui, text: str) -> None:
    app.query_one(PromptBlock).value = text
    await pilot.press("enter")
    await pilot.pause()
