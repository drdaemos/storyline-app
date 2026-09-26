"""Interactive presentation of conversation and tool activity."""

from collections.abc import Iterator
from contextlib import contextmanager

from rich.console import RenderableType
from rich.markdown import Markdown
from rich.text import Text
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Collapsible, Static

from storyline.tui.models import MessageKind


class ChatMessage(Static):
    """One conversation entry whose body can grow while a reply streams in."""

    def __init__(self, kind: MessageKind, body: str) -> None:
        super().__init__(_renderable(kind, body), classes=f"message {kind}")
        self.kind = kind
        self.body = body

    def append(self, text: str) -> None:
        """Extend the body and re-render it."""
        self.body += text
        self.update(_renderable(self.kind, self.body))


class ToolLogEntry(Collapsible):
    """One collapsed log entry for a tool call; expanding it shows the request and result."""

    DEFAULT_CSS = """
    ToolLogEntry { margin-bottom: 1; border: none; padding: 0; background: transparent; }
    ToolLogEntry .tool-details { color: $text-muted; }
    """

    def __init__(self, *, tool_name: str, arguments: str) -> None:
        self._tool_name = tool_name
        self._arguments = arguments
        super().__init__(
            Static(self._details(None), classes="tool-details"),
            title=f"{tool_name} · working",
            classes="message tool",
        )

    def complete(self, *, content: object, outcome: str) -> None:
        """Attach a result while keeping it in the existing tool entry."""
        self.title = f"{self._tool_name} · {outcome}"
        self.query_one(".tool-details", Static).update(self._details(str(content)))

    def _details(self, result: str | None) -> Text:
        return Text(f"Request\n{self._arguments}\n\nResult\n{result or 'Waiting for result.'}")


class MessageLog(VerticalScroll):
    """A scrollable log that follows updates until the reader scrolls away."""

    DEFAULT_CSS = """
    MessageLog { height: 1fr; padding: 1 2; }
    MessageLog .message { margin-bottom: 1; }
    MessageLog .user { color: $accent; background: $surface-lighten-1; }
    MessageLog .agent { color: $text; }
    MessageLog .system, MessageLog .tool { color: $warning; }
    MessageLog .error { color: $error; }
    """

    class ReachedBottom(Message):
        """The reader has returned to the newest message."""

    class NewMessages(Message):
        """New content arrived while the reader was viewing older entries."""

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._tool_entries: dict[str, ToolLogEntry] = {}

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        super().watch_scroll_y(old_value, new_value)
        if self.is_vertical_scroll_end:
            self.post_message(self.ReachedBottom())

    async def add_message(self, kind: MessageKind, body: str) -> ChatMessage:
        """Add one conversation entry."""
        message = ChatMessage(kind, body)
        with self._following_changes():
            await self.mount(message)
        return message

    def append_to_message(self, message: ChatMessage, text: str) -> None:
        """Extend a streamed message."""
        with self._following_changes():
            message.append(text)

    async def add_tool_call(self, *, tool_call_id: str, tool_name: str, arguments: str) -> ToolLogEntry:
        """Add a compact tool entry whose details are available on click."""
        entry = ToolLogEntry(tool_name=tool_name, arguments=arguments)
        self._tool_entries[tool_call_id] = entry
        with self._following_changes():
            await self.mount(entry)
        return entry

    def complete_tool_call(self, *, tool_call_id: str, content: object, outcome: str) -> None:
        """Attach a result to its existing tool entry."""
        entry = self._tool_entries.pop(tool_call_id, None)
        if entry is None:
            return
        with self._following_changes():
            entry.complete(content=content, outcome=outcome)

    @contextmanager
    def _following_changes(self) -> Iterator[None]:
        """Keep the newest entry in view if the reader was already there; otherwise flag unseen content."""
        follows_log = self.is_vertical_scroll_end
        yield
        if follows_log:
            self.scroll_end(animate=False)
        else:
            self.post_message(self.NewMessages())


def _renderable(kind: MessageKind, body: str) -> RenderableType:
    if kind == MessageKind.AGENT:
        return Markdown(body)
    if kind == MessageKind.USER:
        return Text.assemble(("> ", "bold"), body)
    return Text(body)
