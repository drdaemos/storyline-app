"""Tests for choosing, switching and creating stories in a workspace."""

import pytest

from storyline.workspace import StoryLibrary, StorySelectionError
from storyline.workspace.file_workspace import FileWorkspace


def _library(workspace_path) -> StoryLibrary:
    return StoryLibrary(FileWorkspace(workspace_path))


@pytest.mark.asyncio
async def test_stories_are_the_visible_subdirectories_of_the_workspace(tmp_path) -> None:
    for name in ("harbor", "attic", ".storyline", ".hidden"):
        (tmp_path / name).mkdir()
    (tmp_path / "script.md").write_text("A story from before workspaces held many.", encoding="utf-8")

    assert await _library(tmp_path).list_stories() == ("attic", "harbor")


@pytest.mark.asyncio
async def test_a_missing_workspace_directory_has_no_stories(tmp_path) -> None:
    assert await _library(tmp_path / "missing").list_stories() == ()


@pytest.mark.asyncio
async def test_created_story_becomes_active_and_is_resumed_next_session(tmp_path) -> None:
    await _library(tmp_path).create(name="attic")
    created = await _library(tmp_path).create(name="  harbor ")

    resumed = await _library(tmp_path).open_initial()

    assert created.name == "harbor"
    assert (tmp_path / "harbor").is_dir()
    assert resumed is not None and resumed.name == "harbor"


@pytest.mark.asyncio
async def test_switching_changes_the_story_resumed_next_session(tmp_path) -> None:
    library = _library(tmp_path)
    await library.create(name="attic")
    await library.create(name="harbor")

    await library.switch(name="attic")
    resumed = await _library(tmp_path).open_initial()

    assert resumed is not None and resumed.name == "attic"


@pytest.mark.asyncio
async def test_a_requested_story_wins_over_the_last_active_one(tmp_path) -> None:
    library = _library(tmp_path)
    await library.create(name="attic")
    await library.create(name="harbor")

    opened = await _library(tmp_path).open_initial(requested="attic")

    assert opened is not None and opened.name == "attic"


@pytest.mark.asyncio
async def test_the_only_story_opens_when_none_was_active(tmp_path) -> None:
    (tmp_path / "harbor").mkdir()

    opened = await _library(tmp_path).open_initial()

    assert opened is not None and opened.name == "harbor"


@pytest.mark.asyncio
async def test_no_story_opens_when_the_choice_is_ambiguous(tmp_path) -> None:
    (tmp_path / "attic").mkdir()
    (tmp_path / "harbor").mkdir()

    assert await _library(tmp_path).open_initial() is None
    assert await _library(tmp_path / "empty").open_initial() is None


@pytest.mark.asyncio
async def test_a_removed_active_story_is_not_resumed(tmp_path) -> None:
    library = _library(tmp_path)
    await library.create(name="attic")
    await library.create(name="harbor")
    await library.create(name="cellar")
    (tmp_path / "cellar").rmdir()

    assert await _library(tmp_path).open_initial() is None


@pytest.mark.asyncio
async def test_unreadable_workspace_state_is_treated_as_no_active_story(tmp_path) -> None:
    (tmp_path / "attic").mkdir()
    (tmp_path / "harbor").mkdir()
    (tmp_path / ".storyline").mkdir()
    (tmp_path / ".storyline" / "state.json").write_text("not json", encoding="utf-8")

    assert await _library(tmp_path).open_initial() is None


@pytest.mark.asyncio
async def test_missing_stories_cannot_be_opened(tmp_path) -> None:
    library = _library(tmp_path)

    with pytest.raises(StorySelectionError, match="no story named 'attic'"):
        await library.switch(name="attic")
    with pytest.raises(StorySelectionError, match="no story named 'attic'"):
        await library.open_initial(requested="attic")


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["", "  ", ".hidden", "trailing.", "../outside", "a/b", "a\\b", "what?", "c:"])
async def test_story_names_must_be_single_visible_directory_names(tmp_path, name: str) -> None:
    with pytest.raises(StorySelectionError, match="Story names"):
        await _library(tmp_path).create(name=name)

    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_existing_stories_are_not_created_again(tmp_path) -> None:
    library = _library(tmp_path)
    story = await library.create(name="attic")
    await story.append_script(text="Dust.")

    with pytest.raises(StorySelectionError, match="already exists"):
        await library.create(name="attic")
    assert await story.read_script() == "Dust."


@pytest.mark.asyncio
async def test_each_story_keeps_its_own_script_lore_and_history(tmp_path) -> None:
    library = _library(tmp_path)
    attic = await library.create(name="attic")
    harbor = await library.create(name="harbor")

    await attic.append_script(text="Dust.")
    await attic.write_lore(filename="house.md", content="---\nsummary: The house.\nkeywords: house\n---\n")
    await attic.write_message_history(message_history=[])

    assert await harbor.read_script() == ""
    assert await harbor.list_lore() == ()
    assert sorted(path.name for path in (tmp_path / "harbor").iterdir()) == []
