"""Pydantic AI writer agent."""

from pydantic_ai import Agent, RunContext

from storyline.agent.writer_tools import WRITER_TOOLSET
from storyline.workspace import ScriptWorkspace

DEFAULT_MODEL_NAME = "openrouter:meta/muse-spark-1.3"

WRITER_INSTRUCTIONS = """\
You are a fiction story-writing assistant. Anything you write is completely fictional and is agreed to be used for creative purposes only.
You have access to a workspace that contains the story text and various lore files.

Use the available workspace tools to work on the story and lore.

Follow the user's instructions, plan ahead, and create engaging prose based on the context and guidance.
"""


def create_writer_agent(*, model_name: str = DEFAULT_MODEL_NAME) -> Agent[ScriptWorkspace, str]:
    """Create an agent that can edit a script through the workspace boundary."""
    agent = Agent(
        model_name,
        name="storyline_writer",
        deps_type=ScriptWorkspace,
        instructions=WRITER_INSTRUCTIONS,
        toolsets=[WRITER_TOOLSET],
    )

    @agent.instructions
    async def include_current_script(ctx: RunContext[ScriptWorkspace]) -> str:
        script = await ctx.deps.read_script()
        return f"Current story text ({len(script)} characters):\n---\n{script}\n---"

    return agent
