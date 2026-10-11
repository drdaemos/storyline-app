"""Pydantic AI writer agent."""

import hashlib
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.capabilities import WebSearch
from pydantic_ai.settings import ModelSettings
from pydantic_ai_harness.skills import Skills

from storyline.agent.models import resolve_model
from storyline.agent.writer_tools import WRITER_TOOLSET
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


def create_writer_agent(*, model_name: str = DEFAULT_MODEL_NAME, instructions: str = WRITER_INSTRUCTIONS) -> Agent[Story, str]:
    """Create an agent that can edit one story through the story boundary."""
    return Agent(
        resolve_model(model_name),
        name="storyline_writer",
        deps_type=Story,
        instructions=instructions,
        toolsets=[WRITER_TOOLSET],
        capabilities=[WebSearch(), Skills(WRITER_SKILLS_PATH)],
        model_settings=ModelSettings(max_tokens=WRITER_MAX_OUTPUT_TOKENS),
    )
