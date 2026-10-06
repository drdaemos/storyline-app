"""Filesystem adapter for a workspace that holds many stories, one directory each."""

import asyncio
import re
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

from pydantic import BaseModel, ValidationError

from storyline.workspace.atomic_file import atomic_write
from storyline.workspace.contracts import StorySelectionError
from storyline.workspace.file_story import FileStory

STATE_DIRECTORY = ".storyline"
STATE_FILENAME = "state.json"
INVALID_STORY_NAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


class WorkspaceState(BaseModel):
    """Workspace-level settings persisted between sessions."""

    active_story: str | None = None


@dataclass
class FileWorkspace:
    """A local directory whose visible subdirectories are story packages."""

    root: Path
    _write_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    @property
    def state_path(self) -> Path:
        """Return the location of the workspace-level state file."""
        return self.root / STATE_DIRECTORY / STATE_FILENAME

    async def list_stories(self) -> tuple[str, ...]:
        """Return the names of every story directory, sorted."""
        return await asyncio.to_thread(self._list_stories)

    async def create_story(self, *, name: str) -> FileStory:
        """Create a new, empty story directory."""
        async with self._write_lock:
            return await asyncio.to_thread(self._create_story, name)

    async def open_story(self, *, name: str) -> FileStory:
        """Open an existing story directory."""
        if name not in await self.list_stories():
            raise StorySelectionError(f"There is no story named {name!r}.")
        return FileStory(root=self.root / name)

    async def read_active_story(self) -> str | None:
        """Return the story that was active last; unreadable state is treated as no record."""
        return await asyncio.to_thread(self._read_active_story)

    async def write_active_story(self, *, name: str) -> None:
        """Record the story that is active now."""
        state = WorkspaceState(active_story=name).model_dump_json().encode("utf-8")
        async with self._write_lock:
            await asyncio.to_thread(partial(atomic_write, self.state_path, state))

    def _list_stories(self) -> tuple[str, ...]:
        if not self.root.is_dir():
            return ()
        return tuple(sorted(path.name for path in self.root.iterdir() if path.is_dir() and not path.name.startswith(".")))

    def _create_story(self, name: str) -> FileStory:
        path = self.root / _valid_story_name(name)
        try:
            path.mkdir(parents=True)
        except FileExistsError as error:
            raise StorySelectionError(f"A story named {path.name!r} already exists.") from error
        return FileStory(root=path)

    def _read_active_story(self) -> str | None:
        try:
            return WorkspaceState.model_validate_json(self.state_path.read_bytes()).active_story
        except (FileNotFoundError, ValidationError):
            return None


def _valid_story_name(name: str) -> str:
    """Return ``name`` if it can be used as a single, visible directory name on every platform."""
    stripped = name.strip()
    if not stripped or stripped.startswith(".") or stripped.endswith(".") or INVALID_STORY_NAME.search(stripped) is not None:
        raise StorySelectionError('Story names must not be empty, start or end with a dot, or contain \\ / : * ? " < > |.')
    return stripped
