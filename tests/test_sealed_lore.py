"""Tests for sealed lore: files under ``sealed/`` that the lore operations accept and report apart from the story's own."""

import pytest

from storyline.workspace import LoreEditError
from storyline.workspace.file_story import FileStory

HEADER = "---\nsummary: {summary}\nkeywords: {keywords}\n---\n{body}\n"


def _lore(summary: str, body: str = "Text.") -> str:
    return HEADER.format(summary=summary, keywords="k", body=body)


@pytest.mark.asyncio
async def test_writing_a_sealed_file_creates_the_folder_and_reports_the_filename_with_a_slash(tmp_path) -> None:
    story = FileStory(tmp_path)

    edit = await story.write_lore(filename="sealed/vera.md", content=_lore("What Vera wants."))

    assert edit.filename == "sealed/vera.md"
    assert (tmp_path / "sealed" / "vera.md").is_file()
    assert await story.read_lore(filename="sealed/vera.md") == _lore("What Vera wants.")


@pytest.mark.asyncio
@pytest.mark.parametrize("filename", ["sealed/vera.md", "sealed/vera", "sealed\\vera.md", "  sealed/vera.md  "])
async def test_sealed_filenames_are_accepted_in_every_spelling(tmp_path, filename) -> None:
    story = FileStory(tmp_path)

    await story.write_lore(filename=filename, content=_lore("Vera."))

    assert [lore.filename for lore in await story.list_lore()] == ["sealed/vera.md"]


@pytest.mark.asyncio
async def test_list_lore_returns_the_stories_own_files_first_then_the_sealed_ones_each_flagged(tmp_path) -> None:
    story = FileStory(tmp_path)
    await story.write_lore(filename="sealed/vera.md", content=_lore("Vera."))
    await story.write_lore(filename="city.md", content=_lore("The city."))
    await story.write_lore(filename="sealed/arno.md", content=_lore("Arno."))
    await story.write_lore(filename="atlas.md", content=_lore("Atlas."))

    listed = await story.list_lore()

    assert [(lore.filename, lore.sealed) for lore in listed] == [
        ("atlas.md", False),
        ("city.md", False),
        ("sealed/arno.md", True),
        ("sealed/vera.md", True),
    ]
    assert listed[2].summary == "Arno."


@pytest.mark.asyncio
async def test_a_story_without_a_sealed_folder_lists_only_its_own_lore(tmp_path) -> None:
    story = FileStory(tmp_path)
    await story.write_lore(filename="city.md", content=_lore("The city."))

    assert [(lore.filename, lore.sealed) for lore in await story.list_lore()] == [("city.md", False)]


@pytest.mark.asyncio
async def test_sealed_files_can_be_appended_edited_and_deleted_like_any_lore(tmp_path) -> None:
    story = FileStory(tmp_path)
    await story.write_lore(filename="sealed/vera.md", content=_lore("Vera.", "She lies."))

    appended = await story.append_lore(filename="sealed/vera.md", text="\nShe knows.")
    edited = await story.replace_in_lore(filename="sealed/vera.md", find="She lies.", replace="She hides.")
    await story.delete_lore(filename="sealed/vera.md")

    assert appended.filename == edited.filename == "sealed/vera.md"
    assert await story.list_lore() == ()
    with pytest.raises(LoreEditError, match="sealed/vera.md"):
        await story.read_lore(filename="sealed/vera.md")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename",
    ["sealed/sub/vera.md", "other/vera.md", "Sealed/vera.md", "/vera.md", "/sealed/vera.md", "../vera.md", "sealed/../vera.md", "C:\\vera.md", "sealed/", "", "sealed/script.md", "script.md", "sealed/vera.txt"],
)
async def test_every_other_path_is_still_refused(tmp_path, filename) -> None:
    story = FileStory(tmp_path)

    with pytest.raises(LoreEditError):
        await story.write_lore(filename=filename, content=_lore("Nope."))
    with pytest.raises(LoreEditError):
        await story.read_lore(filename=filename)

    assert [path.name for path in tmp_path.iterdir()] == []
