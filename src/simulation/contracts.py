from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, Field


JsonScalar: TypeAlias = str | int | float | bool | None
JsonObject: TypeAlias = dict[str, JsonScalar | list[JsonScalar] | dict[str, JsonScalar]]
JsonValue: TypeAlias = JsonScalar | list[JsonScalar] | list[JsonObject] | JsonObject


class DiceRequest(BaseModel):
    expression: str = Field(..., min_length=3)
    reason: str = Field(default="", max_length=400)
    character_id: str | None = None
    check_type: str | None = None


class SceneMove(BaseModel):
    move_id: str
    actor_id: str
    action_type: Literal["action", "reaction"] = "action"
    target: str = Field(..., min_length=1, max_length=120)
    description: str = Field(..., min_length=1, max_length=800)
    source: Literal["user", "character"] = "character"


class CharacterActionOutput(BaseModel):
    action_type: Literal["action", "reaction"] = "action"
    target: str = Field(..., min_length=1, max_length=120)
    description: str = Field(..., min_length=1, max_length=800)
    intent_tags: list[str] = Field(default_factory=list)


class MoveAdjudication(BaseModel):
    move_id: str
    actor_id: str
    requires_skill_check: bool = False
    skill: str | None = None
    difficulty_class: int | None = Field(default=None, ge=1, le=40)
    auto_outcome: Literal["success", "failure"] | None = None
    reasoning: str = Field(default="", max_length=1000)


class GmResolutionOutput(BaseModel):
    adjudications: list[MoveAdjudication] = Field(default_factory=list)


class MoveOutcome(BaseModel):
    move_id: str
    actor_id: str
    action_type: Literal["action", "reaction"]
    target: str
    description: str
    requires_skill_check: bool = False
    skill: str | None = None
    difficulty_class: int | None = None
    roll_expression: str | None = None
    rolls: list[int] = Field(default_factory=list)
    modifier: int | None = None
    total: int | None = None
    success: bool = True
    reasoning: str = ""

    def to_summary(self) -> str:
        mode = "roll" if self.requires_skill_check else "auto"
        check = f"{self.skill} vs {self.difficulty_class}" if self.skill and self.difficulty_class else "n/a"
        verdict = "success" if self.success else "failure"
        return f"[{mode}] {self.actor_id}: {self.description} ({check}) => {verdict}"


class ObservationInput(BaseModel):
    character_id: str
    content: str = Field(..., min_length=1, max_length=800)
    importance: int = Field(..., ge=1, le=5)


class StateOp(BaseModel):
    op: Literal["set", "increment", "decrement", "append_unique", "remove_value"]
    path: str = Field(..., min_length=1)
    value: JsonValue = None


class RulesetResolutionOutput(BaseModel):
    dice_request: list[DiceRequest] = Field(default_factory=list)
    result: Literal["success", "failure", "critical_failure"]
    outcome: str = Field(..., min_length=1, max_length=2000)
    new_observations: list[ObservationInput] = Field(default_factory=list)
    state_ops: list[StateOp] = Field(default_factory=list)

    def to_resolved_outcome(self) -> str:
        return f"{self.result.upper()}: {self.outcome}"

class CharacterReflectionOutput(BaseModel):
    action_text: str = Field(..., min_length=1, max_length=1200)
    intent_tags: list[str] = Field(default_factory=list)


class NarratorOutput(BaseModel):
    narration_text: str = Field(..., min_length=1, max_length=3000)
    new_observations: list[ObservationInput] = Field(default_factory=list)
    state_ops: list[StateOp] = Field(default_factory=list)


class SuggestedActionsOutput(BaseModel):
    suggested_actions: list[str] = Field(default_factory=list)


class CharacterRuntime(BaseModel):
    character_id: str
    role: Literal["npc", "user_persona"]
    stat_block: dict[str, Any]


class RuntimeSession(BaseModel):
    id: str
    ruleset_id: str
    world_lore_id: str
    current_scene_id: str
    current_turn_index: int
    small_model_key: str
    large_model_key: str
    user_id: str
    created_at: datetime
    updated_at: datetime


class RuntimeRuleset(BaseModel):
    id: str
    name: str
    rulebook_text: str
    character_stat_schema: dict[str, Any]
    scene_state_schema: dict[str, Any]
    mechanics_guidance: dict[str, Any] | None = None


class RuntimeWorldLore(BaseModel):
    id: str
    name: str
    lore_text: str
    lore_json: dict[str, Any] | None = None


class RuntimeScene(BaseModel):
    id: str
    session_id: str
    scene_index: int
    state_json: dict[str, Any]
    created_at: datetime


class RuntimeObservation(BaseModel):
    id: str
    session_id: str
    scene_id: str
    character_id: str
    content: str
    importance: int
    reinforcement_count: int = 0
    created_at: datetime


class StartSimulationSessionInput(BaseModel):
    session_id: str
    scenario_id: str | None = None
    ruleset_id: str = "everyday-tension"
    world_lore_id: str = "default-world"
    character_ids: list[str]
    npc_ids: list[str]
    stat_blocks: dict[str, dict[str, Any]]
    scene_seed: dict[str, Any]
    intro_seed: str
    user_id: str = "anonymous"
    small_model_key: str = "deepseek-v32"
    large_model_key: str = "claude-sonnet"


class TurnResult(BaseModel):
    narration_text: str
    session_id: str
    turn_index: int
    scene_id: str
    suggested_actions: list[str] = Field(default_factory=list)
    meta_text: str | None = None
