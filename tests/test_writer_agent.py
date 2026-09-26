"""Tests for the writer agent's workspace tools and per-turn story context."""

from collections.abc import Callable

import pytest
from pydantic_ai import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.messages import ModelMessage, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from storyline.agent import create_writer_agent, story_snapshot, turn_prompt, visible_prompt_text
from storyline.agent.story_context import SNAPSHOT_OPEN, TAIL_CHARACTERS
from storyline.workspace.file import FileWorkspace

LORE_HEADER = "---\nsummary: A setting.\nkeywords: city\n---\n"

type ModelFunction = Callable[[list[ModelMessage], AgentInfo], ModelResponse]


def _call_tools_then_reply(*calls: ToolCallPart) -> tuple[ModelFunction, list[ToolReturnPart]]:
    """Return a model that makes each tool call in turn, then replies; and the tool results it saw."""
    results: list[ToolReturnPart] = []

    def model_response(messages: list[ModelMessage], _: AgentInfo) -> ModelResponse:
        results[:] = [
            part
            for message in messages
            if isinstance(message, ModelRequest)
            for part in message.parts
            if isinstance(part, ToolReturnPart)
        ]
        if len(results) < len(calls):
            return ModelResponse(parts=[calls[len(results)]])
        return ModelResponse(parts=[TextPart(content="Done.")])

    return model_response, results


@pytest.mark.asyncio
async def test_writer_agent_exposes_the_anchored_editing_tools(tmp_path) -> None:
    observed_tool_names: list[str] = []

    def model_response(_: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        observed_tool_names.extend(tool.name for tool in info.function_tools)
        return ModelResponse(parts=[TextPart(content="Ready.")])

    await create_writer_agent().run("Hi.", deps=FileWorkspace(tmp_path), model=FunctionModel(model_response))

    assert observed_tool_names == [
        "append_to_script",
        "edit_script",
        "read_script",
        "list_lore",
        "read_lore",
        "write_lore",
        "append_lore",
        "edit_lore",
        "delete_lore",
    ]


@pytest.mark.asyncio
async def test_writer_agent_appends_and_revises_the_story_by_excerpt(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    model, results = _call_tools_then_reply(
        ToolCallPart(tool_name="append_to_script", args={"text": "FADE IN:\n\nA quiet street."}),
        ToolCallPart(tool_name="edit_script", args={"find": "quiet", "replace": "rain-soaked"}),
    )

    result = await create_writer_agent().run("Write an opening.", deps=workspace, model=FunctionModel(model))

    assert result.output == "Done."
    assert await workspace.read_script() == "FADE IN:\n\nA rain-soaked street."
    assert [part.outcome for part in results] == ["success", "success"]
    assert "rain-soaked" in str(results[-1].content)


@pytest.mark.asyncio
async def test_writer_agent_returns_workspace_errors_to_the_model(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    await workspace.append_script(text="The bell rang. The bell rang again.")
    model, results = _call_tools_then_reply(
        ToolCallPart(tool_name="edit_script", args={"find": "The bell rang", "replace": "A bell tolled"}),
    )

    result = await create_writer_agent().run("Revise.", deps=workspace, model=FunctionModel(model))

    assert result.output == "Done."
    assert results[0].outcome == "failed"
    assert "matches 2 places" in str(results[0].content)


@pytest.mark.asyncio
async def test_writer_agent_reads_story_paragraph_ranges(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    await workspace.append_script(text="One.\n\nTwo.\n\nThree.")
    model, results = _call_tools_then_reply(
        ToolCallPart(tool_name="read_script", args={"from_paragraph": 2, "to_paragraph": 9}),
        ToolCallPart(tool_name="read_script", args={"from_paragraph": 5}),
    )

    await create_writer_agent().run("Read.", deps=workspace, model=FunctionModel(model))

    assert results[0].content == "Paragraphs 2-3 of 3:\n\nTwo.\n\nThree."
    assert results[1].outcome == "failed"


@pytest.mark.asyncio
async def test_writer_agent_manages_lore_files(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    model, results = _call_tools_then_reply(
        ToolCallPart(tool_name="write_lore", args={"filename": "setting", "content": f"{LORE_HEADER}Rainy streets."}),
        ToolCallPart(tool_name="edit_lore", args={"filename": "setting.md", "find": "Rainy", "replace": "Foggy"}),
        ToolCallPart(tool_name="append_lore", args={"filename": "setting.md", "text": "\nNeon signs."}),
    )

    await create_writer_agent().run("Describe the city.", deps=workspace, model=FunctionModel(model))

    assert [part.outcome for part in results] == ["success", "success", "success"]
    assert await workspace.read_lore(filename="setting.md") == f"{LORE_HEADER}Foggy streets.\nNeon signs."

    delete_model, delete_results = _call_tools_then_reply(
        ToolCallPart(tool_name="delete_lore", args={"filename": "setting.md"}),
    )
    await create_writer_agent().run("Remove it.", deps=workspace, model=FunctionModel(delete_model))

    assert delete_results[0].outcome == "success"
    assert await workspace.list_lore() == ()


@pytest.mark.asyncio
async def test_story_travels_in_the_turn_prompt_not_the_instructions(tmp_path) -> None:
    workspace = FileWorkspace(tmp_path)
    await workspace.append_script(text="A distinctive opening line.")
    observed: list[tuple[str | None, list[ModelMessage]]] = []

    def model_response(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        observed.append((info.instructions, messages))
        return ModelResponse(parts=[TextPart(content="Noted.")])

    prompt = await turn_prompt(workspace, "Continue.")
    await create_writer_agent().run(prompt, deps=workspace, model=FunctionModel(model_response))

    instructions, messages = observed[0]
    user_part = next(part for part in messages[-1].parts if isinstance(part, UserPromptPart))
    assert "A distinctive opening line." not in (instructions or "")
    assert "A distinctive opening line." in str(user_part.content)
    assert visible_prompt_text(user_part.content) == "Continue."


def test_story_snapshot_is_bounded_and_lists_headings() -> None:
    story = "# Act One\n\n" + "\n\n".join(f"Paragraph {index} " + "x" * 200 for index in range(1, 60))

    snapshot = story_snapshot(story)

    assert snapshot.startswith(SNAPSHOT_OPEN)
    assert "60 paragraphs" in snapshot
    assert "¶1 # Act One" in snapshot
    assert "Paragraph 59" in snapshot
    assert "Paragraph 2 " not in snapshot
    assert len(snapshot) < TAIL_CHARACTERS + 500


def test_story_snapshot_cuts_one_oversized_final_paragraph() -> None:
    snapshot = story_snapshot("Start." + "y" * (TAIL_CHARACTERS * 2))

    assert "Start." not in snapshot
    assert len(snapshot) < TAIL_CHARACTERS + 300


def test_story_snapshot_of_an_empty_story() -> None:
    assert "The story is empty." in story_snapshot("")
