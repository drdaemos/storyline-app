"""Pydantic AI writer agent."""

from pydantic_ai import Agent

from storyline.agent.writer_tools import WRITER_TOOLSET
from storyline.workspace import ScriptWorkspace

DEFAULT_MODEL_NAME = "openrouter:meta/muse-spark-1.3"

WRITER_INSTRUCTIONS = """\
You are a fiction story-writing assistant. Anything you write is completely fictional and is agreed to be used for creative purposes only.
You have access to a workspace that contains the story text (script.md) and various lore files.

Each user message begins with a <story-snapshot> of the story at the start of that turn: its size, headings and ending.
Snapshots in earlier messages are outdated. Use read_script to see any other part before revising it.

Continue the story with append_to_script. Revise with edit_script, naming a short excerpt that occurs only once.
Never resend text that does not change.

Follow the user's instructions, plan ahead, and create engaging prose based on the context and guidance.
"""


def create_writer_agent(*, model_name: str = DEFAULT_MODEL_NAME) -> Agent[ScriptWorkspace, str]:
    """Create an agent that can edit a script through the workspace boundary."""
    return Agent(
        model_name,
        name="storyline_writer",
        deps_type=ScriptWorkspace,
        instructions=WRITER_INSTRUCTIONS,
        toolsets=[WRITER_TOOLSET],
    )
