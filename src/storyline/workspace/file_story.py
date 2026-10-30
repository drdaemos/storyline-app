"""Filesystem adapter for one story package."""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from pydantic import BaseModel, TypeAdapter, ValidationError
from pydantic_ai import ModelMessagesTypeAdapter
from pydantic_ai.messages import ModelMessage

from storyline.workspace.atomic_file import atomic_write
from storyline.workspace.contracts import (
    AgendaError,
    AgendaItem,
    Clock,
    ClockError,
    ConversationHistoryError,
    LoreEditError,
    LoreFile,
    Roll,
    RollLogError,
    StorySetup,
    StorySetupError,
    TextEdit,
)
from storyline.workspace.lore_format import lore_metadata
from storyline.workspace.text_edit import TextChange, append_text, replace_unique, snippet

SCRIPT_FILENAME = "script.md"
AGENDA_FILENAME = "agenda.json"
CLOCKS_FILENAME = "clocks.json"
ROLLS_FILENAME = "rolls.json"
CONVERSATION_HISTORY_FILENAME = ".storyline-history.json"
STORY_SETTINGS_FILENAME = ".storyline-settings.json"
SETUP_FILENAME = "story.json"
SEALED_DIRNAME = "sealed"
_LORE_NAME_RULE = "Lore filenames must be Markdown filenames beside script.md, or in the sealed folder as sealed/<name>.md."
_AGENDA_ADAPTER = TypeAdapter(tuple[AgendaItem, ...])
_CLOCKS_ADAPTER = TypeAdapter(tuple[Clock, ...])
_ROLLS_ADAPTER = TypeAdapter(tuple[Roll, ...])


class StorySettings(BaseModel):
    """Session settings a story keeps between runs."""

    model: str | None = None


type TextChanger = Callable[[str], TextChange]


