"""Tests for the local script workspace."""

import pytest
from pydantic_ai import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.messages import UserPromptPart

from storyline.workspace import (
    ConversationHistoryError,
    LoreEditError,
    LoreFile,
    TextEditError,
    WorkspaceConfigurationError,
    open_workspace,
)
from storyline.workspace.file import CONVERSATION_HISTORY_FILENAME, FileWorkspace
from storyline.workspace.text_edit import SNIPPET_RADIUS, paragraphs

LORE_HEADER = "---\nsummary: A mystery reference.\nkeywords: mystery, city\n---\n"


@pytest.mark.asyncio
async def test_script_is_appended_to_and_edited_by_unique_excerpt(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)

    first = await workspace.append_script(text="INT. ROOM")
    await workspace.append_script(text=" - NIGHT\n\nRain falls.")
    edit = await workspace.replace_in_script(find="Rain falls", replace="Snow falls")

    assert first.original_length == 0
    assert await workspace.read_script() == "INT. ROOM - NIGHT\n\nSnow falls."
    assert edit.filename == "script.md"
    assert "Snow falls." in edit.snippet


@pytest.mark.asyncio
async def test_script_edits_insert_and_delete_through_anchors(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    await workspace.append_script(text="She opened the door. The hall was dark.")

    await workspace.replace_in_script(find="the door.", replace="the door. It creaked.")
    await workspace.replace_in_script(find=" The hall was dark.", replace="")

    assert await workspace.read_script() == "She opened the door. It creaked."


@pytest.mark.asyncio
async def test_script_edit_requires_exactly_one_match(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    await workspace.append_script(text="The bell rang. The bell rang again.")

    with pytest.raises(TextEditError, match="matches 2 places"):
        await workspace.replace_in_script(find="The bell rang", replace="A bell tolled")
    with pytest.raises(TextEditError, match="does not match"):
        await workspace.replace_in_script(find="The whistle blew", replace="x")
    with pytest.raises(TextEditError, match="must not be empty"):
        await workspace.replace_in_script(find="", replace="x")

    assert await workspace.read_script() == "The bell rang. The bell rang again."


@pytest.mark.asyncio
async def test_script_edit_tolerates_whitespace_and_typographic_quote_differences(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    await workspace.append_script(text="“Stay,” she said.\n  He   didn’t move.\n\nThe end.")

    await workspace.replace_in_script(find='"Stay," she said. He didn\'t move.', replace="He left.")

    assert await workspace.read_script() == "He left.\n\nThe end."


@pytest.mark.asyncio
async def test_edit_snippets_stay_small_for_long_changes(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    long_text = "word " * 1000

    edit = await workspace.append_script(text=long_text)

    assert len(edit.snippet) < 4 * SNIPPET_RADIUS + 10
    assert " … " in edit.snippet


def test_paragraphs_are_numbered_blocks_separated_by_blank_lines() -> None:
    assert [(paragraph.number, paragraph.text) for paragraph in paragraphs("\nOne.\n\n  \nTwo\nlines.\n\nThree.\n")] == [
        (1, "One."),
        (2, "Two\nlines."),
        (3, "Three."),
    ]


@pytest.mark.asyncio
async def test_lore_files_are_written_appended_edited_and_deleted(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)

    created = await workspace.write_lore(filename="mira", content=f"{LORE_HEADER}The blue clue is hidden.")
    await workspace.append_lore(filename="mira.md", text="\nLikes jazz.")
    await workspace.replace_in_lore(filename="mira.md", find="blue", replace="red")

    assert created.filename == "mira.md"
    assert created.original_length == 0
    assert await workspace.list_lore() == (
        LoreFile(filename="mira.md", summary="A mystery reference.", keywords="mystery, city"),
    )
    assert await workspace.read_lore(filename="mira") == f"{LORE_HEADER}The red clue is hidden.\nLikes jazz."

    await workspace.delete_lore(filename="mira.md")

    assert await workspace.list_lore() == ()


@pytest.mark.asyncio
async def test_write_lore_replaces_existing_content(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    await workspace.write_lore(filename="mira.md", content=f"{LORE_HEADER}Old.")

    rewritten = await workspace.write_lore(filename="mira.md", content=f"{LORE_HEADER}New.")

    assert rewritten.original_length == len(f"{LORE_HEADER}Old.")
    assert await workspace.read_lore(filename="mira.md") == f"{LORE_HEADER}New."


@pytest.mark.asyncio
async def test_workspace_rejects_invalid_lore_edits(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)

    with pytest.raises(LoreEditError, match="Markdown filenames"):
        await workspace.write_lore(filename="../outside.md", content=LORE_HEADER)
    with pytest.raises(LoreEditError, match="summary and keywords"):
        await workspace.write_lore(filename="setting.md", content="New detail")
    with pytest.raises(LoreEditError, match="summary and keywords"):
        await workspace.write_lore(filename="invalid.md", content="---\nsummary: Missing keywords\n---\nContent")
    with pytest.raises(LoreEditError, match="does not exist"):
        await workspace.read_lore(filename="setting.md")
    with pytest.raises(LoreEditError, match="does not exist"):
        await workspace.append_lore(filename="setting.md", text="More.")
    with pytest.raises(LoreEditError, match="does not exist"):
        await workspace.delete_lore(filename="setting.md")

    await workspace.write_lore(filename="setting.md", content=f"{LORE_HEADER}Text")
    with pytest.raises(TextEditError, match="does not match"):
        await workspace.replace_in_lore(filename="setting.md", find="Missing", replace="x")
    with pytest.raises(LoreEditError, match="summary and keywords"):
        await workspace.replace_in_lore(filename="setting.md", find="summary", replace="title")


@pytest.mark.asyncio
async def test_workspace_persists_complete_conversation_history(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    tool_call_id = "call-123"
    history = [
        ModelRequest(parts=[UserPromptPart(content="Add an opening.")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="append_to_script", args={"text": "FADE IN:"}, tool_call_id=tool_call_id)]
        ),
        ModelRequest(
            parts=[ToolReturnPart(tool_name="append_to_script", content="Appended.", tool_call_id=tool_call_id)]
        ),
        ModelResponse(parts=[TextPart(content="Added an opening.")]),
    ]

    await workspace.write_message_history(message_history=history)
    restored_history = await FileWorkspace(tmp_path).read_message_history()

    assert restored_history == history
    assert (tmp_path / CONVERSATION_HISTORY_FILENAME).is_file()


@pytest.mark.asyncio
async def test_workspace_writes_leave_no_temporary_files(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)

    await workspace.append_script(text="Opening.")
    await workspace.write_lore(filename="setting.md", content=LORE_HEADER)
    await workspace.write_message_history(message_history=[])

    assert sorted(path.name for path in tmp_path.iterdir()) == [CONVERSATION_HISTORY_FILENAME, "script.md", "setting.md"]


@pytest.mark.asyncio
async def test_unreadable_history_can_be_archived(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    (tmp_path / CONVERSATION_HISTORY_FILENAME).write_text("not json", encoding="utf-8")

    with pytest.raises(ConversationHistoryError):
        await workspace.read_message_history()
    archive_name = await workspace.archive_message_history()

    assert await workspace.read_message_history() == []
    assert (tmp_path / archive_name).read_text(encoding="utf-8") == "not json"


def test_open_workspace_requires_a_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STORYLINE_WORKSPACE", raising=False)

    with pytest.raises(WorkspaceConfigurationError, match="STORYLINE_WORKSPACE"):
        open_workspace()


def test_open_workspace_falls_back_to_the_environment(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("STORYLINE_WORKSPACE", str(tmp_path))

    workspace = open_workspace()

    assert isinstance(workspace, FileWorkspace)
    assert workspace.root == tmp_path.resolve()


def test_open_workspace_prefers_an_explicit_path(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("STORYLINE_WORKSPACE", str(tmp_path / "from-env"))

    workspace = open_workspace(str(tmp_path / "explicit"))

    assert isinstance(workspace, FileWorkspace)
    assert workspace.root == (tmp_path / "explicit").resolve()
