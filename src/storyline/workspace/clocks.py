"""Pure clock operations shared by the writer's tools and the storage adapter."""

from collections.abc import Sequence

from storyline.workspace.contracts import Clock, ClockError

EMPTY_CLOCKS_TEXT = "There are no clocks."
MIN_SEGMENTS = 2
MAX_SEGMENTS = 12


def set_clock(
    clocks: Sequence[Clock],
    *,
    name: str,
    segments: int,
    visible: bool,
    when_full: str,
    clock_id: str | None = None,
) -> tuple[Clock, ...]:
    """Return the clocks with one added (no ``clock_id``) or changed; a changed clock keeps what it has filled, within its new segments."""
    if not name.strip():
        raise ClockError("A clock needs a name.")
    if not MIN_SEGMENTS <= segments <= MAX_SEGMENTS:
        raise ClockError(f"A clock has {MIN_SEGMENTS} to {MAX_SEGMENTS} segments, not {segments}.")
    if clock_id is None:
        return (
            *clocks,
            Clock(name=name.strip(), segments=segments, visible=visible, when_full=when_full.strip()),
        )
    current = _find(clocks, clock_id)
    changed = current.model_copy(update={"name": name.strip(), "segments": segments, "filled": min(current.filled, segments), "visible": visible, "when_full": when_full.strip()})
    return tuple(changed if clock.id == clock_id else clock for clock in clocks)


def tick_clock(clocks: Sequence[Clock], clock_id: str, *, by: int) -> tuple[Clock, ...]:
    """Return the clocks with one moved by ``by`` segments (negative to roll back), kept within 0 and its segments."""
    if by == 0:
        raise ClockError("Tick by a number other than 0; use a negative number to roll a clock back.")
    current = _find(clocks, clock_id)
    moved = current.model_copy(update={"filled": max(0, min(current.segments, current.filled + by))})
    return tuple(moved if clock.id == clock_id else clock for clock in clocks)


def remove_clock(clocks: Sequence[Clock], clock_id: str) -> tuple[Clock, ...]:
    """Return the clocks without the one with this id."""
    _find(clocks, clock_id)
    return tuple(clock for clock in clocks if clock.id != clock_id)


def find_clock(clocks: Sequence[Clock], clock_id: str) -> Clock:
    """Return the clock with this id; raise ``ClockError`` naming the valid ids when there is none."""
    return _find(clocks, clock_id)


def render_clocks(clocks: Sequence[Clock]) -> str:
    """Render every clock, hidden ones too, one per line with its id."""
    if not clocks:
        return EMPTY_CLOCKS_TEXT
    return "\n".join(render_clock(clock) for clock in clocks)


def render_clock(clock: Clock) -> str:
    """Render one clock such as ``3f2a9c1d Vera's patience: 3/6, hidden. When full: she leaves.``"""
    line = f"{clock.id} {clock.name}: {clock.filled}/{clock.segments}, {'visible' if clock.visible else 'hidden'}."
    if clock.full:
        line += " FULL."
    return f"{line} When full: {clock.when_full}" if clock.when_full else line


def _find(clocks: Sequence[Clock], clock_id: str) -> Clock:
    current = next((clock for clock in clocks if clock.id == clock_id), None)
    if current is None:
        known = ", ".join(clock.id for clock in clocks) or "none, there are no clocks"
        raise ClockError(f"No clock has the id {clock_id!r}. Valid ids: {known}.")
    return current
