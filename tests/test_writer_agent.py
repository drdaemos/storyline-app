"""Tests for the writer agent's workspace tools and per-turn story context."""

from collections.abc import Callable

import pytest
from pydantic_ai import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.messages import ModelMessage, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.native_tools import WebSearchTool

from storyline.agent import WRITER_INSTRUCTIONS, assemble, create_writer_agent, prompt_version, story_snapshot, turn_prompt, visible_prompt_text
from storyline.agent.story_context import GUIDE_CHARACTERS, SNAPSHOT_OPEN, TAIL_CHARACTERS
from storyline.agent.writer import WRITER_PROMPT_PATH
from storyline.presets import BUNDLED_PRESETS, DEFAULT_PRESET_ID
from storyline.workspace import LoreFile
from storyline.workspace.file_story import FileStory

LORE_HEADER = "---\nsummary: A setting.\nkeywords: city\n---\n"

type ModelFunction = Callable[[list[ModelMessage], AgentInfo], ModelResponse]


def _call_tools_then_reply(*calls: ToolCallPart) -> tuple[ModelFunction, list[ToolReturnPart]]:
    """Return a model that makes each tool call in turn, then replies; and the tool results it saw."""
    results: list[ToolReturnPart] = []

    def model_response(messages: list[ModelMessage], _: AgentInfo) -> ModelResponse:
        results[:] = [part for message in messages if isinstance(message, ModelRequest) for part in message.parts if isinstance(part, ToolReturnPart)]
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

    assembly = assemble(BUNDLED_PRESETS.get(DEFAULT_PRESET_ID))
    await create_writer_agent().run("Hi.", deps=FileStory(tmp_path), model=FunctionModel(model_response), capabilities=list(assembly.capabilities))

    assert observed_tool_names == [
        "load_capability",
        "append_to_script",
        "edit_script",
        "read_script",
        "list_lore",
        "read_lore",
        "write_lore",
        "append_lore",
        "edit_lore",
        "delete_lore",
        "enable_mechanic",
        "set_agenda",
        "update_agenda_item",
    ]


@pytest.mark.asyncio
async def test_writer_agent_offers_web_search(tmp_path) -> None:
    observed_native_tools: list[object] = []

    def model_response(_: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        observed_native_tools.extend(info.model_request_parameters.native_tools)
        return ModelResponse(parts=[TextPart(content="Ready.")])

    await create_writer_agent().run("Hi.", deps=FileStory(tmp_path), model=FunctionModel(model_response))

    assert any(isinstance(tool, WebSearchTool) for tool in observed_native_tools)


@pytest.mark.asyncio
async def test_writer_agent_appends_and_revises_the_story_by_excerpt(tmp_path) -> None:
    workspace = FileStory(tmp_path)
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
    workspace = FileStory(tmp_path)
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
    workspace = FileStory(tmp_path)
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
    workspace = FileStory(tmp_path)
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
    workspace = FileStory(tmp_path)
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
    assert len(snapshot) < TAIL_CHARACTERS + 450


def test_story_snapshot_of_an_empty_story() -> None:
    assert "The story is empty." in story_snapshot("")


def test_story_snapshot_lists_lore_and_shows_plan_and_style_guide() -> None:
    lore = (
        LoreFile(filename="ines.md", summary="The point-of-view character.", keywords="Ines"),
        LoreFile(filename="plan.md", summary="The plan.", keywords="plan"),
    )

    snapshot = story_snapshot("Opening.", lore=lore, guides={"plan.md": "Next: the storm."})

    assert "- ines.md: The point-of-view character." in snapshot
    assert "Next: the storm." in snapshot
    assert "style.md does not exist yet." in snapshot


def test_story_snapshot_cuts_an_oversized_guide() -> None:
    snapshot = story_snapshot("Opening.", guides={"plan.md": "p" * (GUIDE_CHARACTERS * 2)})

    assert "read_lore shows the rest" in snapshot
    assert len(snapshot) < GUIDE_CHARACTERS + TAIL_CHARACTERS + 500


@pytest.mark.asyncio
async def test_turn_prompt_carries_guides_without_their_metadata_header(tmp_path) -> None:
    story = FileStory(tmp_path)
    await story.write_lore(filename="plan.md", content="---\nsummary: The plan.\nkeywords: plan\n---\nScene one: arrival.")
    await story.write_lore(filename="style.md", content="---\nsummary: Style guide.\nkeywords: style\n---\nKeep it plain.")

    snapshot = (await turn_prompt(story, "Continue."))[0]

    assert "Scene one: arrival." in snapshot
    assert "Keep it plain." in snapshot
    assert "keywords: plan" not in snapshot


@pytest.mark.asyncio
async def test_writer_agent_runs_with_the_given_instructions(tmp_path) -> None:
    observed: list[str | None] = []

    def model_response(_: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        observed.append(info.instructions)
        return ModelResponse(parts=[TextPart(content="Ready.")])

    await create_writer_agent(instructions="Write only haiku.").run("Hi.", deps=FileStory(tmp_path), model=FunctionModel(model_response))

    assert len(observed) == 1
    assert observed[0] is not None and observed[0].startswith("Write only haiku.")


def test_default_instructions_come_from_the_prompt_file() -> None:
    assert WRITER_INSTRUCTIONS == WRITER_PROMPT_PATH.read_text(encoding="utf-8")
    assert WRITER_INSTRUCTIONS.strip()


def test_prompt_version_identifies_the_instructions() -> None:
    assert prompt_version("A prompt.") == prompt_version("A prompt.")
    assert prompt_version("A prompt.") != prompt_version("Another prompt.")
