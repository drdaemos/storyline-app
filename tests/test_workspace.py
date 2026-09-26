"""Tests for the local script workspace."""

import pytest
from pydantic_ai import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.messages import UserPromptPart

from storyline.workspace import (
    LoreEditError,
    LoreFile,
    ScriptEditError,
    WorkspaceConfigurationError,
    open_workspace,
)
from storyline.workspace.file import CONVERSATION_HISTORY_FILENAME, FileWorkspace


@pytest.mark.asyncio
async def test_workspace_replaces_a_script_range_and_appends(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)

    first_edit = await workspace.apply_edit(start_offset=0, end_offset=0, replacement="INT. ROOM")
    append_edit = await workspace.apply_edit(start_offset=9, end_offset=9, replacement=" - NIGHT")

    assert first_edit.original_length == 0
    assert append_edit.new_length == 17
    assert await workspace.read_script() == "INT. ROOM - NIGHT"


@pytest.mark.asyncio
async def test_workspace_rejects_ranges_outside_the_script(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)

    with pytest.raises(ScriptEditError, match="Invalid edit range"):
        await workspace.apply_edit(start_offset=1, end_offset=1, replacement="x")


@pytest.mark.asyncio
async def test_workspace_accepts_derived_ranges_and_bare_lore_filenames(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    await workspace.apply_edit(start_offset=0, end_offset=0, replacement="abc")

    script_edit = await workspace.apply_edit(start_offset=1, replacement="B")
    lore_content = "---\nSummary: A brief setting reference.\nKeywords: city, mystery\n---\nThe room is red."
    await workspace.edit_lore(filename="setting", action="append", content=lore_content)
    lore_edit = await workspace.edit_lore(
        filename="setting",
        action="replace",
        content="tan",
        start_offset=lore_content.index("red"),
    )

    assert script_edit.end_offset == 2
    assert await workspace.read_script() == "aBc"
    assert lore_edit.filename == "setting.md"
    assert await workspace.read_lore(filename="setting") == lore_content.replace("red", "tan")
    assert await workspace.list_lore() == (
        LoreFile(filename="setting.md", summary="A brief setting reference.", keywords="city, mystery"),
    )

    deleted = await workspace.edit_lore(filename="setting", action="delete")
    deleted_again = await workspace.edit_lore(filename="setting", action="delete")

    assert deleted.original_length == len(lore_content)
    assert deleted.new_length == 0
    assert deleted_again.original_length == 0
    assert await workspace.list_lore() == ()


@pytest.mark.asyncio
async def test_workspace_lists_lore_headers_and_edits_lore_files(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    original_content = "---\nsummary: A mystery reference.\nkeywords: mystery, city\n---\nThe blue clue is hidden."

    created = await workspace.edit_lore(
        filename="mira.md",
        action="append",
        content=original_content,
    )
    appended = await workspace.edit_lore(
        filename="mira.md",
        action="append",
        content="\nLikes jazz.",
    )
    replaced = await workspace.edit_lore(
        filename="mira.md",
        action="replace",
        content="red",
        start_offset=original_content.index("blue"),
        end_offset=original_content.index("blue") + len("blue"),
    )

    assert created.original_length == 0
    assert appended.new_length == len(original_content) + len("\nLikes jazz.")
    assert replaced.new_length == appended.new_length + len("red") - len("blue")
    assert await workspace.list_lore() == (
        LoreFile(filename="mira.md", summary="A mystery reference.", keywords="mystery, city"),
    )
    assert await workspace.read_lore(filename="mira.md") == "---\nsummary: A mystery reference.\nkeywords: mystery, city\n---\nThe red clue is hidden.\nLikes jazz."
    assert (tmp_path / "mira.md").read_text(encoding="utf-8") == "---\nsummary: A mystery reference.\nkeywords: mystery, city\n---\nThe red clue is hidden.\nLikes jazz."


@pytest.mark.asyncio
async def test_workspace_rejects_invalid_lore_edits(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)

    with pytest.raises(LoreEditError, match="Markdown filenames"):
        await workspace.edit_lore(filename="../outside.md", action="append", content="# Outside")

    with pytest.raises(LoreEditError, match="summary and keywords"):
        await workspace.edit_lore(filename="setting.md", action="append", content="New detail")

    with pytest.raises(LoreEditError, match="does not exist"):
        await workspace.read_lore(filename="setting.md")

    with pytest.raises(LoreEditError, match="summary and keywords"):
        await workspace.edit_lore(filename="invalid.md", action="append", content="---\nsummary: Missing keywords\n---\nContent")

    await workspace.edit_lore(filename="setting.md", action="append", content="---\nsummary: S\nkeywords: k\n---\nText")
    with pytest.raises(LoreEditError, match="Invalid edit range"):
        await workspace.edit_lore(filename="setting.md", action="replace", content="x", start_offset=999)


@pytest.mark.asyncio
async def test_workspace_persists_complete_conversation_history(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    tool_call_id = "call-123"
    history = [
        ModelRequest(parts=[UserPromptPart(content="Add an opening.")]),
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="edit_script",
                    args={"start_offset": 0, "end_offset": 0, "replacement": "FADE IN:"},
                    tool_call_id=tool_call_id,
                )
            ]
        ),
        ModelRequest(
            parts=[ToolReturnPart(tool_name="edit_script", content="Updated script.", tool_call_id=tool_call_id)]
        ),
        ModelResponse(parts=[TextPart(content="Added an opening.")]),
    ]

    await workspace.write_message_history(message_history=history)
    restored_history = await FileWorkspace(tmp_path).read_message_history()

    assert restored_history == history
    assert (tmp_path / CONVERSATION_HISTORY_FILENAME).is_file()


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
