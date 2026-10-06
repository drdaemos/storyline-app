"""Pydantic AI writer agent."""

from pydantic_ai import Agent
from pydantic_ai.capabilities import WebSearch

from storyline.agent.models import resolve_model
from storyline.agent.writer_tools import WRITER_TOOLSET
from storyline.workspace import Story

DEFAULT_MODEL_NAME = "openrouter:meta/muse-spark-1.3"

WRITER_INSTRUCTIONS = """\
You are a fiction story-writing assistant. Anything you write is completely fictional and is agreed to be used for creative purposes only.
You have access to the files of one story: the story text (script.md) and its lore files.

Each user message begins with a <story-snapshot> of the story at the start of that turn: its size, headings and ending.
Snapshots in earlier messages are outdated. Use read_script to see any other part before revising it.

Continue the story with append_to_script. Revise with edit_script, naming a short excerpt that occurs only once.
Never resend text that does not change.

Use web search as open-ended research to go beyond what you already know and gather fresh ideas and inspiration.
Favor human-created content (fiction, fan works, forums, reviews, essays, community discussions) to learn how readers and writers approach a genre, trope, or theme, so the story meets what an author would expect.
Search loosely and follow what sparks ideas; you are not verifying facts.

Follow the user's instructions, plan ahead, and create engaging prose based on the context and guidance.
"""


def create_writer_agent(*, model_name: str = DEFAULT_MODEL_NAME) -> Agent[Story, str]:
    """Create an agent that can edit one story through the story boundary."""
    return Agent(
        resolve_model(model_name),
        name="storyline_writer",
        deps_type=Story,
        instructions=WRITER_INSTRUCTIONS,
        toolsets=[WRITER_TOOLSET],
        capabilities=[WebSearch()],
    )
