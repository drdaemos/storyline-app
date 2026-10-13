"""Tests that the terminal interface offers every room operation and draws every room event."""

from textual.binding import Binding

from storyline.agent import create_writer_agent
from storyline.room import EVENT_TYPES, Operation
from storyline.tui.models import TuiConfig
from storyline.tui.prompt import PromptInput
from storyline.tui.session import StorylineTui
from storyline.workspace import StoryLibrary
from storyline.workspace.file_workspace import FileWorkspace


def _app(tmp_path) -> StorylineTui:
    return StorylineTui(TuiConfig(library=StoryLibrary(FileWorkspace(tmp_path)), agent=create_writer_agent()))


def _keys(bindings: list) -> set[str]:
    """The keys of Textual bindings, which are written as ``Binding`` objects or ``(keys, action, description)`` tuples."""
    keys: set[str] = set()
    for binding in bindings:
        written = binding.key if isinstance(binding, Binding) else binding[0]
        keys.update(written.split(","))
    return keys


def test_every_room_event_has_a_handler_that_exists() -> None:
    assert set(StorylineTui.EVENT_HANDLERS) == set(EVENT_TYPES)
    for handler in StorylineTui.EVENT_HANDLERS.values():
        assert callable(getattr(StorylineTui, handler, None)), handler


def test_every_room_operation_is_offered_and_nothing_else() -> None:
    assert set(StorylineTui.OPERATION_BINDINGS) == set(Operation)


def test_every_slash_command_an_operation_names_is_registered(tmp_path) -> None:
    commands = _app(tmp_path)._commands
    named = {binding for binding in StorylineTui.OPERATION_BINDINGS.values() if binding.startswith("/")}

    assert named
    assert named <= set(commands)


def test_every_key_an_operation_names_is_bound() -> None:
    bound = _keys(StorylineTui.BINDINGS) | _keys(PromptInput.BINDINGS)
    named = {binding for binding in StorylineTui.OPERATION_BINDINGS.values() if not binding.startswith("/")}

    assert named
    assert named <= bound
