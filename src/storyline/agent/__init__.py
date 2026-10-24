"""Writing agent package."""

from storyline.agent.assembly import RunAssembly, assemble
from storyline.agent.history import RemovedTurn, actionable_history, without_last_turn
from storyline.agent.models import ModelNameError, resolve_model, validate_model_name
from storyline.agent.sealing import tool_call_is_sealed
from storyline.agent.story_context import story_snapshot, turn_prompt, visible_prompt_text
from storyline.agent.writer import DEFAULT_MODEL_NAME, WRITER_INSTRUCTIONS, create_writer_agent, prompt_version, writer_prompt_version
from storyline.agent.writing_session import ArchivedHistory, PromptDelivered, RunSetup, TurnEvent, TurnOutcome, WritingSession, WritingTurn

__all__ = (
    "ArchivedHistory",
    "DEFAULT_MODEL_NAME",
    "ModelNameError",
    "RunAssembly",
    "RunSetup",
    "WRITER_INSTRUCTIONS",
    "PromptDelivered",
    "TurnEvent",
    "TurnOutcome",
    "WritingSession",
    "WritingTurn",
    "RemovedTurn",
    "actionable_history",
    "assemble",
    "without_last_turn",
    "create_writer_agent",
    "prompt_version",
    "resolve_model",
    "story_snapshot",
    "tool_call_is_sealed",
    "turn_prompt",
    "validate_model_name",
    "writer_prompt_version",
    "visible_prompt_text",
)
