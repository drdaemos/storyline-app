"""Pydantic AI writer agent."""

import hashlib
from collections.abc import Mapping
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.capabilities import WebSearch
from pydantic_ai.settings import ModelSettings

from storyline.agent.models import resolve_model
from storyline.agent.writer_tools import WRITER_TOOLSET
from storyline.mechanics import Mechanic
from storyline.presets import Preset, PresetCatalog
from storyline.workspace import Story

DEFAULT_MODEL_NAME = "openrouter:meta/muse-spark-1.3"
WRITER_PROMPT_PATH = Path(__file__).with_name("prompts") / "writer.md"
WRITER_INSTRUCTIONS = WRITER_PROMPT_PATH.read_text(encoding="utf-8")
WRITER_SKILLS_PATH = Path(__file__).with_name("skills")
WRITER_MAX_OUTPUT_TOKENS = 16_000
"""Output cap per model response, explicit so a large tool call is not cut off mid-JSON by a provider default."""


def prompt_version(instructions: str) -> str:
    """Return a short stable identifier for a set of instructions, to tell prompt variants apart."""
    return hashlib.sha256(instructions.encode("utf-8")).hexdigest()[:10]


def writer_prompt_version(instructions: str, preset: Preset) -> str:
    """Return a short stable identifier for the core instructions together with a preset's layer."""
    return prompt_version("\n\n".join((instructions, preset.layer)))


def catalog_prompt_version(instructions: str, presets: PresetCatalog, mechanics: Mapping[str, Mechanic]) -> str:
    """Return a short stable identifier for everything a run of any bundled story kind is prompted with.

    That is the core instructions, every preset's layer, review checklist and skills, and every registered mechanic's
    prompt, so a change to any of them changes the version. Presets and mechanics are taken in id order.
    """
    parts = [instructions]
    for preset in sorted(presets, key=lambda item: item.id):
        parts += [preset.id, preset.layer, preset.review_checklist or ""]
        if preset.skills_dir is not None:
            parts += [f"{path.relative_to(preset.skills_dir).as_posix()}\n{path.read_text(encoding='utf-8')}" for path in sorted(preset.skills_dir.rglob("*")) if path.is_file()]
    parts += [f"{mechanic_id}\n{mechanics[mechanic_id].prompt}" for mechanic_id in sorted(mechanics)]
    return prompt_version("\n\n".join(parts))


def create_writer_agent(*, model_name: str = DEFAULT_MODEL_NAME, instructions: str = WRITER_INSTRUCTIONS) -> Agent[Story, str]:
    """Create an agent that can edit one story through the story boundary."""
    return Agent(
        resolve_model(model_name),
        name="storyline_writer",
        deps_type=Story,
        instructions=instructions,
        toolsets=[WRITER_TOOLSET],
        capabilities=[WebSearch()],
        model_settings=ModelSettings(max_tokens=WRITER_MAX_OUTPUT_TOKENS),
    )
