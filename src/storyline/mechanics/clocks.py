"""The clocks mechanic: slow-building events the writer keeps count of, visible to the user or hidden."""

from collections.abc import Mapping
from functools import partial
from pathlib import Path

from pydantic_ai import FunctionToolset, RunContext, ToolFailed

from storyline.mechanics.base import Mechanic
from storyline.workspace import Clock, Story, WorkspaceEditError, render_clocks
from storyline.workspace import remove_clock as drop_clock
from storyline.workspace import set_clock as put_clock
from storyline.workspace import tick_clock as move_clock
from storyline.workspace.clocks import find_clock, render_clock

CLOCK_TOOL_NAMES = frozenset({"set_clock", "tick_clock", "remove_clock"})
"""The clock tools, so an interface knows to show the clocks again after one runs."""

CLOCKS_TOOLSET = FunctionToolset[Story](id="clocks")


@CLOCKS_TOOLSET.tool
async def set_clock(ctx: RunContext[Story], name: str, segments: int, visible: bool, when_full: str, clock_id: str | None = None) -> str:
    """Create a clock, or change one. Returns every clock with its id.

    Args:
        name: What is building, in a few words, e.g. "The guard's suspicion".
        segments: How many ticks fill it, 2 to 12: 4 for something close, 6 for something steady, 8 for something slow.
        visible: True when the persona would see it coming, so the user sees it too; false for a character's secret plan, which only the number of hidden clocks reveals.
        when_full: What happens when it fills, as you mean it to land.
        clock_id: The id of an existing clock to change; omit to create a new one. A changed clock keeps what it has filled, within its new segments.
    """
    try:
        clocks = await ctx.deps.change_clocks(change=partial(put_clock, name=name, segments=segments, visible=visible, when_full=when_full, clock_id=clock_id))
    except WorkspaceEditError as error:
        raise ToolFailed(str(error)) from error
    return f"{'Changed' if clock_id else 'Created'} {name.strip()}.\n{render_clocks(clocks)}"


@CLOCKS_TOOLSET.tool
async def tick_clock(ctx: RunContext[Story], clock_id: str, reason: str, by: int = 1) -> str:
    """Move a clock forward, or back with a negative number. Returns the clock's new state and every clock with its id.

    Args:
        clock_id: The id shown in the clock list, e.g. '3f2a9c1d'.
        reason: Why it moved: time passing offscreen, what the persona did or did not do, a roll.
        by: How many segments to add; negative to roll back. The clock stays between empty and full.
    """
    if not reason.strip():
        raise ToolFailed("Give the reason the clock moved.")
    before: list[int] = []

    def change(clocks: tuple[Clock, ...]) -> tuple[Clock, ...]:
        before.append(find_clock(clocks, clock_id).filled)
        return move_clock(clocks, clock_id, by=by)

    try:
        clocks = await ctx.deps.change_clocks(change=change)
    except WorkspaceEditError as error:
        raise ToolFailed(str(error)) from error
    clock = find_clock(clocks, clock_id)
    state = f"{clock.name} is now {clock.filled}/{clock.segments} (was {before[0]}; {reason.strip()})."
    if clock.full and before[0] < clock.segments:
        state += f" It is full. When full: {clock.when_full or 'nothing was set; decide what it brings.'}"
    elif clock.full:
        state += " It was already full."
    return f"{state}\n{render_clocks(clocks)}"


@CLOCKS_TOOLSET.tool
async def remove_clock(ctx: RunContext[Story], clock_id: str) -> str:
    """Remove a clock once what it counted has happened or no longer matters. Returns the clocks that remain with their ids.

    Args:
        clock_id: The id shown in the clock list.
    """
    try:
        clocks = await ctx.deps.change_clocks(change=partial(drop_clock, clock_id=clock_id))
    except WorkspaceEditError as error:
        raise ToolFailed(str(error)) from error
    return f"Removed the clock.\n{render_clocks(clocks)}"


class ClocksMechanic(Mechanic):
    """Gives the writer clocks that build toward events, some of them hidden from the user."""

    id = "clocks"
    description = "Clocks that fill one tick at a time toward something that will happen, shown to the user or kept hidden."
    requires = ("sealed",)
    prompt_path = Path(__file__).with_name("clocks.md")
    toolset = CLOCKS_TOOLSET

    async def snapshot_section(self, story: Story) -> list[str]:
        """Every clock, hidden ones included, with its id and what happens when it fills."""
        try:
            clocks = await story.read_clocks()
        except WorkspaceEditError as error:
            return ["Clocks:", f"The clocks cannot be read: {error}"]
        if not clocks:
            return ["Clocks: none yet."]
        return ["Clocks:", *(render_clock(clock) for clock in clocks)]

    def seals(self, tool_name: str, arguments: Mapping[str, object]) -> bool:
        """Hidden clocks would leak in the call; visible ones are shown in the panel anyway."""
        return tool_name in CLOCK_TOOL_NAMES
