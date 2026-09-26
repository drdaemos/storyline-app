"""Conversion of persisted model messages into displayable log entries."""

from collections.abc import Sequence
from dataclasses import dataclass

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from storyline.agent import visible_prompt_text
from storyline.tui.models import MessageKind


@dataclass(frozen=True)
class TranscriptMessage:
    """A user prompt or agent reply."""

    kind: MessageKind
    body: str


@dataclass(frozen=True)
class TranscriptToolCall:
    """A tool call with its result, if one was recorded."""

    tool_name: str
    arguments: str
    result: str | None
    outcome: str


TranscriptEntry = TranscriptMessage | TranscriptToolCall


def tool_result_summary(part: ToolReturnPart | RetryPromptPart) -> tuple[str, str]:
    """Return the displayable result text and outcome of a tool result."""
    if isinstance(part, ToolReturnPart):
        return str(part.content), part.outcome
    return part.model_response(), "retry"


def transcript_entries(history: Sequence[ModelMessage]) -> list[TranscriptEntry]:
    """Return the user prompts, agent replies and tool calls of a conversation in order."""
    results = {
        part.tool_call_id: tool_result_summary(part)
        for message in history
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart | RetryPromptPart) and part.tool_name is not None
    }

    entries: list[TranscriptEntry] = []
    for message in history:
        if isinstance(message, ModelRequest):
            for part in message.parts:
                text = visible_prompt_text(part.content) if isinstance(part, UserPromptPart) else None
                if text:
                    entries.append(TranscriptMessage(kind=MessageKind.USER, body=text))
        elif isinstance(message, ModelResponse):
            for part in message.parts:
                if isinstance(part, TextPart) and part.content.strip():
                    entries.append(TranscriptMessage(kind=MessageKind.AGENT, body=part.content))
                elif isinstance(part, ToolCallPart):
                    result, outcome = results.get(part.tool_call_id, (None, "interrupted"))
                    entries.append(
                        TranscriptToolCall(
                            tool_name=part.tool_name,
                            arguments=part.args_as_json_str(),
                            result=result,
                            outcome=outcome,
                        )
                    )
    return entries
