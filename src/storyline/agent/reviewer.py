"""The reviewer: a separate agent that checks the narrator's plan against the story's record before a beat is written."""

import os
from collections.abc import Callable, Mapping
from pathlib import Path

from pydantic_ai import Agent, FunctionToolset, RunContext
from pydantic_ai.messages import ModelRequest, UserPromptPart
from pydantic_ai.models import Model

from storyline.agent.models import ModelNameError, resolve_model, validate_model_name
from storyline.agent.story_context import turn_prompt, visible_prompt_text
from storyline.agent.writer_tools import WRITER_TOOLSET
from storyline.mechanics import Mechanic, resolve_mechanics
from storyline.mechanics.review import BeatPlan, ReviewFailedError, Verdict
from storyline.presets import BUNDLED_PRESETS
from storyline.workspace import Story

REVIEW_MODEL_ENV_VAR = "STORYLINE_REVIEW_MODEL"
REVIEWER_PROMPT_PATH = Path(__file__).parent.parent / "mechanics" / "reviewer.md"
READ_ONLY_TOOL_NAMES = ("list_lore", "read_lore", "read_script")
"""The writer's tools that only read; the reviewer never gets one that writes."""
FALLBACK_CHECKLIST = """- Does each character act as their cast sheet or the lore says they would, with no one giving ground without a cause in the story?
- Does something happen to the persona that nothing in the story set up?
- Does the plan contradict the lore, the sealed files or what has already happened in the script?
- Is the plan inside the content bounds in collaboration.md?"""
NO_USER_MESSAGE = "There is no message from the user in this conversation yet."


def reviewer_toolset() -> FunctionToolset[Story]:
    """The tools the reviewer reads the story with."""
    toolset = FunctionToolset[Story](id="reviewer_workspace")
    for name in READ_ONLY_TOOL_NAMES:
        toolset.add_tool(WRITER_TOOLSET.tools[name])
    return toolset


def reviewer_instructions(checklist: str | None) -> str:
    """The reviewer's instructions with the checklist of the story's preset after them."""
    return f"{REVIEWER_PROMPT_PATH.read_text(encoding='utf-8').rstrip()}\n\n{(checklist or FALLBACK_CHECKLIST).strip()}"


def create_reviewer_agent(model: Model | str, *, checklist: str | None) -> Agent[Story, Verdict]:
    """Create the reviewer: it reads the story through read-only tools and answers with a verdict."""
    return Agent(model, name="storyline_reviewer", deps_type=Story, output_type=Verdict, instructions=reviewer_instructions(checklist), toolsets=[reviewer_toolset()])


def latest_user_message(ctx: RunContext[Story]) -> str | None:
    """What the user last wrote in the conversation, without the story snapshot added for the model."""
    for message in reversed(ctx.messages):
        if isinstance(message, ModelRequest):
            for part in reversed(message.parts):
                if isinstance(part, UserPromptPart) and (text := visible_prompt_text(part.content)):
                    return text
    return None


def review_model(ctx: RunContext[Story], resolver: Callable[[str], Model | str] | None = None) -> Model | str:
    """The model that reviews: the one ``STORYLINE_REVIEW_MODEL`` names, otherwise the narrator's own."""
    name = os.getenv(REVIEW_MODEL_ENV_VAR, "").strip()
    if not name:
        return ctx.model
    try:
        validate_model_name(name)
        return (resolver or resolve_model)(name)
    except ModelNameError as error:
        raise ReviewFailedError(f"{REVIEW_MODEL_ENV_VAR} is not a usable model, so the review could not run: {error}") from error


class StoryReviewer:
    """Runs the reviewer on the narrator's plan: the ``PlanReviewer`` the review mechanic is given."""

    def __init__(self, registry: Mapping[str, Mechanic], model_resolver: Callable[[str], Model | str] | None = None) -> None:
        self.registry = registry
        """The mechanics a story's setup is resolved against, to snapshot the story as the narrator sees it."""
        self.model_resolver = model_resolver
        """Turns the model name in ``STORYLINE_REVIEW_MODEL`` into a model; None resolves it as the writer's models are. Replaced in tests."""

    async def __call__(self, ctx: RunContext[Story], plan: BeatPlan) -> Verdict:
        """Run the reviewer on a plan and return its verdict; its cost is counted in the narrator's turn."""
        model = review_model(ctx, self.model_resolver)
        try:
            setup = await ctx.deps.read_setup()
            checklist = BUNDLED_PRESETS.get(setup.preset).review_checklist if setup.preset in BUNDLED_PRESETS else None
            mechanics = resolve_mechanics(setup.mechanics, self.registry)
            user_message = latest_user_message(ctx)
            request = f"The user's latest message:\n{user_message or NO_USER_MESSAGE}\n\nThe narrator's plan:\n{plan.model_dump_json(indent=2)}"
            prompt = await turn_prompt(ctx.deps, request, mechanics, registry=self.registry)
            result = await create_reviewer_agent(model, checklist=checklist).run(prompt, deps=ctx.deps, usage=ctx.usage)
        except Exception as error:
            raise ReviewFailedError(f"The reviewer could not be reached ({type(error).__name__}: {str(error)[:200]}); write the beat on your own judgement.") from error
        return result.output
