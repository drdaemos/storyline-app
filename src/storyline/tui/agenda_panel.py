"""The agenda, shown at the top of the screen while the story has one."""

from collections.abc import Sequence

from rich.text import Text
from textual.containers import VerticalScroll
from textual.widgets import Static

from storyline.room import ClockView
from storyline.workspace import AgendaItem

STATUS_MARKS = {"open": "○", "working": "●", "waiting": "◐", "settled": "✓", "dropped": "✗"}
WAITING_SUFFIX = "waiting on you"
CLOCKS_HEADING = "Clocks"


def agenda_line(item: AgendaItem) -> str:
    """Return the one-line text for an item, e.g. ``✓ The city — Buffalo``."""
    line = f"{STATUS_MARKS[item.status]} {item.title}"
    if item.status == "waiting":
        return f"{line} — {WAITING_SUFFIX}"
    if item.status == "settled" and item.outcome:
        return f"{line} — {item.outcome}"
    return line


def clock_line(clock: ClockView) -> str:
    """Return the one-line text for a clock, e.g. ``Dawn ■■□□□□ 2/6``; a full clock ends with a mark."""
    empty = max(clock.segments - clock.filled, 0)
    line = f"{clock.name} {'■' * clock.filled}{'□' * empty} {clock.filled}/{clock.segments}"
    return f"{line} ✓ full" if clock.filled >= clock.segments else line


def hidden_clocks_line(hidden: int) -> str:
    """Return the line that counts the clocks the user may not see, without naming them."""
    return f"{hidden} hidden"


class AgendaPanel(VerticalScroll):
    """A bounded, scrolling list of agenda items, then the story's clocks; hidden while there is neither."""

    DEFAULT_CSS = """
    AgendaPanel {
        dock: top;
        display: none;
        height: auto;
        max-height: 8;
        padding: 0 3;
        margin-bottom: 1;
        background: transparent;
    }
    AgendaPanel.-has-items { display: block; }
    AgendaPanel Static { height: auto; }
    """

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self.items: tuple[AgendaItem, ...] = ()
        self.clocks: tuple[ClockView, ...] = ()
        self.hidden_clocks = 0

    async def show_items(self, items: Sequence[AgendaItem]) -> None:
        """Replace the displayed agenda; with no clocks either, the panel hides."""
        self.items = tuple(items)
        await self._redraw()

    async def show_clocks(self, clocks: Sequence[ClockView], hidden: int = 0) -> None:
        """Replace the displayed clocks and the count of hidden ones; with no agenda either, the panel hides."""
        self.clocks = tuple(clocks)
        self.hidden_clocks = hidden
        await self._redraw()

    async def _redraw(self) -> None:
        has_clocks = bool(self.clocks) or self.hidden_clocks > 0
        self.set_class(bool(self.items) or has_clocks, "-has-items")
        lines: list[Static] = [Static(_styled_line(item)) for item in self.items]
        if has_clocks:
            lines.append(Static(Text(CLOCKS_HEADING, style="bold")))
            lines.extend(Static(Text(clock_line(clock))) for clock in self.clocks)
            if self.hidden_clocks > 0:
                lines.append(Static(Text(hidden_clocks_line(self.hidden_clocks), style="dim")))
        await self.remove_children()
        await self.mount_all(lines)


def _styled_line(item: AgendaItem) -> Text:
    return Text(agenda_line(item), style="dim strike" if item.status == "dropped" else "")
