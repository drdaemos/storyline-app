"""The agenda, shown at the top of the screen while the story has one."""

from collections.abc import Sequence

from rich.text import Text
from textual.containers import VerticalScroll
from textual.widgets import Static

from storyline.workspace import AgendaItem

STATUS_MARKS = {"open": "○", "working": "●", "waiting": "◐", "settled": "✓", "dropped": "✗"}
WAITING_SUFFIX = "waiting on you"


def agenda_line(item: AgendaItem) -> str:
    """Return the one-line text for an item, e.g. ``✓ The city — Buffalo``."""
    line = f"{STATUS_MARKS[item.status]} {item.title}"
    if item.status == "waiting":
        return f"{line} — {WAITING_SUFFIX}"
    if item.status == "settled" and item.outcome:
        return f"{line} — {item.outcome}"
    return line


class AgendaPanel(VerticalScroll):
    """A bounded, scrolling list of agenda items; hidden while there are none."""

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

    async def show_items(self, items: Sequence[AgendaItem]) -> None:
        """Replace the displayed agenda; an empty one hides the panel."""
        self.items = tuple(items)
        self.set_class(bool(self.items), "-has-items")
        await self.remove_children()
        await self.mount_all([Static(_styled_line(item)) for item in self.items])


def _styled_line(item: AgendaItem) -> Text:
    return Text(agenda_line(item), style="dim strike" if item.status == "dropped" else "")
