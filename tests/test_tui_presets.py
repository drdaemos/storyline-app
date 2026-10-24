"""Tests for the terminal UI's story kinds (presets) and sealed lore."""

import json
from collections.abc import AsyncIterator

import pytest
from pydantic_ai import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.messages import ModelMessage, UserPromptPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel

from storyline.agent import create_writer_agent
from storyline.presets import BUNDLED_PRESETS, DEFAULT_PRESET_ID, PresetCatalog, load_presets
from storyline.tui.message_log import SEALED_DETAILS_NOTICE, ChatMessage, ToolLogEntry
from storyline.tui.models import MessageKind, TuiConfig
from storyline.tui.prompt import PromptBlock
from storyline.tui.session import StorylineTui
from storyline.workspace import StoryLibrary, StorySetup
from storyline.workspace.file_story import FileStory
from storyline.workspace.file_workspace import FileWorkspace

STORY_NAME = "noir"
LORE = "---\nsummary: {summary}\nkeywords: k\n---\n{body}\n"
SECRET = "Vera is the informant."
ARGUMENTS_MARKER = "argument-marker-1970"


def _two_preset_catalog(tmp_path) -> PresetCatalog:
    root = tmp_path / "catalog"
    for preset_id, title in ((DEFAULT_PRESET_ID, "Co-writing"), ("roleplay", "Roleplay")):
        directory = root / preset_id
        directory.mkdir(parents=True)
        (directory / "preset.md").write_text(
            f"---\nname: {preset_id}\ntitle: {title}\ndescription: The {title} kind of story.\nmechanics: []\n---\nHow you work together.\n",
            encoding="utf-8",
        )
    return load_presets(root)


@pytest.fixture
def catalog(tmp_path) -> PresetCatalog:
    """A two-preset catalog the terminal offers and the stories it creates open with."""
    return _two_preset_catalog(tmp_path)


def _workspace(tmp_path):
    return tmp_path / "workspace"


def _app(tmp_path, *, presets: PresetCatalog = BUNDLED_PRESETS, with_story: bool = False) -> StorylineTui:
    _workspace(tmp_path).mkdir(exist_ok=True)
    if with_story:
        (_workspace(tmp_path) / STORY_NAME).mkdir(exist_ok=True)
    config = TuiConfig(library=StoryLibrary(FileWorkspace(_workspace(tmp_path))), agent=create_writer_agent(), presets=presets)
    return StorylineTui(config)


def _story(tmp_path) -> FileStory:
    return FileStory(_workspace(tmp_path) / STORY_NAME)


async def _story_with_sealed_lore(tmp_path) -> FileStory:
    story = _story(tmp_path)
    (_workspace(tmp_path) / STORY_NAME).mkdir(parents=True, exist_ok=True)
    await story.write_setup(setup=StorySetup(mechanics=("sealed",)))
    await story.write_lore(filename="city.md", content=LORE.format(summary="The city.", body="Buffalo."))
    await story.write_lore(filename="sealed/vera.md", content=LORE.format(summary="What Vera wants.", body=SECRET))
    return story


async def _submit(pilot, app: StorylineTui, text: str) -> None:
    app.query_one(PromptBlock).value = text
    await pilot.press("enter")
    await pilot.pause()


def _bodies(app: StorylineTui, kind: MessageKind) -> list[str]:
    return [message.body for message in app.query(ChatMessage) if message.kind == kind]


def _details(entry: ToolLogEntry) -> str:
    return str(entry.query_one(".tool-details").render())


@pytest.mark.asyncio
async def test_presets_command_lists_each_kind_and_marks_the_default(tmp_path, catalog) -> None:
    app = _app(tmp_path, presets=catalog)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/presets")

        listing = _bodies(app, MessageKind.SYSTEM)[-1]
        lines = {line.split()[0]: line for line in listing.splitlines() if line.strip()}
        assert "(default)" in lines[DEFAULT_PRESET_ID] and "Co-writing" in lines[DEFAULT_PRESET_ID]
        assert "Roleplay" in lines["roleplay"] and "kind of story" in lines["roleplay"]
        assert "(default)" not in lines["roleplay"]
        assert listing.index(DEFAULT_PRESET_ID) < listing.index("roleplay")


