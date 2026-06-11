"""Runtime models: serializable session state, player actions, engine events, and the player-facing view."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.models.vn.script import StateValue


class VNRuntimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VNAction(VNRuntimeModel):
    type: Literal["proceed", "choose", "go_deeper"]
    option_index: int | None = None


# Beat lifecycle: pre (not yet executed) -> extension (offer pending, if annotated) -> resolve (routing).
BeatPhase = Literal["pre", "extension", "resolve"]


class VNRuntimeState(VNRuntimeModel):
    """Complete, serializable session state. Same actions + same seed always replay to the same state."""

    vars: dict[str, StateValue]
    visited: set[str] = Field(default_factory=set)
    current_beat: str
    phase: BeatPhase = "pre"
    status: Literal["running", "ended"] = "running"
    ending_id: str | None = None
    seed: int = 0
    roll_count: int = 0
    action_log: list[VNAction] = Field(default_factory=list)


# --- Engine events -----------------------------------------------------------


class SceneEntered(VNRuntimeModel):
    type: Literal["scene_entered"] = "scene_entered"
    scene_id: str
    intent: str


class BeatEntered(VNRuntimeModel):
    type: Literal["beat_entered"] = "beat_entered"
    scene_id: str
    beat_id: str
    intent: str


class CheckResolved(VNRuntimeModel):
    type: Literal["check_resolved"] = "check_resolved"
    beat_id: str
    roll: int
    difficulty: int
    modifier_total: int
    success: bool


class ChoiceMade(VNRuntimeModel):
    type: Literal["choice_made"] = "choice_made"
    intent: str


class WentDeeper(VNRuntimeModel):
    type: Literal["went_deeper"] = "went_deeper"
    beat_id: str
    deeper_domain: str


class EndingReached(VNRuntimeModel):
    type: Literal["ending_reached"] = "ending_reached"
    ending_id: str
    intent: str


EngineEvent = Annotated[
    SceneEntered | BeatEntered | CheckResolved | ChoiceMade | WentDeeper | EndingReached,
    Field(discriminator="type"),
]


# --- Player-facing view ------------------------------------------------------


class PendingOption(VNRuntimeModel):
    index: int
    intent: str


class Pending(VNRuntimeModel):
    """What the player is being asked. Beat choices and open-exit scene selection look identical."""

    kind: Literal["choice", "extension"]
    prompt: str
    options: list[PendingOption] = Field(default_factory=list)
    deeper_domain: str = ""


class EngineView(VNRuntimeModel):
    status: Literal["running", "ended"]
    scene_id: str
    beat_id: str
    pending: Pending | None = None
    ending_id: str | None = None
    vars: dict[str, StateValue]
    visited: list[str]
