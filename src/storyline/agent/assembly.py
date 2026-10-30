"""What a story's preset and mechanics add to the writer for each run: instructions on top of the core prompt, skills and tools."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai_harness.skills import Skills

from storyline.agent.writer import WRITER_SKILLS_PATH
from storyline.mechanics import Mechanic
from storyline.presets import Preset
from storyline.workspace import Story

SKILL_FILENAME = "SKILL.md"


@dataclass(frozen=True)
class RunAssembly:
    """The per-run additions to the writer agent: passed as run ``instructions`` and ``capabilities``."""

    instructions: str
    """The preset's layer of the prompt, then each mechanic's section, separated by blank lines."""
    capabilities: tuple[AbstractCapability[Story], ...]
    """The skill catalog: the core skills the preset keeps, the preset's own and each mechanic's."""
    toolsets: tuple[AbstractToolset[Story], ...] = ()
    """The tools of the story's mechanics."""


def assemble(preset: Preset, mechanics: Sequence[Mechanic] = (), *, core_skills: Path = WRITER_SKILLS_PATH) -> RunAssembly:
    """Assemble the run additions for a preset and the story's mechanics; a preset skill with a core skill's name replaces it."""
    overridden = sorted(_skill_names(core_skills) & _skill_names(preset.skills_dir)) if preset.skills_dir is not None else []
    catalog: list[AbstractCapability[Story]] = [Skills(core_skills, exclude=overridden) if overridden else Skills(core_skills)]
    if preset.skills_dir is not None and _skill_names(preset.skills_dir):
        catalog.append(Skills(preset.skills_dir))
    catalog.extend(Skills(mechanic.skills_dir) for mechanic in mechanics if mechanic.skills_dir is not None and _skill_names(mechanic.skills_dir))
    sections = [preset.layer, *(mechanic.prompt for mechanic in mechanics if mechanic.prompt)]
    toolsets = tuple(mechanic.toolset for mechanic in mechanics if mechanic.toolset is not None)
    return RunAssembly(instructions="\n\n".join(sections), capabilities=tuple(catalog), toolsets=toolsets)


def _skill_names(directory: Path) -> set[str]:
    return {path.parent.name for path in directory.glob(f"*/{SKILL_FILENAME}")}