@pytest.mark.asyncio
async def test_presets_command_lists_the_bundled_kinds_by_default(tmp_path) -> None:
    app = _app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/presets")

        listing = _bodies(app, MessageKind.SYSTEM)[-1]
        assert all(preset.id in listing and preset.title in listing for preset in BUNDLED_PRESETS.summaries())


@pytest.mark.asyncio
async def test_new_creates_a_co_writing_story_unless_told_otherwise(tmp_path) -> None:
    app = _app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/new harbor")

        assert await FileStory(_workspace(tmp_path) / "harbor").read_setup() == StorySetup(preset=DEFAULT_PRESET_ID)
        assert "Created harbor." in _bodies(app, MessageKind.SYSTEM)
        assert app._state.room is not None and app._state.room.snapshot().preset == DEFAULT_PRESET_ID


@pytest.mark.asyncio
async def test_new_as_a_preset_creates_the_story_as_that_kind(tmp_path, catalog) -> None:
    app = _app(tmp_path, presets=catalog)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/new harbor lights --as roleplay")

        story = FileStory(_workspace(tmp_path) / "harbor lights")
        assert (await story.read_setup()).preset == "roleplay"
        assert "Created harbor lights." in _bodies(app, MessageKind.SYSTEM)
        assert app._state.room is not None and app._state.room.snapshot().preset == "roleplay"


@pytest.mark.asyncio
async def test_new_as_an_unknown_preset_lists_the_known_ones_and_creates_nothing(tmp_path, catalog) -> None:
    app = _app(tmp_path, presets=catalog)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/new harbor --as nope")
        await _submit(pilot, app, "/new harbor --as")

        errors = _bodies(app, MessageKind.ERROR)
        assert "nope" in errors[0] and DEFAULT_PRESET_ID in errors[0] and "roleplay" in errors[0]
        assert "--as" in errors[1]
        assert not (_workspace(tmp_path) / "harbor").exists()
        assert app._state.room is None


@pytest.mark.asyncio
async def test_the_prompt_names_a_stories_preset_unless_it_is_the_default(tmp_path, catalog) -> None:
    app = _app(tmp_path, presets=catalog)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/new harbor")
        assert app.query_one(PromptBlock).placeholder == f"> [harbor · {app._state.model_name}]"

        await _submit(pilot, app, "/new mill --as roleplay")
        assert app.query_one(PromptBlock).placeholder == f"> [mill · roleplay · {app._state.model_name}]"

        await _submit(pilot, app, "/story harbor")
        assert "roleplay" not in app.query_one(PromptBlock).placeholder


@pytest.mark.asyncio
async def test_lore_hides_sealed_files_and_counts_them(tmp_path) -> None:
    await _story_with_sealed_lore(tmp_path)
    app = _app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/lore")

        listing = _bodies(app, MessageKind.SYSTEM)[-1]
        assert "city.md" in listing and "The city." in listing
        assert "vera" not in listing and "Vera" not in listing
        assert "1 sealed" in listing and "/sealed" in listing


@pytest.mark.asyncio
async def test_lore_without_sealed_files_says_nothing_about_them(tmp_path) -> None:
    story = _story(tmp_path)
    (_workspace(tmp_path) / STORY_NAME).mkdir(parents=True)
    await story.write_lore(filename="city.md", content=LORE.format(summary="The city.", body="Buffalo."))
    app = _app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/lore")

        assert "sealed" not in _bodies(app, MessageKind.SYSTEM)[-1]


@pytest.mark.asyncio
async def test_lore_points_to_sealed_instead_of_showing_a_sealed_file(tmp_path) -> None:
    await _story_with_sealed_lore(tmp_path)
    app = _app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/lore sealed/vera.md")

        shown = _bodies(app, MessageKind.SYSTEM)[-1]
        assert "/sealed" in shown
        assert SECRET not in shown
        assert _bodies(app, MessageKind.ERROR) == []


@pytest.mark.asyncio
async def test_sealed_lists_the_sealed_files_behind_a_spoiler_warning(tmp_path) -> None:
    await _story_with_sealed_lore(tmp_path)
    app = _app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/sealed")

        listing = _bodies(app, MessageKind.SYSTEM)[-1]
        lines = listing.splitlines()
        assert "poiler" in lines[0]
        assert "sealed/vera.md" in listing and "What Vera wants." in listing
        assert SECRET not in listing
        assert "city.md" not in listing


