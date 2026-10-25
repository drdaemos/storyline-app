"""Tests for mechanics: resolving them, assembling them into a run, sealing tool calls and enabling them in a story."""

from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic_ai import FunctionToolset, ModelResponse, RunContext, TextPart, ToolCallPart
from pydantic_ai.messages import ModelMessage, ModelRequest, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from storyline.agent import WRITER_INSTRUCTIONS, TurnOutcome, WritingSession, assemble, create_writer_agent, story_snapshot, tool_call_is_sealed, turn_prompt
from storyline.agent.writer_tools import mechanic_toolset
from storyline.mechanics import Mechanic, MechanicError, SealedMechanic, resolve_mechanics
from storyline.presets import BUNDLED_PRESETS, DEFAULT_PRESET_ID, PresetError, load_presets, setup_for
from storyline.registry import MECHANICS
from storyline.workspace import LoreFile, Story, StoryLibrary, StorySetup, StorySetupError
from storyline.workspace.file_story import SETUP_FILENAME, FileStory
from storyline.workspace.file_workspace import FileWorkspace

LORE = "---\nsummary: {summary}\nkeywords: k\n---\nBody.\n"
CO_WRITING = BUNDLED_PRESETS.get(DEFAULT_PRESET_ID)


def _mechanic(tmp_path: Path, mechanic_id: str, *, requires: tuple[str, ...] = (), with_tool: bool = False, with_skill: bool = False, sealed_tool: str | None = None) -> Mechanic:
    """A mechanic of this id with a prompt section, optionally a tool called ``<id>_tool`` and a skill called ``<id>-skill``."""
    directory = tmp_path / f"mechanic-{mechanic_id}"
    directory.mkdir(parents=True, exist_ok=True)
    prompt_path = directory / "prompt.md"
    prompt_path.write_text(f"Section of {mechanic_id}.\n", encoding="utf-8")
    skills_dir = directory / "skills"
    if with_skill:
        (skills_dir / f"{mechanic_id}-skill").mkdir(parents=True)
        (skills_dir / f"{mechanic_id}-skill" / "SKILL.md").write_text(f"---\nname: {mechanic_id}-skill\ndescription: Skill of {mechanic_id}.\n---\nDo it.\n", encoding="utf-8")
    toolset = FunctionToolset[Story]()
    if with_tool:

        async def tool(ctx: RunContext[Story]) -> str:
            return f"{mechanic_id} used"

        toolset.add_function(tool, name=f"{mechanic_id}_tool")

    async def snapshot_section(self: Mechanic, story: Story) -> list[str]:
        return [f"Section lines of {mechanic_id}."]

    def seals(self: Mechanic, tool_name: str, arguments: Mapping[str, object]) -> bool:
        return tool_name == sealed_tool

    attributes: dict[str, object] = {
        "id": mechanic_id,
        "description": f"Does {mechanic_id}.",
        "requires": requires,
        "prompt_path": prompt_path,
        "toolset": toolset if with_tool else None,
        "skills_dir": skills_dir if with_skill else None,
        "snapshot_section": snapshot_section,
        "seals": seals,
    }
    return type(f"{mechanic_id.title()}Mechanic", (Mechanic,), attributes)()


def _registry(*mechanics: Mechanic) -> dict[str, Mechanic]:
    return {mechanic.id: mechanic for mechanic in mechanics}


