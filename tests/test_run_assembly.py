"""Tests for how a story's preset is assembled into each writer run."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic_ai import ModelResponse, TextPart
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel

from storyline.agent import WRITER_INSTRUCTIONS, WritingSession, assemble, create_writer_agent
from storyline.agent.writer import WRITER_SKILLS_PATH
from storyline.presets import BUNDLED_PRESETS, DEFAULT_PRESET_ID, Preset, load_presets
from storyline.workspace import StorySetup, StorySetupError
from storyline.workspace.file_story import SETUP_FILENAME, FileStory

IN_CHARACTER_PHRASE = "speak or act as one of the characters"
CORE_SKILLS = ("assess-request", "research", "develop-element", "outline", "write-scene", "revise")


def _skill(root: Path, name: str, description: str) -> None:
    (root / name).mkdir(parents=True)
    (root / name / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {description}\n---\nDo the {name} work.\n", encoding="utf-8")


def _core_description(name: str) -> str:
    header = (WRITER_SKILLS_PATH / name / "SKILL.md").read_text(encoding="utf-8").split("---\n", 2)[1]
    return next(line.removeprefix("description:").strip() for line in header.splitlines() if line.startswith("description:"))


def _preset_with_skills(tmp_path: Path) -> Preset:
    preset_dir = tmp_path / "presets" / "tabletop"
    preset_dir.mkdir(parents=True)
    (preset_dir / "preset.md").write_text("---\nname: tabletop\ntitle: Tabletop\ndescription: A game.\nmechanics: []\n---\nThe tabletop layer.\n", encoding="utf-8")
    _skill(preset_dir / "skills", "write-scene", "Scene writing for the tabletop preset.")
    _skill(preset_dir / "skills", "cast-sheet", "Make a cast sheet.")
    return load_presets(tmp_path / "presets").get("tabletop")


def _recorder(seen: list[str]) -> FunctionModel:
    def respond(_: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.append(str(info.instructions))
        return ModelResponse(parts=[TextPart(content="Ready.")])

    respond_model: Callable[[list[ModelMessage], AgentInfo], ModelResponse] = respond
    return FunctionModel(respond_model)


async def _run_assembled(preset: Preset, tmp_path: Path) -> str:
    seen: list[str] = []
    assembly = assemble(preset)
    await create_writer_agent().run("Hi.", deps=FileStory(tmp_path / "story"), model=_recorder(seen), instructions=assembly.instructions, capabilities=list(assembly.capabilities))
    return seen[0]


@pytest.mark.asyncio
async def test_a_co_writing_session_sends_the_core_then_the_layer_and_every_core_skill(tmp_path: Path) -> None:
    story = FileStory(tmp_path)
    seen: list[str] = []
    session = await WritingSession.open(story=story, agent=create_writer_agent(), default_model_name="openrouter:x/y", model=_recorder(seen))

    await session.turn("Hi.").run()

    layer = BUNDLED_PRESETS.get(DEFAULT_PRESET_ID).layer
    assert session.preset_id == DEFAULT_PRESET_ID
    assert WRITER_INSTRUCTIONS in seen[0] and layer in seen[0]
    assert seen[0].index(WRITER_INSTRUCTIONS) < seen[0].index(layer)
    for name in CORE_SKILLS:
        assert _core_description(name) in seen[0]


@pytest.mark.asyncio
async def test_the_moved_guidance_is_in_the_layer_and_not_in_the_core(tmp_path: Path) -> None:
    assert IN_CHARACTER_PHRASE not in WRITER_INSTRUCTIONS
    assert IN_CHARACTER_PHRASE in BUNDLED_PRESETS.get(DEFAULT_PRESET_ID).layer

    instructions = await _run_assembled(BUNDLED_PRESETS.get(DEFAULT_PRESET_ID), tmp_path)

    assert instructions.count(IN_CHARACTER_PHRASE) == 1


@pytest.mark.asyncio
async def test_a_preset_skill_replaces_the_core_skill_of_the_same_name_and_adds_new_ones(tmp_path: Path) -> None:
    instructions = await _run_assembled(_preset_with_skills(tmp_path), tmp_path)

    assert "Scene writing for the tabletop preset." in instructions
    assert _core_description("write-scene") not in instructions
    assert "Make a cast sheet." in instructions
    assert "The tabletop layer." in instructions
    for name in CORE_SKILLS:
        if name != "write-scene":
            assert _core_description(name) in instructions


@pytest.mark.asyncio
async def test_a_session_uses_the_preset_its_story_names(tmp_path: Path) -> None:
    preset = _preset_with_skills(tmp_path)
    (tmp_path / "story").mkdir()
    story = FileStory(tmp_path / "story")
    await story.write_setup(setup=StorySetup(preset="tabletop"))
    seen: list[str] = []

    session = await WritingSession.open(story=story, agent=create_writer_agent(), model=_recorder(seen), presets=load_presets(tmp_path / "presets"))
    await session.turn("Hi.").run()

    assert session.preset_id == preset.id
    assert "The tabletop layer." in seen[0]
    assert BUNDLED_PRESETS.get(DEFAULT_PRESET_ID).layer not in seen[0]


@pytest.mark.asyncio
async def test_a_story_naming_an_unknown_preset_fails_to_open(tmp_path: Path) -> None:
    story = FileStory(tmp_path)
    await story.write_setup(setup=StorySetup(preset="no-such-preset"))

    with pytest.raises(StorySetupError, match="no-such-preset"):
        await WritingSession.open(story=story, agent=create_writer_agent())


@pytest.mark.asyncio
async def test_a_story_with_an_unreadable_setup_fails_to_open(tmp_path: Path) -> None:
    (tmp_path / SETUP_FILENAME).write_text("{not json", encoding="utf-8")

    with pytest.raises(StorySetupError, match=SETUP_FILENAME):
        await WritingSession.open(story=FileStory(tmp_path), agent=create_writer_agent())


@pytest.mark.asyncio
async def test_story_setup_round_trips_through_story_json(tmp_path: Path) -> None:
    story = FileStory(tmp_path)
    assert await story.read_setup() == StorySetup()

    await story.write_setup(setup=StorySetup(preset="roleplay", mechanics=("clocks", "oracle")))

    assert await story.read_setup() == StorySetup(preset="roleplay", mechanics=("clocks", "oracle"))
    assert json.loads((tmp_path / SETUP_FILENAME).read_text(encoding="utf-8"))["preset"] == "roleplay"
    assert await story.list_lore() == ()