@pytest.mark.asyncio
@pytest.mark.parametrize("argument", ["vera", "vera.md", "sealed/vera.md"])
async def test_sealed_shows_one_file_by_any_of_its_names(tmp_path, argument: str) -> None:
    await _story_with_sealed_lore(tmp_path)
    app = _app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, f"/sealed {argument}")

        shown = _bodies(app, MessageKind.SYSTEM)[-1]
        assert "poiler" in shown.splitlines()[0]
        assert "sealed/vera.md" in shown and SECRET in shown


@pytest.mark.asyncio
async def test_sealed_reports_a_missing_file_and_a_story_without_sealed_lore(tmp_path) -> None:
    await _story_with_sealed_lore(tmp_path)
    app = _app(tmp_path)

    async with app.run_test() as pilot:
        await _submit(pilot, app, "/sealed nobody")
        assert "nobody" in _bodies(app, MessageKind.ERROR)[-1]

        await _submit(pilot, app, "/new harbor")
        await _submit(pilot, app, "/sealed")
        assert "No sealed" in _bodies(app, MessageKind.SYSTEM)[-1]


def _sealed_calls_history() -> list[ModelMessage]:
    return [
        ModelRequest(parts=[UserPromptPart(content="What does Vera want?")]),
        ModelResponse(parts=[ToolCallPart(tool_name="read_lore", args={"filename": "sealed/vera.md", "note": ARGUMENTS_MARKER}, tool_call_id="c1")]),
        ModelRequest(parts=[ToolReturnPart(tool_name="read_lore", content=SECRET, tool_call_id="c1")]),
        ModelResponse(parts=[ToolCallPart(tool_name="read_lore", args={"filename": "city.md"}, tool_call_id="c2")]),
        ModelRequest(parts=[ToolReturnPart(tool_name="read_lore", content="Buffalo.", tool_call_id="c2")]),
        ModelResponse(parts=[TextPart(content="Done.")]),
    ]


@pytest.mark.asyncio
async def test_restored_sealed_tool_entries_hide_their_arguments_and_result(tmp_path) -> None:
    story = await _story_with_sealed_lore(tmp_path)
    await story.write_message_history(message_history=_sealed_calls_history())
    app = _app(tmp_path)

    async with app.run_test() as pilot:
        sealed, open_entry = list(app.query(ToolLogEntry))
        assert sealed.title == "read_lore · success · sealed"
        assert open_entry.title == "read_lore · success"

        sealed.collapsed = False
        open_entry.collapsed = False
        await pilot.pause()

        hidden = _details(sealed)
        assert hidden == SEALED_DETAILS_NOTICE and "/sealed" in hidden
        assert ARGUMENTS_MARKER not in hidden and SECRET not in hidden
        assert "Buffalo." in _details(open_entry)


@pytest.mark.asyncio
async def test_live_sealed_tool_entries_stay_hidden_when_the_result_arrives(tmp_path) -> None:
    await _story_with_sealed_lore(tmp_path)

    async def stream_response(messages: list[ModelMessage], _: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        if any(isinstance(part, ToolReturnPart) for message in messages for part in message.parts):
            yield "Done."
            return
        arguments = json.dumps({"filename": "sealed/vera.md"})
        yield {0: DeltaToolCall(name="read_lore", json_args=arguments, tool_call_id="c1")}

    app = _app(tmp_path)
    with app._config.agent.override(model=FunctionModel(stream_function=stream_response)):
        async with app.run_test() as pilot:
            await _submit(pilot, app, "What does Vera want?")
            await app.workers.wait_for_complete()
            await pilot.pause()

            (entry,) = (entry for entry in app.query(ToolLogEntry) if entry.title.startswith("read_lore"))
            entry.collapsed = False
            await pilot.pause()

            assert entry.title == "read_lore · success · sealed"
            assert _details(entry) == SEALED_DETAILS_NOTICE
            assert "vera" not in _details(entry) and SECRET not in _details(entry)
