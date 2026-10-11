"""Tests for the writer's core prompt, its skills and how they are wired into the agent."""

from pathlib import Path

import pytest
import yaml
from pydantic_ai import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel

from storyline.agent import WRITER_INSTRUCTIONS, create_writer_agent
from storyline.agent.writer import WRITER_MAX_OUTPUT_TOKENS, WRITER_SKILLS_PATH
from storyline.workspace.file_story import FileStory

SKILL_NAMES = ("assess-request", "research", "develop-element", "outline", "write-scene", "revise")


def _skill_files() -> list[Path]:
    return sorted(WRITER_SKILLS_PATH.glob("*/SKILL.md"))


def _frontmatter(path: Path) -> tuple[dict[str, object], str]:
    _, header, body = path.read_text(encoding="utf-8").split("---\n", 2)
    parsed = yaml.safe_load(header)
    assert isinstance(parsed, dict)
    return parsed, body


def test_every_expected_skill_exists_with_matching_frontmatter() -> None:
    assert [path.parent.name for path in _skill_files()] == sorted(SKILL_NAMES)
    for path in _skill_files():
        header, body = _frontmatter(path)
        assert header["name"] == path.parent.name
        assert isinstance(header["description"], str) and header["description"].strip()
        assert body.strip()


def test_core_prompt_names_the_fixed_role_files_and_agenda_tools() -> None:
    for expected in ("script.md", "plan.md", "style.md", "collaboration.md", "set_agenda", "update_agenda_item", "load_capability"):
        assert expected in WRITER_INSTRUCTIONS


def test_core_prompt_points_at_every_skill() -> None:
    for name in SKILL_NAMES:
        assert name in WRITER_INSTRUCTIONS


@pytest.mark.asyncio
async def test_writer_offers_load_capability_with_each_skill_in_the_catalog(tmp_path: Path) -> None:
    tool_names: list[str] = []
    catalog: list[str] = []

    def respond(_: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        tool_names[:] = [tool.name for tool in info.function_tools]
        catalog[:] = [str(info.instructions)]
        return ModelResponse(parts=[TextPart(content="Ready.")])

    await create_writer_agent().run("Hi.", deps=FileStory(tmp_path), model=FunctionModel(respond))

    assert "load_capability" in tool_names
    for name in SKILL_NAMES:
        header, _ = _frontmatter(WRITER_SKILLS_PATH / name / "SKILL.md")
        assert str(header["description"]) in catalog[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("name", SKILL_NAMES)
async def test_loading_a_skill_returns_its_instructions(tmp_path: Path, name: str) -> None:
    returned: list[str] = []

    def respond(messages: list[ModelMessage], _: AgentInfo) -> ModelResponse:
        returned[:] = [str(part.content) for message in messages if isinstance(message, ModelRequest) for part in message.parts if isinstance(part, ToolReturnPart)]
        if not returned:
            return ModelResponse(parts=[ToolCallPart(tool_name="load_capability", args={"id": name})])
        return ModelResponse(parts=[TextPart(content="Loaded.")])

    await create_writer_agent().run("Hi.", deps=FileStory(tmp_path), model=FunctionModel(respond))

    _, body = _frontmatter(WRITER_SKILLS_PATH / name / "SKILL.md")
    assert returned
    assert body.strip().splitlines()[0] in returned[0]


@pytest.mark.asyncio
async def test_writer_caps_output_tokens(tmp_path: Path) -> None:
    observed: list[int | None] = []

    def respond(_: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        observed.append(info.model_settings.get("max_tokens") if info.model_settings else None)
        return ModelResponse(parts=[TextPart(content="Ready.")])

    await create_writer_agent().run("Hi.", deps=FileStory(tmp_path), model=FunctionModel(respond))

    assert observed == [WRITER_MAX_OUTPUT_TOKENS]


@pytest.mark.asyncio
async def test_custom_instructions_still_replace_the_core_prompt(tmp_path: Path) -> None:
    seen: list[str] = []

    def respond(_: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.append(str(info.instructions))
        return ModelResponse(parts=[TextPart(content="Ready.")])

    await create_writer_agent(instructions="Variant prompt.").run("Hi.", deps=FileStory(tmp_path), model=FunctionModel(respond))

    assert "Variant prompt." in seen[0]
    assert WRITER_INSTRUCTIONS not in seen[0]
