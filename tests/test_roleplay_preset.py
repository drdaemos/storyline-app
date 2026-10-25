"""Tests for the roleplay preset and the prompt files of its mechanics: loading, assembly and structure."""

from pathlib import Path

import pytest
import yaml
from pydantic_ai import ModelResponse, TextPart
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel

from storyline.agent import assemble, create_writer_agent
from storyline.agent.writer import WRITER_SKILLS_PATH
from storyline.mechanics import resolve_mechanics
from storyline.presets import BUNDLED_PRESETS, PRESETS_PATH, PresetError, load_presets, setup_for
from storyline.registry import MECHANICS
from storyline.workspace.file_story import FileStory

MECHANICS_PATH = Path(MECHANICS["sealed"].prompt_path or "").parent
ROLEPLAY = BUNDLED_PRESETS.get("roleplay")
ROLEPLAY_MECHANICS = ["persona", "cast", "sealed", "clocks", "oracle", "review"]
PROMPT_FILES = sorted(MECHANICS_PATH.glob("*.md"))
SKILL_FILES = [*sorted(PRESETS_PATH.glob("*/skills/*/SKILL.md")), *sorted(MECHANICS_PATH.glob("*/skills/*/SKILL.md"))]
VALID_HEADER = "---\nname: {name}\ntitle: A title\ndescription: A description.\nmechanics: []\n---\nLayer.\n"


def _skill_header(path: Path) -> dict[str, object]:
    header = yaml.safe_load(path.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert isinstance(header, dict)
    return header


# The preset


def test_the_roleplay_preset_loads_with_its_mechanics_layer_skills_and_checklist() -> None:
    assert (ROLEPLAY.title.strip(), ROLEPLAY.description.strip(), ROLEPLAY.layer.strip()) != ("", "", "")
    assert ROLEPLAY.mechanics == tuple(ROLEPLAY_MECHANICS)
    assert ROLEPLAY.skills_dir is not None and {path.name for path in ROLEPLAY.skills_dir.iterdir()} == {"assess-request", "write-scene"}
    assert ROLEPLAY.review_checklist is not None and ROLEPLAY.review_checklist.strip()


def test_the_roleplay_preset_resolves_to_all_six_mechanics_with_requirements_first() -> None:
    resolved = [mechanic.id for mechanic in resolve_mechanics(ROLEPLAY.mechanics, MECHANICS)]

    assert sorted(resolved) == sorted(ROLEPLAY_MECHANICS)
    assert resolved.index("sealed") < resolved.index("cast") and resolved.index("sealed") < resolved.index("clocks") and resolved.index("sealed") < resolved.index("review")
    assert setup_for(ROLEPLAY, MECHANICS).mechanics == tuple(resolved)
    assert setup_for(ROLEPLAY, MECHANICS).preset == "roleplay"


def test_co_writing_has_no_checklist() -> None:
    assert BUNDLED_PRESETS.get("co-writing").review_checklist is None


def test_a_checklist_is_read_from_review_md_and_an_empty_one_is_refused(tmp_path: Path) -> None:
    (tmp_path / "mine").mkdir()
    (tmp_path / "mine" / "preset.md").write_text(VALID_HEADER.format(name="mine"), encoding="utf-8")
    (tmp_path / "mine" / "review.md").write_text("- Does it fit?\n", encoding="utf-8")

    assert load_presets(tmp_path).get("mine").review_checklist == "- Does it fit?"

    (tmp_path / "mine" / "review.md").write_text("  \n", encoding="utf-8")
    with pytest.raises(PresetError, match="review"):
        load_presets(tmp_path)


# Assembly


@pytest.mark.asyncio
async def test_the_roleplay_run_has_the_layer_then_each_mechanics_section_and_the_catalog_of_skills(tmp_path: Path) -> None:
    mechanics = resolve_mechanics(ROLEPLAY.mechanics, MECHANICS)
    assembly = assemble(ROLEPLAY, mechanics)
    seen: list[AgentInfo] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.append(info)
        return ModelResponse(parts=[TextPart(content="Done.")])

    await create_writer_agent().run(
        "Hi.",
        deps=FileStory(tmp_path),
        model=FunctionModel(respond),
        instructions=assembly.instructions,
        capabilities=list(assembly.capabilities),
        toolsets=list(assembly.toolsets),
    )

    instructions = str(seen[0].instructions)
    positions = [instructions.index(ROLEPLAY.layer)] + [instructions.index(mechanic.prompt) for mechanic in mechanics]
    assert positions == sorted(positions)
    assert {"set_clock", "tick_clock", "remove_clock", "roll", "request_review"} <= {tool.name for tool in seen[0].function_tools}


@pytest.mark.asyncio
async def test_the_roleplay_catalog_has_cast_sheet_and_the_roleplay_versions_of_the_core_skills(tmp_path: Path) -> None:
    assembly = assemble(ROLEPLAY, resolve_mechanics(ROLEPLAY.mechanics, MECHANICS))
    seen: list[str] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.append(str(info.instructions) + " ".join(str(tool) for tool in info.function_tools))
        return ModelResponse(parts=[TextPart(content="Done.")])

    await create_writer_agent().run("Hi.", deps=FileStory(tmp_path), model=FunctionModel(respond), instructions=assembly.instructions, capabilities=list(assembly.capabilities))

    catalog = seen[0]
    assert "cast-sheet" in catalog
    for name in ("assess-request", "write-scene"):
        roleplay = str(_skill_header(PRESETS_PATH / "roleplay" / "skills" / name / "SKILL.md")["description"])
        core = str(_skill_header(WRITER_SKILLS_PATH / name / "SKILL.md")["description"])
        assert roleplay in catalog and core not in catalog
    assert catalog.count("name: assess-request") <= 1


# Prompt structure


@pytest.mark.parametrize("path", PROMPT_FILES, ids=lambda path: path.name)
def test_every_mechanic_prompt_file_is_not_empty(path: Path) -> None:
    assert path.read_text(encoding="utf-8").strip()


def test_every_registered_mechanic_that_has_a_prompt_has_a_description_and_a_prompt_file_in_the_package() -> None:
    for mechanic in MECHANICS.values():
        assert mechanic.description.strip() and "\n" not in mechanic.description.strip()
        assert mechanic.prompt_path is not None and mechanic.prompt_path.parent == MECHANICS_PATH and mechanic.prompt.strip()


def test_the_reviewer_prompt_ends_with_the_checklist_heading_the_preset_checklist_follows() -> None:
    reviewer = (MECHANICS_PATH / "reviewer.md").read_text(encoding="utf-8").rstrip()

    assert reviewer.endswith("## Checklist")


def test_the_cast_mechanic_ships_its_skill() -> None:
    skills = MECHANICS["cast"].skills_dir

    assert skills is not None and [path.name for path in skills.iterdir()] == ["cast-sheet"]


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda path: f"{path.parent.parent.parent.name}/{path.parent.name}")
def test_every_preset_and_mechanic_skill_has_matching_frontmatter_and_a_body(path: Path) -> None:
    header = _skill_header(path)

    assert header["name"] == path.parent.name
    assert isinstance(header["description"], str) and header["description"].strip()
    assert path.read_text(encoding="utf-8").split("---\n", 2)[2].strip()


@pytest.mark.parametrize("path", sorted(PRESETS_PATH.glob("*/review.md")), ids=lambda path: path.parent.name)
def test_every_preset_checklist_is_a_list(path: Path) -> None:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert lines and all(line.startswith("- ") for line in lines)
