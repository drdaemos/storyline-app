"""Filesystem adapter for one story package."""

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from pydantic_ai import ModelMessagesTypeAdapter
from pydantic_ai.messages import ModelMessage

from storyline.workspace.atomic_file import atomic_write
from storyline.workspace.contracts import ConversationHistoryError, LoreEditError, LoreFile, TextEdit
from storyline.workspace.text_edit import TextChange, append_text, replace_unique, snippet

SCRIPT_FILENAME = "script.md"
CONVERSATION_HISTORY_FILENAME = ".storyline-history.json"
LORE_HEADER_DELIMITER = re.compile(r"-{3,}\s*")
LORE_HEADER_PROPERTY = re.compile(r"(?P<key>[^:\s][^:]*):\s*(?P<value>.*)")

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
        """List Markdown lore files with their summary and keywords."""
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

        lore_files: list[LoreFile] = []
        for path in sorted(self.root.glob("*.md")):
            if path.name == SCRIPT_FILENAME:
                continue
            metadata = _lore_metadata(path.read_text(encoding="utf-8"))
            lore_files.append(
                LoreFile(
                    filename=path.name,
                    summary=metadata.get("summary") if metadata else None,
                    keywords=metadata.get("keywords") if metadata else None,
                )
            )
        return tuple(lore_files)

    def _read_existing_lore(self, path: Path) -> str:
        if not path.is_file():
            raise LoreEditError(f"Lore file does not exist: {path.name}. Use write_lore to create it.")
        return path.read_text(encoding="utf-8")

    def _change_lore(self, filename: str, change: TextChanger, *, create: bool) -> TextEdit:
        path = self._lore_path(filename)
        if path.exists() and not path.is_file():
            raise LoreEditError(f"Lore path is not a file: {path.name}")
        if create:
            existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        else:
            existing = self._read_existing_lore(path)

        result = change(existing)
        metadata = _lore_metadata(result.text)
        if metadata is None or not metadata.get("summary") or not metadata.get("keywords"):
            raise LoreEditError("Lore files must start with a hyphen-delimited header containing non-empty summary and keywords properties.")
        atomic_write(path, result.text.encode("utf-8"))
        return _text_edit(path.name, existing, result)

    def _delete_lore(self, filename: str) -> None:
        path = self._lore_path(filename)
        self._read_existing_lore(path)
        path.unlink()

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
        relative_path = Path(filename.strip())
        if relative_path.suffix == "":
            relative_path = relative_path.with_suffix(".md")
        if (
            not filename.strip()
            or relative_path.is_absolute()
            or relative_path.drive
            or len(relative_path.parts) != 1
            or relative_path.suffix.lower() != ".md"
            or relative_path.name.lower() == SCRIPT_FILENAME
        ):
            raise LoreEditError("Lore filenames must be Markdown filenames beside script.md.")
        return self.root.joinpath(relative_path)


def _overwrite(_: str, *, content: str) -> TextChange:
    return TextChange(text=content, start=0, end=len(content))


def _text_edit(filename: str, original: str, change: TextChange) -> TextEdit:
    return TextEdit(
        filename=filename,
        original_length=len(original),
        new_length=len(change.text),
        snippet=snippet(change.text, change.start, change.end),
    )


def _lore_metadata(content: str) -> dict[str, str] | None:
    lines = content.splitlines()
    if not lines or LORE_HEADER_DELIMITER.fullmatch(lines[0]) is None:
        return None

    properties: dict[str, str] = {}
    for line in lines[1:]:
        if LORE_HEADER_DELIMITER.fullmatch(line):
            if properties:
                return properties
            return None
        if not line.strip():
            continue
        property_match = LORE_HEADER_PROPERTY.fullmatch(line)
        if property_match is None:
            return None
        key = property_match.group("key").strip().lower()
        if key in properties:
            return None
        properties[key] = property_match.group("value").strip()
    return None
