"""The review mechanic: a second look at the narrator's plan before a beat with stakes is written.

The reviewer itself, an agent of its own, lives in ``storyline.agent.reviewer``; the registry hands it to the mechanic.
"""

from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator
from pydantic_ai import FunctionToolset, RunContext, ToolFailed

from storyline.mechanics.base import Mechanic
from storyline.workspace import Story


class BeatAction(BaseModel):
    """One character's move in the planned beat."""

    character: str = Field(description="Who acts: a cast member's name, or a bystander.")
    intends: str = Field(description="What they try to do, in a line.")
    because: str = Field(description="The file or fact behind it: their cast sheet's want, a clock, a roll, something that happened in the script.")


class BeatPlan(BaseModel):
    """The narrator's plan for the next beat, before any of it is written."""

    persona_input: str = Field(description="The persona's words and actions as the user gave them, unchanged and nothing added.")
    actions: list[BeatAction] = Field(description="What each character other than the persona does in the beat.")
    rolls: list[str] = Field(default=[], description="The oracle rolls the beat rests on, each as question, odds and result.")
    changes: list[str] = Field(default=[], description="What changes in the story: for the persona, the cast, the clocks, the world.")
    hand_back: str = Field(description="Where the beat stops and what the persona is left to answer.")


class Objection(BaseModel):
    """One thing in the plan that the story's record does not support."""

    issue: str = Field(description="What is wrong with the plan, in a sentence.")
    rests_on: str = Field(description="The file or fact the objection rests on, e.g. sealed/vera.md: what the sheet says, or what the script established.")
    instead: str = Field(description="What would fit the record instead.")


class Verdict(BaseModel):
    """The reviewer's answer: the plan holds, or it has objections."""

    verdict: Literal["pass", "object"]
    objections: list[Objection] = Field(default=[], description="Required with an objection; few and concrete.")

    @model_validator(mode="after")
    def _objection_has_objections(self) -> Self:
        if self.verdict == "object" and not self.objections:
            raise ValueError("An objecting verdict must list its objections.")
        return self


class ReviewFailedError(RuntimeError):
    """Raised when the review could not be done: its model is unusable or the reviewer failed."""


type PlanReviewer = Callable[[RunContext[Story], BeatPlan], Awaitable[Verdict]]
"""Runs the reviewer on the narrator's plan and returns its verdict; raises ``ReviewFailedError`` when the review could not be done."""


def format_verdict(verdict: Verdict) -> str:
    """Render a verdict as the text of the tool result."""
    if verdict.verdict == "pass":
        return "Pass."
    lines = ["Objections:"]
    lines.extend(f"- {objection.issue} Rests on: {objection.rests_on}. Instead: {objection.instead}" for objection in verdict.objections)
    return "\n".join(lines)


class ReviewMechanic(Mechanic):
    """Gives the narrator a reviewer that checks its plan against the story's record."""

    id = "review"
    description = "A second agent checks the narrator's plan for a beat with stakes against the story's files before it is written."
    requires = ("sealed",)
    prompt_path = Path(__file__).with_name("review.md")

    def __init__(self, reviewer: PlanReviewer) -> None:
        self.reviewer = reviewer
        """The reviewer agent's run; ``storyline.registry`` supplies it from the agent layer."""
        self.toolset = FunctionToolset[Story](id="review")
        self.toolset.add_function(self.request_review, name="request_review")

    async def request_review(self, ctx: RunContext[Story], plan: BeatPlan) -> str:
        """Have the plan for the next beat checked against the story's files before you write it. Returns a pass or objections.

        Args:
            plan: The plan for the beat. The reviewer sees the story's files, sealed ones included, and the user's latest message, not your conversation.
        """
        try:
            return format_verdict(await self.reviewer(ctx, plan))
        except ReviewFailedError as error:
            raise ToolFailed(str(error)) from error

    def seals(self, tool_name: str, arguments: Mapping[str, object]) -> bool:
        """The plan names what is hidden, and the verdict quotes the sealed files."""
        return tool_name == "request_review"
