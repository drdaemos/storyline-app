"""Pydantic models for the VN script format.

Mirrors specs/vn_script_schema_draft.md. These models enforce shape only
(field types, routing-block exclusivity, in-domain initials); referential
integrity across ids is the structural validator's job (src/vn/validator.py).
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VNModel(BaseModel):
    """Base for all script models: unknown fields are schema errors."""

    model_config = ConfigDict(extra="forbid")


# --- State variables -------------------------------------------------------


class FlagVar(VNModel):
    name: str = Field(..., min_length=1)
    type: Literal["flag"] = "flag"
    initial: bool = False


class CounterVar(VNModel):
    name: str = Field(..., min_length=1)
    type: Literal["counter"] = "counter"
    max: int = Field(..., ge=1)
    initial: int = 0

    @model_validator(mode="after")
    def initial_in_domain(self) -> "CounterVar":
        if not (0 <= self.initial <= self.max):
            raise ValueError(f"counter '{self.name}': initial {self.initial} outside domain 0..{self.max}")
        return self


class EnumVar(VNModel):
    name: str = Field(..., min_length=1)
    type: Literal["enum"] = "enum"
    values: list[str] = Field(..., min_length=1)
    initial: str

    @model_validator(mode="after")
    def initial_in_domain(self) -> "EnumVar":
        if len(set(self.values)) != len(self.values):
            raise ValueError(f"enum '{self.name}': duplicate values")
        if self.initial not in self.values:
            raise ValueError(f"enum '{self.name}': initial '{self.initial}' not in values")
        return self


StateVar = Annotated[FlagVar | CounterVar | EnumVar, Field(discriminator="type")]


# --- Conditions, guards, effects -------------------------------------------

VarOp = Literal["==", ">=", "<="]
StateValue = bool | int | str


class VarCondition(VNModel):
    var: str = Field(..., min_length=1)
    op: VarOp
    value: StateValue


class VisitedCondition(VNModel):
    visited: str = Field(..., min_length=1, description="Scene or beat id")
    value: bool = True


Condition = VarCondition | VisitedCondition

# AND semantics; empty list = always true. OR = duplicate edges/options. [D4]
Guard = list[Condition]


class Effect(VNModel):
    var: str = Field(..., min_length=1)
    op: Literal["set", "inc", "dec"]
    value: StateValue


# --- Checks -----------------------------------------------------------------


class VarCheckModifier(VarCondition):
    mod: int


class VisitedCheckModifier(VisitedCondition):
    mod: int


CheckModifier = VarCheckModifier | VisitedCheckModifier


class CheckSpec(VNModel):
    difficulty: int
    modifiers: list[CheckModifier] = Field(default_factory=list)
    on_success: str = Field(..., min_length=1)
    on_failure: str = Field(..., min_length=1)


# --- Beats ------------------------------------------------------------------


class Extension(VNModel):
    """Presence on a beat marks an extension point (micro-loop). [D3]"""

    deeper_domain: str = ""


class ExitEdge(VNModel):
    target_scene: str = Field(..., min_length=1)
    guard: Guard = Field(default_factory=list)
    priority: int = 1


class ChoiceOption(VNModel):
    intent: str = Field(..., min_length=1)
    guard: Guard = Field(default_factory=list)
    target: str = Field(..., min_length=1)


class BeatBase(VNModel):
    id: str = Field(..., min_length=1)
    intent: str = Field(..., min_length=1)
    effects: list[Effect] = Field(default_factory=list)
    extension: Extension | None = None


class PlainBeat(BeatBase):
    type: Literal["plain"] = "plain"
    next: str | None = None
    exit_edges: list[ExitEdge] | None = None
    exit: Literal["open"] | None = None

    @model_validator(mode="after")
    def exactly_one_routing(self) -> "PlainBeat":
        routes = [self.next is not None, self.exit_edges is not None, self.exit is not None]
        if sum(routes) != 1:
            raise ValueError(f"plain beat '{self.id}': exactly one of next / exit_edges / exit required")
        if self.exit_edges is not None and len(self.exit_edges) == 0:
            raise ValueError(f"plain beat '{self.id}': exit_edges must not be empty")
        return self


class CheckBeat(BeatBase):
    type: Literal["check"] = "check"
    check: CheckSpec


class ChoiceBeat(BeatBase):
    type: Literal["choice"] = "choice"
    options: list[ChoiceOption] = Field(..., min_length=1)


class EndingBeat(BeatBase):
    type: Literal["ending"] = "ending"
    ending_id: str = Field(..., min_length=1)


Beat = Annotated[PlainBeat | CheckBeat | ChoiceBeat | EndingBeat, Field(discriminator="type")]


# --- Scenes and script ------------------------------------------------------


class Scene(VNModel):
    id: str = Field(..., min_length=1)
    intent: str = Field(..., min_length=1)
    prerequisites: Guard = Field(default_factory=list)
    repeatable: bool = False
    forced: int | None = None
    entry_beat: str = Field(..., min_length=1)
    beats: list[Beat] = Field(..., min_length=1)


class Meta(VNModel):
    title: str = Field(..., min_length=1)
    protagonist: str = Field(..., min_length=1)


class Script(VNModel):
    meta: Meta
    state_vars: list[StateVar] = Field(default_factory=list)
    start_scene: str = Field(..., min_length=1)
    scenes: list[Scene] = Field(..., min_length=1)
