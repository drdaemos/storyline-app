"""Typed data objects shared by the terminal UI."""

from dataclasses import dataclass, field
from enum import StrEnum

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage

from storyline.agent import DEFAULT_MODEL_NAME
from storyline.workspace import ScriptWorkspace


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

    workspace: ScriptWorkspace
    agent: Agent[ScriptWorkspace, str]
    initial_model_name: str = DEFAULT_MODEL_NAME


@dataclass
class TuiState:
    """Mutable state owned by one terminal session."""

    model_name: str
    message_history: list[ModelMessage] = field(default_factory=list)
