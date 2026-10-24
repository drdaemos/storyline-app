"""Typed data objects shared by the terminal UI."""

from dataclasses import dataclass
from enum import StrEnum

from pydantic_ai import Agent

from storyline.agent import DEFAULT_MODEL_NAME
from storyline.presets import BUNDLED_PRESETS, PresetCatalog
from storyline.room import StoryRoom
from storyline.workspace import Story, StoryLibrary


class MessageKind(StrEnum):
    """Visual category for a conversation entry."""

    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    ERROR = "error"


@dataclass(frozen=True)
class PromptCommand:
    """A command offered by the prompt's inline command list."""

    name: str
    description: str


@dataclass(frozen=True)
class TuiConfig:
    """Dependencies and initial settings supplied by the composition root."""

    library: StoryLibrary
    agent: Agent[Story, str]
    initial_model_name: str = DEFAULT_MODEL_NAME
    requested_story: str | None = None
    """The story named on the command line; without one, the session resumes the last active story."""
    presets: PresetCatalog = BUNDLED_PRESETS
    """The kinds of story ``/new --as`` offers."""


@dataclass
class TuiState:
    """Mutable state owned by one terminal session."""

    default_model_name: str
    """The model for stories that do not remember one; changed by ``/model`` while no story is open."""
    room: StoryRoom | None = None

    @property
    def story(self) -> Story | None:
        return self.room.story if self.room is not None else None

    @property
    def model_name(self) -> str:
        return self.room.model_name if self.room is not None else self.default_model_name
