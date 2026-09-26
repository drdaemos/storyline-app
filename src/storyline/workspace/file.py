"""Filesystem adapter for the writing workspace interface."""

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path

from pydantic_ai import ModelMessagesTypeAdapter
from pydantic_ai.messages import ModelMessage

from storyline.workspace.contracts import (
    ConversationHistoryError,
    LoreAction,
    LoreEdit,
    LoreEditError,
    LoreFile,
    ScriptEdit,
    ScriptEditError,
)

SCRIPT_FILENAME = "script.md"
CONVERSATION_HISTORY_FILENAME = ".storyline-history.json"
LORE_HEADER_DELIMITER = re.compile(r"-{3,}\s*")
LORE_HEADER_PROPERTY = re.compile(r"(?P<key>[^:\s][^:]*):\s*(?P<value>.*)")


@dataclass
class FileWorkspace:
    """A local directory-backed writing workspace adapter."""

    root: Path
    _write_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    @property
    def script_path(self) -> Path:
        """Return the fixed script location within this workspace."""
        return self.root / SCRIPT_FILENAME

    @property
    def conversation_history_path(self) -> Path:
        """Return the persisted Pydantic AI history location within this workspace."""
        return self.root / CONVERSATION_HISTORY_FILENAME

    async def read_script(self) -> str:
        """Return an empty script until the first edit creates it."""
        return await asyncio.to_thread(self._read_script)

    async def apply_edit(
        self,
        *,
        start_offset: int,
        replacement: str,
        end_offset: int | None = None,
    ) -> ScriptEdit:
        """Apply one focused replacement and persist the resulting script."""
        async with self._write_lock:
            return await asyncio.to_thread(
                self._apply_edit,
                start_offset=start_offset,
                end_offset=end_offset,
                replacement=replacement,
            )

    async def list_lore(self) -> tuple[LoreFile, ...]:
        """List Markdown lore files with their summary and keywords."""
        return await asyncio.to_thread(self._list_lore)

    async def read_lore(self, *, filename: str) -> str:
        """Read one full Markdown lore file."""
        return await asyncio.to_thread(self._read_lore, filename=filename)

    async def edit_lore(
        self,
        *,
        filename: str,
        action: LoreAction,
        content: str | None = None,
        start_offset: int | None = None,
        end_offset: int | None = None,
    ) -> LoreEdit:
        """Apply one focused change to a Markdown lore file."""
        async with self._write_lock:
            return await asyncio.to_thread(
                self._edit_lore,
                filename=filename,
                action=action,
                content=content,
                start_offset=start_offset,
                end_offset=end_offset,
            )

    async def read_message_history(self) -> list[ModelMessage]:
        """Read the complete persisted Pydantic AI conversation history."""
        return await asyncio.to_thread(self._read_message_history)

    async def write_message_history(self, *, message_history: list[ModelMessage]) -> None:
        """Persist Pydantic AI messages without losing tool call details."""
        serialized_history = ModelMessagesTypeAdapter.dump_json(message_history)
        async with self._write_lock:
            await asyncio.to_thread(self._write_message_history, serialized_history)

    def _read_script(self) -> str:
        try:
            return self.script_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def _apply_edit(self, *, start_offset: int, end_offset: int | None, replacement: str) -> ScriptEdit:
        script = self._read_script()
        resolved_end_offset = _resolve_end_offset(start_offset, end_offset, replacement)
        if not _is_valid_range(start_offset, resolved_end_offset, len(script)):
            raise ScriptEditError(_invalid_range_message(start_offset, resolved_end_offset, "script", len(script)))
        updated_script = f"{script[:start_offset]}{replacement}{script[resolved_end_offset:]}"
        self.root.mkdir(parents=True, exist_ok=True)
        self.script_path.write_text(updated_script, encoding="utf-8")
        return ScriptEdit(
            start_offset=start_offset,
            end_offset=resolved_end_offset,
            original_length=len(script),
            new_length=len(updated_script),
        )

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

    def _read_lore(self, *, filename: str) -> str:
        path = self._lore_path(filename)
        if not path.is_file():
            raise LoreEditError(f"Lore file does not exist: {filename}")
        return path.read_text(encoding="utf-8")

    def _edit_lore(
        self,
        *,
        filename: str,
        action: LoreAction,
        content: str | None,
        start_offset: int | None,
        end_offset: int | None,
    ) -> LoreEdit:
        path = self._lore_path(filename)
        if path.exists() and not path.is_file():
            raise LoreEditError(f"Lore path is not a file: {filename}")

        existing = path.read_text(encoding="utf-8") if path.is_file() else None
        original_length = len(existing) if existing is not None else 0
        if action == "delete":
            if existing is not None:
                path.unlink()
            return LoreEdit(
                filename=path.name,
                action=action,
                original_length=original_length,
                new_length=0,
            )

        if content is None:
            raise LoreEditError(f"{action.capitalize()} requires content.")
        if existing is None:
            updated = content
        elif action == "append":
            updated = f"{existing}{content}"
        else:
            if start_offset is None:
                raise LoreEditError("Replace requires start_offset.")
            resolved_end_offset = _resolve_end_offset(start_offset, end_offset, content)
            if not _is_valid_range(start_offset, resolved_end_offset, len(existing)):
                raise LoreEditError(_invalid_range_message(start_offset, resolved_end_offset, path.name, len(existing)))
            updated = f"{existing[:start_offset]}{content}{existing[resolved_end_offset:]}"

        metadata = _lore_metadata(updated)
        if metadata is None or not metadata.get("summary") or not metadata.get("keywords"):
            raise LoreEditError(
                "Lore files must start with a hyphen-delimited header containing non-empty summary and keywords properties."
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(updated, encoding="utf-8")
        return LoreEdit(
            filename=path.name,
            action=action,
            original_length=original_length,
            new_length=len(updated),
        )

    def _read_message_history(self) -> list[ModelMessage]:
        try:
            serialized_history = self.conversation_history_path.read_bytes()
        except FileNotFoundError:
            return []

        try:
            return ModelMessagesTypeAdapter.validate_json(serialized_history)
        except ValueError as error:
            raise ConversationHistoryError(
                f"Saved conversation history is invalid: {self.conversation_history_path}"
            ) from error

    def _write_message_history(self, serialized_history: bytes) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.conversation_history_path.write_bytes(serialized_history)

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


def _is_valid_range(start_offset: int, end_offset: int, length: int) -> bool:
    return 0 <= start_offset <= end_offset <= length


def _invalid_range_message(start_offset: int, end_offset: int, target: str, length: int) -> str:
    return f"Invalid edit range {start_offset}:{end_offset} for {target} with {length} characters."


def _resolve_end_offset(start_offset: int, end_offset: int | None, replacement: str) -> int:
    if end_offset is not None:
        return end_offset
    return start_offset + len(replacement)


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
