"""Conversion of persisted model messages into conversation entries."""

from collections.abc import Sequence

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
from storyline.room.protocol import Entry, MessageEntry, ToolCallEntry


def tool_result_summary(part: ToolReturnPart | RetryPromptPart) -> tuple[str, str]:
    """Return the displayable result text and outcome of a tool result."""
    if isinstance(part, ToolReturnPart):
        return str(part.content), part.outcome
    return part.model_response(), "retry"


def transcript_entries(history: Sequence[ModelMessage]) -> list[Entry]:
    """Return the user prompts, writer replies and tool calls of a conversation in order."""
    results = {
        part.tool_call_id: tool_result_summary(part)
        for message in history
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart | RetryPromptPart) and part.tool_name is not None
    }

    entries: list[Entry] = []
    for message in history:
        if isinstance(message, ModelRequest):
            for part in message.parts:
                text = visible_prompt_text(part.content) if isinstance(part, UserPromptPart) else None
                if text:
                    entries.append(MessageEntry(role="user", text=text))
        elif isinstance(message, ModelResponse):
            for part in message.parts:
                if isinstance(part, TextPart) and part.content.strip():
                    entries.append(MessageEntry(role="writer", text=part.content))
                elif isinstance(part, ToolCallPart):
                    result, outcome = results.get(part.tool_call_id, (None, "interrupted"))
                    entries.append(
                        ToolCallEntry(
                            tool_call_id=part.tool_call_id,
                            tool_name=part.tool_name,
                            arguments=part.args_as_json_str(),
                            result=result,
                            outcome=outcome,
                        )
                    )
    return entries
