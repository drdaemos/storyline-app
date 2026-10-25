"""The oracle mechanic: contested outcomes and open questions about the world settled by a die, not by the writer's taste."""

import math
import secrets
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic_ai import FunctionToolset, RunContext, ToolFailed

from storyline.mechanics.base import Mechanic
from storyline.workspace import Roll, Story, WorkspaceEditError

type Odds = Literal["almost certain", "likely", "even", "unlikely", "small chance"]

ODDS_CHANCE: Mapping[str, int] = {"almost certain": 90, "likely": 75, "even": 50, "unlikely": 25, "small chance": 10}
"""The chance in a hundred that the answer is yes, by the odds the writer sets."""
LOG_LIMIT = 50
"""How many rolls the log keeps, newest first."""
SNAPSHOT_ROLLS = 5
STRONG_FRACTION = 5
"""A result is strong when the die lands in the outermost fifth of the range that decided it."""


def roll_d100() -> int:
    """A fair die from 1 to 100."""
    return secrets.randbelow(100) + 1


def answer_for(die: int, chance: int) -> tuple[Literal["yes", "no"], bool]:
    """Return whether the die says yes or no at this chance, and whether the answer is strong."""
    if die <= chance:
        return "yes", die <= math.ceil(chance / STRONG_FRACTION)
    return "no", die > 100 - math.ceil((100 - chance) / STRONG_FRACTION)


def describe_roll(roll: Roll) -> str:
    """Render a roll as ``Strong no (rolled 97 against likely).``"""
    answer = f"{'Strong ' if roll.strong else ''}{roll.answer}"
    return f"{answer[0].upper()}{answer[1:]} (rolled {roll.die} against {roll.odds})."


class OracleMechanic(Mechanic):
    """Gives the writer a roll that answers a question at odds the writer sets from the fiction, and keeps a sealed log."""

    id = "oracle"
    description = "A die the writer rolls for contested outcomes and open questions about the world, at odds it sets from the fiction."
    prompt_path = Path(__file__).with_name("oracle.md")

    def __init__(self, roll_die: Callable[[], int] = roll_d100) -> None:
        self.roll_die = roll_die
        """Where the die comes from: 1 to 100; replaced in tests."""
        self.toolset = FunctionToolset[Story](id="oracle")
        self.toolset.add_function(self.roll, name="roll")

    async def roll(self, ctx: RunContext[Story], question: str, odds: Odds) -> str:
        """Roll the oracle on a yes or no question. Set the odds from the fiction first, and roll once per question.

        Args:
            question: What is being decided, phrased so that yes and no both lead somewhere, e.g. "Does the guard believe the lie?".
            odds: How likely yes is before the roll: almost certain, likely, even, unlikely or small chance.
        """
        if not question.strip():
            raise ToolFailed("Name the question the roll answers.")
        die = self.roll_die()
        answer, strong = answer_for(die, ODDS_CHANCE[odds])
        rolled = Roll(question=question.strip(), odds=odds, die=die, answer=answer, strong=strong, at=datetime.now(UTC))
        try:
            await ctx.deps.change_rolls(change=lambda rolls: (rolled, *rolls)[:LOG_LIMIT])
        except WorkspaceEditError as error:
            raise ToolFailed(f"The roll was {describe_roll(rolled)} It could not be logged: {error}") from error
        return describe_roll(rolled)

    async def snapshot_section(self, story: Story) -> list[str]:
        """The latest rolls, so the writer sees what it already asked."""
        try:
            rolls = await story.read_rolls()
        except WorkspaceEditError as error:
            return ["Recent rolls:", f"The roll log cannot be read: {error}"]
        if not rolls:
            return ["Recent rolls: none yet."]
        return ["Recent rolls (newest first):", *(f"- {roll.question} {describe_roll(roll)}" for roll in rolls[:SNAPSHOT_ROLLS])]

    def seals(self, tool_name: str, arguments: Mapping[str, object]) -> bool:
        """A roll's question can name what is hidden."""
        return tool_name == "roll"
