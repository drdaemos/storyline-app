"""Interactive presentation of conversation and tool activity."""

from collections.abc import Sequence

from rich.console import RenderableType
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Collapsible, Markdown, Static
from textual.widgets.markdown import MarkdownStream

from storyline.room import Entry, MessageEntry
from storyline.tui.markdown import terminal_markdown
from storyline.tui.models import MessageKind

SEALED_DETAILS_NOTICE = "The details are hidden because this call touches sealed lore · /sealed peeks at the sealed files."


class ChatMessage(Static):
    """One plain conversation entry: a user prompt, notice or error."""

    def __init__(self, kind: MessageKind, body: str) -> None:
        super().__init__(_renderable(kind, body), classes=f"message {kind}")
        self.kind = kind
        self.body = body


class AgentReply(Markdown):
    """An agent reply rendered as Markdown, appended to incrementally while it streams."""

    DEFAULT_CSS = """
    AgentReply { margin: 0 0 1 0; padding: 0; background: transparent; }
    """

    def __init__(self, body: str = "") -> None:
        super().__init__(body, classes="message agent", parser_factory=terminal_markdown)
        self.body = body
        self._stream: MarkdownStream | None = None

    async def stream_text(self, fragment: str) -> None:
        """Add streamed text without re-rendering what is already shown."""
        self.body += fragment
        if self._stream is None:
            self._stream = Markdown.get_stream(self)
        await self._stream.write(fragment)

    async def finish(self) -> None:
        """Flush any buffered text."""
        if self._stream is not None:
            await self._stream.stop()
            self._stream = None


class ToolLogEntry(Collapsible):
    """One collapsed log entry for a tool call; expanding it shows the request and result."""

    DEFAULT_CSS = """
    ToolLogEntry { margin-bottom: 1; border: none; padding: 0; background: transparent; }
    ToolLogEntry .tool-details { color: $text-muted; }
    """

    def __init__(self, *, tool_name: str, arguments: str, result: str | None = None, outcome: str = "working", sealed: bool = False) -> None:
        self._tool_name = tool_name
        self._arguments = arguments
        self._sealed = sealed
        self._details = Static(self._details_text(result), classes="tool-details")
        super().__init__(self._details, title=self._heading(outcome), classes="message tool")

    def complete(self, *, result: str, outcome: str, sealed: bool = False) -> None:
        """Attach a result while keeping it in the existing tool entry; a sealed call stays hidden."""
        self._sealed = self._sealed or sealed
        self.title = self._heading(outcome)
        self._details.update(self._details_text(result))

    def _heading(self, outcome: str) -> str:
        return f"{self._tool_name} · {outcome}" + (" · sealed" if self._sealed else "")

    def _details_text(self, result: str | None) -> Text:
        if self._sealed:
            return Text(SEALED_DETAILS_NOTICE)
        return Text(f"Request\n{self._arguments}\n\nResult\n{result or 'Waiting for result.'}")


class ActivityLine(Static):
    """What the agent is doing right now, kept below the newest entry."""

    DEFAULT_CSS = """
    ActivityLine { display: none; color: $text-muted; text-style: italic; }
    ActivityLine.-active { display: block; }
    """

    def show(self, activity: str) -> None:
        """Show ``activity``, or hide the line when it is empty."""
        self.update(activity)
        self.set_class(bool(activity), "-active")


class MessageLog(VerticalScroll):
    """A scrollable log that stays anchored to the newest entry until the reader scrolls away."""

    DEFAULT_CSS = """
    MessageLog { height: 1fr; padding: 1 4 1 2; }
    MessageLog .message { margin-bottom: 1; }
    MessageLog .user { color: $accent; background: $surface-lighten-1; }
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
        self._reader_away = False
        self._activity = ActivityLine()

    def compose(self) -> ComposeResult:
        yield self._activity

    def on_mount(self) -> None:
        self.anchor()

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        super().watch_scroll_y(old_value, new_value)
        self._reader_away = not self.is_vertical_scroll_end
        if not self._reader_away:
            self.post_message(self.ReachedBottom())

    def show_activity(self, activity: str) -> None:
        """Show what the agent is doing as the last item, or hide it when ``activity`` is empty."""
        self._activity.show(activity)

    async def add_message(self, kind: MessageKind, body: str) -> ChatMessage:
        """Add one plain conversation entry."""
        message = ChatMessage(kind, body)
        await self._mount_entries([message])
        return message

    async def add_reply(self) -> AgentReply:
        """Add an empty agent reply to stream into."""
        reply = AgentReply()
        await self._mount_entries([reply])
        return reply

    async def append_to_reply(self, reply: AgentReply, text: str) -> None:
        """Extend a streamed reply."""
        await reply.stream_text(text)
        self._content_changed()

    async def add_tool_call(self, *, tool_call_id: str, tool_name: str, arguments: str, sealed: bool = False) -> ToolLogEntry:
        """Add a compact tool entry whose details are available on click, unless the call is sealed."""
        entry = ToolLogEntry(tool_name=tool_name, arguments=arguments, sealed=sealed)
        self._tool_entries[tool_call_id] = entry
        await self._mount_entries([entry])
        return entry

    def complete_tool_call(self, *, tool_call_id: str, result: str, outcome: str, sealed: bool = False) -> None:
        """Attach a result to its existing tool entry."""
        entry = self._tool_entries.pop(tool_call_id, None)
        if entry is not None:
            entry.complete(result=result, outcome=outcome, sealed=sealed)
            self._content_changed()

    async def show_transcript(self, entries: Sequence[Entry], *, hidden_count: int = 0) -> None:
        """Add entries restored from a saved conversation."""
        widgets: list[Widget] = []
        if hidden_count:
            widgets.append(ChatMessage(MessageKind.SYSTEM, f"… {hidden_count} earlier entries not shown"))
        for entry in entries:
            if isinstance(entry, MessageEntry):
                widgets.append(AgentReply(entry.text) if entry.role == "writer" else ChatMessage(MessageKind.USER, entry.text))
            else:
                widgets.append(
                    ToolLogEntry(
                        tool_name=entry.tool_name,
                        arguments=entry.arguments,
                        result=entry.result,
                        outcome=entry.outcome,
                        sealed=entry.sealed,
                    )
                )
        await self._mount_entries(widgets)

    async def clear(self) -> None:
        """Remove every entry."""
        self._tool_entries.clear()
        await self.query_children(".message").remove()

    async def _mount_entries(self, widgets: Sequence[Widget]) -> None:
        if widgets:
            await self.mount_all(widgets, before=self._activity)
            self._content_changed()

    def _content_changed(self) -> None:
        if self._reader_away:
            self.post_message(self.NewMessages())


def _renderable(kind: MessageKind, body: str) -> RenderableType:
    if kind == MessageKind.USER:
        return Text.assemble(("> ", "bold"), body)
    return Text(body)
