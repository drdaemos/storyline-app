"""Inline prompt and slash-command list for the terminal UI."""

from collections.abc import Sequence
from dataclasses import dataclass

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import OptionList, Static, TextArea
from textual.widgets.option_list import Option

from storyline.tui.models import PromptCommand


class PromptInput(TextArea):
    """A multiline prompt input where Enter submits and Shift+Enter (or Ctrl+J) adds a line break."""

    BINDINGS = [
        # Priority so Enter is handled before TextArea inserts a newline for it.
        Binding("enter", "submit", "Submit", show=False, priority=True),
        Binding("shift+enter,ctrl+j", "insert_newline", "Insert line break", show=False),
    ]

    @dataclass
    class Submitted(Message):
        """Posted when the prompt is ready to send."""

        value: str

    def action_submit(self) -> None:
        """Send the current prompt to the enclosing prompt block."""
        self.post_message(self.Submitted(value=self.text))

    def action_insert_newline(self) -> None:
        """Insert a line break without submitting the prompt."""
        start, end = self.selection
        self.replace("\n", start, end, maintain_selection_offset=False)


class PromptBlock(Vertical):
    """A message input with matching slash commands directly above it."""

    BINDINGS = [("tab", "accept_completion", "Accept command")]

    DEFAULT_CSS = """
    PromptBlock {
        dock: bottom;
        margin-bottom: 2;
        padding: 0 2;
        height: auto;
        background: transparent;
    }
    PromptBlock TextArea {
        height: auto;
        min-height: 1;
        max-height: 6;
        padding: 1 1;
        border: none;
        background: #1e1e1e;
    }
    PromptBlock OptionList {
        display: none;
        height: auto;
        max-height: 8;
        padding: 0;
        border: none;
        background: transparent;
    }
    PromptBlock.-commands-visible OptionList { display: block; }
    PromptBlock #queued-prompts { display: none; height: auto; max-height: 4; color: $text-muted; text-style: italic; }
    PromptBlock.-has-queued #queued-prompts { display: block; }
    """

    @dataclass
    class Changed(Message):
        """Sent when the user changes the prompt."""

        value: str

    @dataclass
    class Submitted(Message):
        """Sent when the user submits a non-command-completion prompt; the value is stripped."""

        value: str

    def __init__(self, *, commands: tuple[PromptCommand, ...], id: str = "prompt") -> None:
        super().__init__(id=id)
        self._commands = commands
        self._matches: tuple[PromptCommand, ...] = ()
        self._queued: tuple[str, ...] = ()

    def compose(self) -> ComposeResult:
        yield Static(id="queued-prompts", markup=False)
        yield OptionList(id="command-list", markup=False, compact=True)
        yield PromptInput(id="prompt-input", compact=True, soft_wrap=True, show_line_numbers=False)

    @property
    def _input(self) -> PromptInput:
        return self.query_one(PromptInput)

    @property
    def value(self) -> str:
        """Return the current prompt value."""
        return self._input.text

    @value.setter
    def value(self, value: str) -> None:
        self._input.text = value
        self._input.cursor_location = self._input.document.end

    @property
    def command_count(self) -> int:
        """Return the number of commands currently displayed."""
        return len(self._matches)

    @property
    def placeholder(self) -> str:
        """Return the input placeholder."""
        return str(self._input.placeholder)

    @placeholder.setter
    def placeholder(self, value: str) -> None:
        self._input.placeholder = value

    @property
    def cursor_position(self) -> int:
        """Return the input cursor position as a character offset."""
        return self._input.document.get_index_from_location(self._input.cursor_location)

    @property
    def input_disabled(self) -> bool:
        """Return whether the input accepts text."""
        return self._input.disabled

    @input_disabled.setter
    def input_disabled(self, disabled: bool) -> None:
        self._input.disabled = disabled

    @property
    def queued(self) -> tuple[str, ...]:
        """Return the prompts shown as waiting for the agent."""
        return self._queued

    def show_queued(self, prompts: Sequence[str]) -> None:
        """Show prompts that the agent has not read yet above the input."""
        self._queued = tuple(prompts)
        lines = [f"queued › {' '.join(prompt.split())}" for prompt in self._queued]
        self.query_one("#queued-prompts", Static).update("\n".join(lines))
        self.set_class(bool(self._queued), "-has-queued")

    def clear(self) -> None:
        """Clear the prompt input."""
        self.value = ""

    def focus_input(self) -> None:
        """Focus the prompt input."""
        self._input.focus()

    def action_accept_completion(self) -> None:
        """Accept the single matching slash command."""
        if len(self._matches) == 1:
            self._select_command(self._matches[0])

    @on(PromptInput.Changed)
    def _on_input_changed(self, event: PromptInput.Changed) -> None:
        event.stop()
        value = event.text_area.text
        self._matches = self._matching_commands(value)
        self._render_commands()
        self.post_message(self.Changed(value=value))

    @on(PromptInput.Submitted)
    def _on_input_submitted(self, event: PromptInput.Submitted) -> None:
        event.stop()
        is_complete_command = any(command.name == event.value for command in self._matches)
        if len(self._matches) == 1 and not is_complete_command:
            self._select_command(self._matches[0])
            return
        self.post_message(self.Submitted(value=event.value.strip()))

    @on(OptionList.OptionSelected)
    def _on_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        if event.option_index < len(self._matches):
            self._select_command(self._matches[event.option_index])

    def _matching_commands(self, value: str) -> tuple[PromptCommand, ...]:
        if not value.startswith("/") or _contains_whitespace(value):
            return ()
        normalized_value = value.casefold()
        return tuple(command for command in self._commands if command.name.casefold().startswith(normalized_value))

    def _render_commands(self) -> None:
        options = [Option(_command_text(command)) for command in self._matches]
        self.query_one(OptionList).set_options(options)
        self.set_class(bool(options), "-commands-visible")

    def _select_command(self, command: PromptCommand) -> None:
        self.value = f"{command.name} "
        self.focus_input()


def _command_text(command: PromptCommand) -> Text:
    return Text.assemble((command.name, "bold"), (f"  {command.description}", "dim"))


def _contains_whitespace(value: str) -> bool:
    """Return whether a command candidate contains whitespace."""
    return any(character.isspace() for character in value)