class Recorder:
    """A fake writer model: calls the given tool once on the first request of each turn, then replies; records what it was given."""

    def __init__(self, tool_call: ToolCallPart | None = None) -> None:
        self.tool_call = tool_call
        self.instructions: list[str] = []
        self.tools: list[list[str]] = []
        self.prompts: list[str] = []
        self.model = FunctionModel(self._respond)

    def _respond(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.instructions.append(str(info.instructions))
        self.tools.append([tool.name for tool in info.function_tools])
        self.prompts.append("\n".join(str(part.content) for message in messages if isinstance(message, ModelRequest) for part in message.parts if isinstance(part, UserPromptPart)))
        returned = any(isinstance(part, ToolReturnPart) for message in messages[-1:] for part in message.parts)
        if self.tool_call is not None and not returned and self.tool_call.tool_name in self.tools[-1]:
            return ModelResponse(parts=[ToolCallPart(tool_name=self.tool_call.tool_name, args=self.tool_call.args)])
        return ModelResponse(parts=[TextPart(content="Done.")])


# Resolving


def test_resolving_puts_requirements_first_and_each_mechanic_once(tmp_path: Path) -> None:
    registry = _registry(_mechanic(tmp_path, "a", requires=("b",)), _mechanic(tmp_path, "b", requires=("c",)), _mechanic(tmp_path, "c"))

    resolved = resolve_mechanics(["a", "c", "a"], registry)

    assert [mechanic.id for mechanic in resolved] == ["c", "b", "a"]


def test_resolving_an_unknown_mechanic_names_it_and_the_known_ones(tmp_path: Path) -> None:
    registry = _registry(_mechanic(tmp_path, "a"))

    with pytest.raises(MechanicError, match="ghost") as error:
        resolve_mechanics(["ghost"], registry)

    assert "a" in str(error.value)


def test_resolving_an_unknown_requirement_is_refused(tmp_path: Path) -> None:
    registry = _registry(_mechanic(tmp_path, "a", requires=("missing",)))

    with pytest.raises(MechanicError, match="missing"):
        resolve_mechanics(["a"], registry)


def test_resolving_a_cycle_is_refused(tmp_path: Path) -> None:
    registry = _registry(_mechanic(tmp_path, "a", requires=("b",)), _mechanic(tmp_path, "b", requires=("a",)))

    with pytest.raises(MechanicError):
        resolve_mechanics(["a"], registry)


def test_the_bundled_registry_has_the_sealed_mechanic() -> None:
    sealed = MECHANICS["sealed"]

    assert isinstance(sealed, SealedMechanic)
    assert sealed.description.strip() and sealed.prompt.strip()
    assert sealed.toolset is None


# Assembly


@pytest.mark.asyncio
async def test_assembly_puts_each_mechanics_section_after_the_preset_layer_and_lists_their_skills_and_tools(tmp_path: Path) -> None:
    first = _mechanic(tmp_path, "first", with_tool=True, with_skill=True)
    second = _mechanic(tmp_path, "second")
    assembly = assemble(CO_WRITING, (first, second))
    seen = Recorder(ToolCallPart(tool_name="first_tool", args={}))

    await create_writer_agent().run(
        "Hi.",
        deps=FileStory(tmp_path / "story"),
        model=seen.model,
        instructions=assembly.instructions,
        capabilities=list(assembly.capabilities),
        toolsets=list(assembly.toolsets),
    )

    instructions = seen.instructions[0]
    assert instructions.index(CO_WRITING.layer) < instructions.index("Section of first.") < instructions.index("Section of second.")
    assert assembly.instructions.startswith(CO_WRITING.layer)
    assert "Skill of first." in instructions
    assert "first_tool" in seen.tools[0]
    assert len(seen.tools) == 2


def test_assembly_without_mechanics_is_the_preset_layer_alone() -> None:
    assembly = assemble(CO_WRITING)

    assert assembly.instructions == CO_WRITING.layer
    assert assembly.toolsets == ()


def test_a_mechanic_without_a_prompt_adds_no_blank_section(tmp_path: Path) -> None:
    class Silent(Mechanic):
        id = "silent"
        description = "Says nothing."

    assert assemble(CO_WRITING, (Silent(),)).instructions == CO_WRITING.layer


# Sealing tool calls


@pytest.mark.parametrize("tool_name", ["read_lore", "write_lore", "append_lore", "edit_lore", "delete_lore"])
@pytest.mark.parametrize("filename", ["sealed/vera.md", "sealed\\vera.md", "  sealed/vera  "])
def test_a_core_lore_tool_on_a_sealed_file_is_sealed_whatever_the_mechanics(tool_name, filename) -> None:
    assert tool_call_is_sealed(tool_name, {"filename": filename}, ()) is True


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [("read_lore", {"filename": "city.md"}), ("read_lore", {"filename": 3}), ("read_lore", {}), ("write_lore", {"filename": "sealed.md"}), ("append_to_script", {"text": "sealed/vera.md"}), ("list_lore", {})],
)
def test_other_core_calls_are_not_sealed(tool_name, arguments) -> None:
    assert tool_call_is_sealed(tool_name, arguments, ()) is False


