"""Tests for the writer agent's workspace-only edit tool."""

import pytest
from pydantic_ai import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from storyline.agent.writer import create_writer_agent
from storyline.workspace.file import FileWorkspace


@pytest.mark.asyncio
async def test_writer_agent_exposes_workspace_tools_and_applies_a_range_edit(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    observed_tool_names: list[list[str]] = []
    observed_tool_descriptions: list[list[str | None]] = []

    def model_response(_, info: AgentInfo) -> ModelResponse:
        observed_tool_names.append([tool.name for tool in info.function_tools])
        observed_tool_descriptions.append([tool.description for tool in info.function_tools])
        if len(observed_tool_names) == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="edit_script",
                        args={"start_offset": 0, "end_offset": 0, "replacement": "FADE IN:"},
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content="Added an opening.")])

    agent = create_writer_agent()
    result = await agent.run("Add an opening.", deps=workspace, model=FunctionModel(model_response))

    assert result.output == "Added an opening."
    assert observed_tool_names == [
        ["edit_script", "list_lore", "read_lore", "edit_lore"],
        ["edit_script", "list_lore", "read_lore", "edit_lore"],
    ]
    assert observed_tool_descriptions == [
        [
            "Replace a character range in the story text without resending unchanged text.\nAfter an edit, briefly state what changed.",
            "List every lore file with its short summary from the metadata header.",
            "Read the full text of one Markdown lore file beside script.md.",
            "Append to, replace within, or delete a Markdown lore file.\n\nLore files require a hyphen-delimited metadata header with non-empty summary and keywords properties.",
        ],
        [
            "Replace a character range in the story text without resending unchanged text.\nAfter an edit, briefly state what changed.",
            "List every lore file with its short summary from the metadata header.",
            "Read the full text of one Markdown lore file beside script.md.",
            "Append to, replace within, or delete a Markdown lore file.\n\nLore files require a hyphen-delimited metadata header with non-empty summary and keywords properties.",
        ],
    ]
    assert await workspace.read_script() == "FADE IN:"


@pytest.mark.asyncio
async def test_writer_agent_returns_workspace_errors_to_the_model(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    observed_failures: list[ToolReturnPart] = []

    def model_response(messages, _) -> ModelResponse:
        for message in messages:
            if isinstance(message, ModelRequest):
                observed_failures.extend(
                    part for part in message.parts if isinstance(part, ToolReturnPart) and part.outcome == "failed"
                )
        if not observed_failures:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="edit_script",
                        args={"start_offset": 1, "end_offset": 1, "replacement": "FADE IN:"},
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content="I could not apply that edit.")])

    agent = create_writer_agent()
    result = await agent.run("Add an opening.", deps=workspace, model=FunctionModel(model_response))

    assert result.output == "I could not apply that edit."
    assert len(observed_failures) == 1
    assert "Invalid edit range 1:1" in str(observed_failures[0].content)


@pytest.mark.asyncio
async def test_writer_agent_accepts_an_omitted_end_offset(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    await workspace.apply_edit(start_offset=0, end_offset=0, replacement="abc")
    call_count = 0

    def model_response(_, __) -> ModelResponse:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="edit_script",
                        args={"start_offset": 1, "replacement": "B"},
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content="Updated the middle character.")])

    agent = create_writer_agent()
    result = await agent.run("Uppercase the middle character.", deps=workspace, model=FunctionModel(model_response))

    assert result.output == "Updated the middle character."
    assert await workspace.read_script() == "aBc"


@pytest.mark.asyncio
async def test_writer_agent_deletes_lore_without_content(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    lore_content = "---\nsummary: A setting.\nkeywords: city\n---\nRainy streets."
    await workspace.edit_lore(filename="setting.md", action="append", content=lore_content)
    call_count = 0

    def model_response(_, __) -> ModelResponse:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ModelResponse(
                parts=[ToolCallPart(tool_name="edit_lore", args={"filename": "setting", "action": "delete"})]
            )
        return ModelResponse(parts=[TextPart(content="Removed the lore file.")])

    agent = create_writer_agent()
    result = await agent.run("Remove the setting lore.", deps=workspace, model=FunctionModel(model_response))

    assert result.output == "Removed the lore file."
    assert await workspace.list_lore() == ()
