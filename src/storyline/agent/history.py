"""Keeping a saved conversation actionable.

A run can stop between a model asking for a tool and the tool's result arriving: the user interrupts, a tool raises,
the process dies. A history saved at that moment holds a tool call without its result, and every provider rejects
such a conversation on the next turn. Calls without results, and results whose call is gone, are dropped instead;
the story files already show whatever those tools changed.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from pydantic_ai.messages import (
    BaseToolCallPart,
    ModelMessage,
    ModelRequest,
    ModelRequestPart,
    ModelResponse,
    ModelResponsePart,
    NativeToolCallPart,
    NativeToolReturnPart,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from storyline.agent.story_context import SNAPSHOT_OPEN, visible_prompt_text


def actionable_history(messages: Sequence[ModelMessage]) -> list[ModelMessage]:
    """Return the conversation without unanswered tool calls or orphaned results, so the next turn can run on it."""
    answered = {part.tool_call_id for message in messages if isinstance(message, ModelRequest) for part in message.parts if _is_function_result(part)}
    kept_calls: set[str] = set()
    repaired: list[ModelMessage] = []
    for message in messages:
        if isinstance(message, ModelResponse):
            native_results = {part.tool_call_id for part in message.parts if isinstance(part, NativeToolReturnPart)}
            parts = [part for part in message.parts if _keep_response_part(part, answered, native_results)]
            kept_calls.update(part.tool_call_id for part in parts if isinstance(part, ToolCallPart))
            if parts:
                repaired.append(message if len(parts) == len(message.parts) else _with_parts(message, parts))
        else:
            request_parts = [part for part in message.parts if not _is_function_result(part) or part.tool_call_id in kept_calls]
            if request_parts:
                repaired.append(message if len(request_parts) == len(message.parts) else _with_parts(message, request_parts))
    return repaired


@dataclass(frozen=True)
class RemovedTurn:
    """The conversation without its last turn, and what the user wrote in that turn."""

    history: list[ModelMessage]
    prompt: str


def without_last_turn(messages: Sequence[ModelMessage]) -> RemovedTurn | None:
    """Remove the last turn: the user's message that started it and everything after, including messages sent mid-turn.

    A turn starts with the message carrying the story snapshot; histories from before snapshots fall back to the last
    message the user typed. Returns None when there is no turn to remove.
    """
    starts = [index for index, message in enumerate(messages) if _starts_turn(message)]
    if not starts:
        starts = [index for index, message in enumerate(messages) if _user_texts(message)]
    if not starts:
        return None
    start = starts[-1]
    prompt = "\n\n".join(text for message in messages[start:] for text in _user_texts(message))
    return RemovedTurn(history=list(messages[:start]), prompt=prompt)


def _starts_turn(message: ModelMessage) -> bool:
    return isinstance(message, ModelRequest) and any(
        isinstance(part, UserPromptPart) and not isinstance(part.content, str) and any(isinstance(item, str) and item.startswith(SNAPSHOT_OPEN) for item in part.content) for part in message.parts
    )


def _user_texts(message: ModelMessage) -> list[str]:
    if not isinstance(message, ModelRequest):
        return []
    texts = (visible_prompt_text(part.content) for part in message.parts if isinstance(part, UserPromptPart))
    return [text for text in texts if text]


def _keep_response_part(part: ModelResponsePart, answered: set[str], native_results: set[str]) -> bool:
    if isinstance(part, NativeToolCallPart):
        return part.tool_call_id in native_results
    if isinstance(part, BaseToolCallPart):
        return part.tool_call_id in answered
    return True


def _is_function_result(part: ModelRequestPart) -> bool:
    """Tool results and tool retries; a retry without a tool name answers the final output and has no call."""
    return isinstance(part, ToolReturnPart) or (isinstance(part, RetryPromptPart) and part.tool_name is not None)


def _with_parts[M: (ModelRequest, ModelResponse)](message: M, parts: Sequence[ModelRequestPart] | Sequence[ModelResponsePart]) -> M:
    return replace(message, parts=list(parts))