def test_a_lore_call_with_unparseable_arguments_naming_the_sealed_folder_is_sealed() -> None:
    broken = ToolCallPart(tool_name="write_lore", args='{"filename": "sealed\\\\vera.md", "content": "She lies')

    assert tool_call_is_sealed("write_lore", broken.args_as_dict(), ()) is True
    assert tool_call_is_sealed("write_lore", ToolCallPart(tool_name="write_lore", args='{"filename": "city.md", ').args_as_dict(), ()) is False


def test_a_mechanic_can_seal_a_call_of_its_own(tmp_path: Path) -> None:
    mechanic = _mechanic(tmp_path, "secret", sealed_tool="secret_roll")

    assert tool_call_is_sealed("secret_roll", {}, (mechanic,)) is True
    assert tool_call_is_sealed("other_tool", {}, (mechanic,)) is False


def test_listing_the_lore_is_sealed_only_in_a_story_with_the_sealed_mechanic() -> None:
    assert tool_call_is_sealed("list_lore", {}, (MECHANICS["sealed"],)) is True
    assert tool_call_is_sealed("list_lore", {}, ()) is False


# The story snapshot


def test_the_snapshot_marks_sealed_lore_as_hidden_from_the_user() -> None:
    lore = (LoreFile("city.md", "The city.", "city"), LoreFile("sealed/vera.md", "What Vera wants.", "vera", sealed=True))

    snapshot = story_snapshot("Opening.", lore=lore, registry=MECHANICS)

    [city] = [line for line in snapshot.splitlines() if "city.md" in line]
    [vera] = [line for line in snapshot.splitlines() if "sealed/vera.md" in line]
    assert "sealed" not in city
    assert "sealed" in vera and "hidden" in vera and "What Vera wants." in vera


def test_the_snapshot_names_the_mechanics_in_use_and_those_that_could_be_enabled(tmp_path: Path) -> None:
    used, other = _mechanic(tmp_path, "used"), _mechanic(tmp_path, "other")

    snapshot = story_snapshot("Opening.", mechanics=(used,), registry=_registry(used, other))
    plain = story_snapshot("Opening.", registry=_registry(used, other))

    in_use = next(line for line in snapshot.splitlines() if "in use" in line)
    assert "used" in in_use
    assert "- other: Does other." in snapshot
    assert "- used: Does used." not in snapshot
    assert "none" in next(line for line in plain.splitlines() if "in use" in line)
    assert "- used: Does used." in plain


@pytest.mark.asyncio
async def test_each_mechanics_snapshot_lines_come_in_mechanic_order_before_the_agenda(tmp_path: Path) -> None:
    first, second = _mechanic(tmp_path, "first"), _mechanic(tmp_path, "second")
    story = FileStory(tmp_path / "story")

    prompt = await turn_prompt(story, "Go.", (first, second), registry=_registry(first, second))

    snapshot = str(prompt[0])
    assert snapshot.index("Section lines of first.") < snapshot.index("Section lines of second.") < snapshot.index("Agenda:")
    assert snapshot.index("style.md") < snapshot.index("Section lines of first.")
    assert prompt[1] == "Go."


# Setup per turn


@pytest.mark.asyncio
async def test_a_story_naming_an_unknown_mechanic_fails_to_open(tmp_path: Path) -> None:
    story = FileStory(tmp_path)
    await story.write_setup(setup=StorySetup(mechanics=("ghost",)))

    with pytest.raises(StorySetupError, match="ghost"):
        await WritingSession.open(story=story, agent=create_writer_agent(), registry=MECHANICS)