@dataclass
class FileStory:
    """A story package stored as one local directory."""

    root: Path
    _write_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    @property
    def name(self) -> str:
        """Return the story's directory name."""
        return self.root.name

    @property
    def script_path(self) -> Path:
        """Return the fixed script location within this story."""
        return self.root / SCRIPT_FILENAME

    @property
    def conversation_history_path(self) -> Path:
        """Return the persisted Pydantic AI history location within this story."""
        return self.root / CONVERSATION_HISTORY_FILENAME

    @property
    def agenda_path(self) -> Path:
        """Return the agenda location within this story."""
        return self.root / AGENDA_FILENAME

    @property
    def clocks_path(self) -> Path:
        """Return the clocks location within this story."""
        return self.root / CLOCKS_FILENAME

    @property
    def rolls_path(self) -> Path:
        """Return the oracle roll log location: the log is sealed along with the rolls' questions."""
        return self.root / SEALED_DIRNAME / ROLLS_FILENAME

    async def read_script(self) -> str:
        """Return an empty script until the first edit creates it."""
        return await asyncio.to_thread(self._read_script)

    async def append_script(self, *, text: str) -> TextEdit:
        """Add text to the end of the script, creating it if needed."""
        return await self._locked(partial(self._change_script, partial(append_text, addition=text)))

    async def replace_in_script(self, *, find: str, replace: str) -> TextEdit:
        """Replace the one passage of the script that matches ``find``."""
        return await self._locked(partial(self._change_script, partial(replace_unique, find=find, replace=replace)))

    async def list_lore(self) -> tuple[LoreFile, ...]:
        """List Markdown lore files with their summary and keywords: the story's own, then the sealed ones."""
        return await asyncio.to_thread(self._list_lore)

    async def read_lore(self, *, filename: str) -> str:
        """Read one full Markdown lore file."""
        return await asyncio.to_thread(self._read_existing_lore, self._lore_path(filename))

    async def write_lore(self, *, filename: str, content: str) -> TextEdit:
        """Create a lore file or replace all of its content."""
        return await self._locked(partial(self._change_lore, filename, partial(_overwrite, content=content), create=True))

    async def append_lore(self, *, filename: str, text: str) -> TextEdit:
        """Add text to the end of an existing lore file."""
        return await self._locked(partial(self._change_lore, filename, partial(append_text, addition=text), create=False))

    async def replace_in_lore(self, *, filename: str, find: str, replace: str) -> TextEdit:
        """Replace the one passage of a lore file that matches ``find``."""
        change = partial(replace_unique, find=find, replace=replace)
        return await self._locked(partial(self._change_lore, filename, change, create=False))

    async def delete_lore(self, *, filename: str) -> None:
        """Remove an existing lore file."""
        await self._locked(partial(self._delete_lore, filename))

    async def read_agenda(self) -> tuple[AgendaItem, ...]:
        """Read the agenda; a story without one has an empty agenda."""
        return await self._locked(self._read_agenda)

    async def write_agenda(self, *, items: Sequence[AgendaItem]) -> None:
        """Replace the whole agenda."""
        await self._locked(partial(self._write_agenda, tuple(items)))

    async def change_agenda(self, *, change: Callable[[tuple[AgendaItem, ...]], Sequence[AgendaItem]]) -> tuple[AgendaItem, ...]:
        """Read, change and write the agenda under the write lock, so parallel tool calls apply one after another."""

        def read_change_write() -> tuple[AgendaItem, ...]:
            items = tuple(change(self._read_agenda()))
            self._write_agenda(items)
            return items

        return await self._locked(read_change_write)

    async def read_clocks(self) -> tuple[Clock, ...]:
        """Read the clocks; a story without any has none."""
        return await self._locked(self._read_clocks)

    async def change_clocks(self, *, change: Callable[[tuple[Clock, ...]], Sequence[Clock]]) -> tuple[Clock, ...]:
        """Read, change and write the clocks under the write lock, so parallel tool calls apply one after another."""

        def read_change_write() -> tuple[Clock, ...]:
            clocks = tuple(change(self._read_clocks()))
            atomic_write(self.clocks_path, _CLOCKS_ADAPTER.dump_json(clocks, indent=2))
            return clocks

        return await self._locked(read_change_write)

    async def read_rolls(self) -> tuple[Roll, ...]:
        """Read the logged oracle rolls, newest first; a story that never rolled has none."""
        return await self._locked(self._read_rolls)

    async def change_rolls(self, *, change: Callable[[tuple[Roll, ...]], Sequence[Roll]]) -> tuple[Roll, ...]:
        """Read, change and write the roll log under the write lock."""

        def read_change_write() -> tuple[Roll, ...]:
            rolls = tuple(change(self._read_rolls()))
            atomic_write(self.rolls_path, _ROLLS_ADAPTER.dump_json(rolls, indent=2))
            return rolls

        return await self._locked(read_change_write)

    @property
    def settings_path(self) -> Path:
        """Return the location of per-story session settings, such as the last model used."""
        return self.root / STORY_SETTINGS_FILENAME

    async def read_model_name(self) -> str | None:
        """Return the last model used with this story; unreadable settings count as none, since they only set a default."""
        return (await asyncio.to_thread(self._read_settings)).model

    async def write_model_name(self, *, model_name: str) -> None:
        """Remember the model, keeping any other settings."""

        def update() -> None:
            settings = self._read_settings().model_copy(update={"model": model_name})
            atomic_write(self.settings_path, settings.model_dump_json(indent=2).encode("utf-8"))

        await self._locked(update)

    @property
    def setup_path(self) -> Path:
        """Return the location of the story's setup record."""
        return self.root / SETUP_FILENAME

    async def read_setup(self) -> StorySetup:
        """Read the setup record; a story without one has the default setup."""
        return await asyncio.to_thread(self._read_setup)

    async def write_setup(self, *, setup: StorySetup) -> None:
        """Record the story's setup."""
        await self._locked(partial(atomic_write, self.setup_path, setup.model_dump_json(indent=2).encode("utf-8")))

    async def read_message_history(self) -> list[ModelMessage]:
        """Read the complete persisted Pydantic AI conversation history."""
        return await asyncio.to_thread(self._read_message_history)

    async def archive_message_history(self) -> str:
        """Move the saved history aside so a fresh conversation can start; return the archive filename."""
        return await self._locked(self._archive_message_history)

    async def write_message_history(self, *, message_history: list[ModelMessage]) -> None:
        """Persist Pydantic AI messages without losing tool call details."""
        serialized_history = ModelMessagesTypeAdapter.dump_json(message_history)
        await self._locked(partial(atomic_write, self.conversation_history_path, serialized_history))

    async def _locked[T](self, operation: Callable[[], T]) -> T:
        """Run a blocking write off the event loop, one at a time."""
        async with self._write_lock:
            return await asyncio.to_thread(operation)

    def _read_script(self) -> str:
        try:
            return self.script_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def _change_script(self, change: TextChanger) -> TextEdit:
        script = self._read_script()
        result = change(script)
        atomic_write(self.script_path, result.text.encode("utf-8"))
        return _text_edit(SCRIPT_FILENAME, script, result)

    def _list_lore(self) -> tuple[LoreFile, ...]:
        if not self.root.is_dir():
            return ()

        lore_files = [self._lore_file(path, sealed=False) for path in sorted(self.root.glob("*.md")) if path.name != SCRIPT_FILENAME]
        lore_files.extend(self._lore_file(path, sealed=True) for path in sorted((self.root / SEALED_DIRNAME).glob("*.md")) if path.is_file())
        return tuple(lore_files)

    def _lore_file(self, path: Path, *, sealed: bool) -> LoreFile:
        metadata = lore_metadata(path.read_text(encoding="utf-8"))
        return LoreFile(
            filename=path.relative_to(self.root).as_posix(),
            summary=metadata.get("summary") if metadata else None,
            keywords=metadata.get("keywords") if metadata else None,
            sealed=sealed,
        )

    def _read_existing_lore(self, path: Path) -> str:
        if not path.is_file():
            raise LoreEditError(f"Lore file does not exist: {path.relative_to(self.root).as_posix()}. Use write_lore to create it.")
        return path.read_text(encoding="utf-8")

    def _change_lore(self, filename: str, change: TextChanger, *, create: bool) -> TextEdit:
        path = self._lore_path(filename)
        name = self._lore_name(filename)
        if path.exists() and not path.is_file():
            raise LoreEditError(f"Lore path is not a file: {name}")
        if create:
            existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        else:
            existing = self._read_existing_lore(path)

        result = change(existing)
        metadata = lore_metadata(result.text)
        if metadata is None or not metadata.get("summary") or not metadata.get("keywords"):
            raise LoreEditError("Lore files must start with a hyphen-delimited header containing non-empty summary and keywords properties.")
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(path, result.text.encode("utf-8"))
        return _text_edit(name, existing, result)

    def _delete_lore(self, filename: str) -> None:
        path = self._lore_path(filename)
        self._read_existing_lore(path)
        path.unlink()

    def _write_agenda(self, items: tuple[AgendaItem, ...]) -> None:
        atomic_write(self.agenda_path, _AGENDA_ADAPTER.dump_json(items, indent=2))

    def _read_settings(self) -> StorySettings:
        try:
            return StorySettings.model_validate_json(self.settings_path.read_bytes())
        except (FileNotFoundError, ValidationError):
            return StorySettings()

    def _read_setup(self) -> StorySetup:
        try:
            serialized = self.setup_path.read_bytes()
        except FileNotFoundError:
            return StorySetup()
        try:
            return StorySetup.model_validate_json(serialized)
        except ValidationError as error:
            raise StorySetupError(f"{SETUP_FILENAME} is not a valid story setup (a JSON object with preset and mechanics): {error}") from error

    def _read_agenda(self) -> tuple[AgendaItem, ...]:
        try:
            serialized = self.agenda_path.read_bytes()
        except FileNotFoundError:
            return ()
        try:
            return _AGENDA_ADAPTER.validate_json(serialized)
        except ValidationError as error:
            raise AgendaError(f"{AGENDA_FILENAME} is not a valid agenda (a JSON list of items with id and title): {error}") from error

    def _read_clocks(self) -> tuple[Clock, ...]:
        try:
            serialized = self.clocks_path.read_bytes()
        except FileNotFoundError:
            return ()
        try:
            return _CLOCKS_ADAPTER.validate_json(serialized)
        except ValidationError as error:
            raise ClockError(f"{CLOCKS_FILENAME} is not a valid list of clocks (a JSON list with id, name, segments and visible): {error}") from error

    def _read_rolls(self) -> tuple[Roll, ...]:
        try:
            serialized = self.rolls_path.read_bytes()
        except FileNotFoundError:
            return ()
        try:
            return _ROLLS_ADAPTER.validate_json(serialized)
        except ValidationError as error:
            raise RollLogError(f"{SEALED_DIRNAME}/{ROLLS_FILENAME} is not a valid roll log: {error}") from error

    def _read_message_history(self) -> list[ModelMessage]:
        try:
            serialized_history = self.conversation_history_path.read_bytes()
        except FileNotFoundError:
            return []

        try:
            return ModelMessagesTypeAdapter.validate_json(serialized_history)
        except ValueError as error:
            raise ConversationHistoryError(f"Saved conversation history is invalid: {self.conversation_history_path}") from error

    def _archive_message_history(self) -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        archive_path = self.root / f".storyline-history.{timestamp}.broken.json"
        self.conversation_history_path.replace(archive_path)
        return archive_path.name

    def _lore_path(self, filename: str) -> Path:
        return self.root.joinpath(*_lore_parts(filename))

    def _lore_name(self, filename: str) -> str:
        """The filename as reported: relative to the story with ``/`` separators."""
        return "/".join(_lore_parts(filename))


def _lore_parts(filename: str) -> tuple[str, ...]:
    """Split a lore filename into its path parts: ``(name,)`` or ``("sealed", name)``; raise ``LoreEditError`` for anything else."""
    parts = filename.strip().replace("\\", "/").split("/")
    directory, name = (parts[0], parts[1]) if len(parts) == 2 else ("", parts[0])
    if len(parts) > 2 or (len(parts) == 2 and directory != SEALED_DIRNAME):
        raise LoreEditError(_LORE_NAME_RULE)
    if not name.strip() or name in {".", ".."}:
        raise LoreEditError(_LORE_NAME_RULE)
    if Path(name).suffix == "":
        name = f"{name}.md"
    if Path(name).suffix.lower() != ".md" or ":" in name or name.lower() == SCRIPT_FILENAME:
        raise LoreEditError(_LORE_NAME_RULE)
    return (directory, name) if directory else (name,)


def _overwrite(_: str, *, content: str) -> TextChange:
    return TextChange(text=content, start=0, end=len(content))


def _text_edit(filename: str, original: str, change: TextChange) -> TextEdit:
    return TextEdit(
        filename=filename,
        original_length=len(original),
        new_length=len(change.text),
        snippet=snippet(change.text, change.start, change.end),
    )
