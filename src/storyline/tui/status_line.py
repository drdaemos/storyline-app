"""One-line status and key hints shown below the prompt."""

from textual.reactive import reactive
from textual.widget import Widget

NEW_MESSAGES_STATUS = "new messages below · scroll down to follow"


class StatusLine(Widget):
    """Shows the current activity or key hints, plus an unseen-messages notice."""

    DEFAULT_CSS = """
    StatusLine { dock: bottom; height: 2; padding: 0 2 1 2; color: $text-muted; }
    """

    text: reactive[str] = reactive("")
    has_unseen_messages: reactive[bool] = reactive(False)

    def render(self) -> str:
        if self.has_unseen_messages:
            return f"{self.text} · {NEW_MESSAGES_STATUS}"
        return self.text