@pytest.mark.asyncio
async def test_a_session_runs_with_the_mechanics_its_story_records(tmp_path: Path) -> None:
    mechanic = _mechanic(tmp_path, "notes", with_tool=True)
    story = FileStory(tmp_path / "story")
    await story.write_setup(setup=StorySetup(mechanics=("notes",)))
    seen = Recorder(ToolCallPart(tool_name="notes_tool", args={}))

    session = await WritingSession.open(story=story, agent=create_writer_agent(), model=seen.model, registry=_registry(mechanic))
    await session.turn("Hi.").run()

    assert [m.id for m in session.mechanics] == ["notes"]
    assert "Section of notes." in seen.instructions[0]
    assert "notes_tool" in seen.tools[0]
    assert "Section lines of notes." in seen.prompts[0]
    assert len(seen.tools) == 2


@pytest.mark.asyncio
async def test_a_mechanic_enabled_during_a_turn_applies_from_the_next_turn(tmp_path: Path) -> None:
    mechanic = _mechanic(tmp_path, "notes", with_tool=True)
    story = FileStory(tmp_path / "story")
    seen = Recorder(ToolCallPart(tool_name="enable_mechanic", args={"mechanic_id": "notes"}))
    session = await WritingSession.open(story=story, agent=create_writer_agent(), model=seen.model, registry={**MECHANICS, "notes": mechanic})

    first = session.turn("Enable it.")
    await first.run()

    assert first.outcome is TurnOutcome.COMPLETED
    assert (await story.read_setup()).mechanics == ("notes",)
    assert all("Section of notes." not in instructions for instructions in seen.instructions)
    assert all("notes_tool" not in tools for tools in seen.tools)
    assert session.mechanics == ()

    seen.tool_call = None
    await session.turn("Carry on.").run()

    assert "Section of notes." in seen.instructions[-1]
    assert "notes_tool" in seen.tools[-1]
    assert [m.id for m in session.mechanics] == ["notes"]


@pytest.mark.asyncio
async def test_a_turn_whose_setup_became_unusable_fails_without_running(tmp_path: Path) -> None:
    story = FileStory(tmp_path)
    seen = Recorder()
    session = await WritingSession.open(story=story, agent=create_writer_agent(), model=seen.model, registry=MECHANICS)
    await story.write_setup(setup=StorySetup(mechanics=("ghost",)))

    turn = session.turn("Hi.")
    await turn.run()

    assert turn.outcome is TurnOutcome.FAILED
    assert isinstance(turn.error, StorySetupError)
    assert seen.instructions == []


@pytest.mark.asyncio
async def test_a_turn_whose_setup_file_is_unreadable_fails_and_a_repaired_one_works_again(tmp_path: Path) -> None:
    story = FileStory(tmp_path)
    seen = Recorder()
    session = await WritingSession.open(story=story, agent=create_writer_agent(), model=seen.model, registry=MECHANICS)
    (tmp_path / SETUP_FILENAME).write_text("{not json", encoding="utf-8")

    broken = session.turn("Hi.")
    await broken.run()
    (tmp_path / SETUP_FILENAME).unlink()
    fixed = session.turn("Hi again.")
    await fixed.run()

    assert broken.outcome is TurnOutcome.FAILED
    assert fixed.outcome is TurnOutcome.COMPLETED


# The enable_mechanic tool


async def _enable(story: FileStory, mechanic_id: str, registry: Mapping[str, Mechanic] = MECHANICS) -> str:
    seen = Recorder(ToolCallPart(tool_name="enable_mechanic", args={"mechanic_id": mechanic_id}))
    await create_writer_agent().run("Go.", deps=story, model=seen.model, toolsets=[mechanic_toolset(registry)])
    return seen.prompts[-1]


@pytest.mark.asyncio
async def test_enabling_a_mechanic_records_it_with_its_requirements(tmp_path: Path) -> None:
    story = FileStory(tmp_path / "story")
    await story.write_setup(setup=StorySetup())

    await _enable(story, "needy", {**MECHANICS, "needy": _mechanic(tmp_path, "needy", requires=("sealed",))})

    assert (await story.read_setup()).mechanics == ("sealed", "needy")


