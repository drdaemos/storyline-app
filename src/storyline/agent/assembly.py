"""What a story's preset adds to the writer for each run: instructions on top of the core prompt, and the skill catalog."""

from dataclasses import dataclass
from pathlib import Path

from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai_harness.skills import Skills

from storyline.agent.writer import WRITER_SKILLS_PATH
from storyline.presets import Preset
from storyline.workspace import Story

SKILL_FILENAME = "SKILL.md"


@dataclass(frozen=True)
class RunAssembly:
    """The per-run additions to the writer agent: passed as run ``instructions`` and ``capabilities``."""

    instructions: str
    """The preset's layer of the prompt."""
    capabilities: tuple[AbstractCapability[Story], ...]
    """The skill catalog: the core skills the preset keeps plus the preset's own."""


def assemble(preset: Preset, *, core_skills: Path = WRITER_SKILLS_PATH) -> RunAssembly:
    """Assemble the run additions for a preset; a preset skill with a core skill's name replaces it."""
    overridden = sorted(_skill_names(core_skills) & _skill_names(preset.skills_dir)) if preset.skills_dir is not None else []
    catalog: list[AbstractCapability[Story]] = [Skills(core_skills, exclude=overridden) if overridden else Skills(core_skills)]
    if preset.skills_dir is not None and _skill_names(preset.skills_dir):
        catalog.append(Skills(preset.skills_dir))
    return RunAssembly(instructions=preset.layer, capabilities=tuple(catalog))


def _skill_names(directory: Path) -> set[str]:
    return {path.parent.name for path in directory.glob(f"*/{SKILL_FILENAME}")}