@pytest.mark.asyncio
async def test_the_enable_result_says_it_takes_effect_from_the_next_turn(tmp_path: Path) -> None:
    story = FileStory(tmp_path / "story")
    results: list[str] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        returned = [part for message in messages for part in message.parts if isinstance(part, ToolReturnPart)]
        if returned:
            results.append(str(returned[0].content))
            return ModelResponse(parts=[TextPart(content="Done.")])
        return ModelResponse(parts=[ToolCallPart(tool_name="enable_mechanic", args={"mechanic_id": "sealed"})])

    await create_writer_agent().run("Go.", deps=story, model=FunctionModel(respond), toolsets=[mechanic_toolset(MECHANICS)])

    assert (await story.read_setup()).mechanics == ("sealed",)
    assert "next turn" in results[0]


@pytest.mark.asyncio
async def test_enabling_an_unknown_mechanic_is_refused_and_changes_nothing(tmp_path: Path) -> None:
    story = FileStory(tmp_path / "story")
    outcomes: list[ToolReturnPart] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        returned = [part for message in messages[-1:] for part in message.parts if isinstance(part, ToolReturnPart)]
        if returned:
            outcomes.extend(returned)
            return ModelResponse(parts=[TextPart(content="Done.")])
        return ModelResponse(parts=[ToolCallPart(tool_name="enable_mechanic", args={"mechanic_id": "ghost"})])

    await create_writer_agent().run("Go.", deps=story, model=FunctionModel(respond), toolsets=[mechanic_toolset(MECHANICS)])

    assert not (tmp_path / "story" / SETUP_FILENAME).exists() or (await story.read_setup()).mechanics == ()
    assert outcomes[0].outcome == "failed"
    assert "ghost" in str(outcomes[0].content) and "sealed" in str(outcomes[0].content)


@pytest.mark.asyncio
async def test_enabling_a_mechanic_already_in_use_changes_nothing(tmp_path: Path) -> None:
    story = FileStory(tmp_path / "story")
    await story.write_setup(setup=StorySetup(preset="co-writing", mechanics=("sealed",)))
    before = (tmp_path / "story" / SETUP_FILENAME).read_text(encoding="utf-8")

    await _enable(story, "sealed")

    assert (tmp_path / "story" / SETUP_FILENAME).read_text(encoding="utf-8") == before


def test_the_core_prompt_tells_the_writer_to_ask_before_it_enables_a_mechanic() -> None:
    assert "enable_mechanic" in WRITER_INSTRUCTIONS
    assert "enable_mechanic" in set(mechanic_toolset(MECHANICS).tools)


# Creating a story as a preset


def test_a_preset_becomes_a_setup_with_its_mechanics_resolved_in_full(tmp_path: Path) -> None:
    root = tmp_path / "presets" / "tabletop"
    root.mkdir(parents=True)
    (root / "preset.md").write_text("---\nname: tabletop\ntitle: Tabletop\ndescription: A game.\nmechanics: [needy]\n---\nLayer.\n", encoding="utf-8")
    preset = load_presets(tmp_path / "presets").get("tabletop")
    registry = _registry(_mechanic(tmp_path, "needy", requires=("base",)), _mechanic(tmp_path, "base"))

    assert setup_for(preset, registry) == StorySetup(preset="tabletop", mechanics=("base", "needy"))


def test_the_default_preset_becomes_the_default_setup() -> None:
    assert setup_for(CO_WRITING, MECHANICS) == StorySetup()


def test_a_preset_naming_an_unknown_mechanic_is_refused_by_name(tmp_path: Path) -> None:
    root = tmp_path / "presets" / "broken"
    root.mkdir(parents=True)
    (root / "preset.md").write_text("---\nname: broken\ntitle: Broken\ndescription: Broken.\nmechanics: [ghost]\n---\nLayer.\n", encoding="utf-8")

    with pytest.raises(PresetError, match="broken"):
        setup_for(load_presets(tmp_path / "presets").get("broken"), MECHANICS)


@pytest.mark.asyncio
async def test_creating_a_story_writes_its_setup(tmp_path: Path) -> None:
    library = StoryLibrary(FileWorkspace(tmp_path))

    plain = await library.create(name="attic")
    sealed = await library.create(name="vault", setup=StorySetup(preset="co-writing", mechanics=("sealed",)))

    assert (tmp_path / "attic" / SETUP_FILENAME).is_file()
    assert await plain.read_setup() == StorySetup()
    assert (await sealed.read_setup()).mechanics == ("sealed",)
