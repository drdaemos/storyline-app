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


class Condition(VNModel):
    """A guard term, either a state-variable comparison (`var`/`op`) or a visitedness
    test (`visited`). Exactly one of the two forms is populated.

    This is a single object rather than a `VarCondition | VisitedCondition` union on
    purpose: guards are arrays, and a per-element object union forces Anthropic's
    structured-output grammar to keep both branches open at every position, which
    compiled past the API's grammar-size limit ("compiled grammar is too large").
    Folding both forms into one object removes that branch point. Scripts persisted
    before this fold used the same field names with no extra tag, so they validate
    unchanged. Use `is_var` / `is_visited` to discriminate."""

    var: str | None = Field(default=None, min_length=1)
    op: VarOp | None = None
    visited: str | None = Field(default=None, min_length=1, description="Scene or beat id")
    value: StateValue = True

    @model_validator(mode="after")
    def _exactly_one_form(self) -> "Condition":
        if (self.var is None) == (self.visited is None):
            raise ValueError("condition must set exactly one of 'var' or 'visited'")
        if self.var is not None and self.op is None:
            raise ValueError(f"var condition on '{self.var}' requires an 'op'")
        if self.visited is not None and self.op is not None:
            raise ValueError(f"visited condition on '{self.visited}' must not set 'op'")
        return self

    @property
    def is_var(self) -> bool:
        return self.var is not None

    @property
    def is_visited(self) -> bool:
        return self.visited is not None


# AND semantics; empty list = always true. OR = duplicate edges/options. [D4]
Guard = list[Condition]


class Effect(VNModel):
    var: str = Field(..., min_length=1)
    op: Literal["set", "inc", "dec"]
    value: StateValue


# --- Checks -----------------------------------------------------------------


class CheckModifier(Condition):
    """A `Condition` that also contributes `mod` to a check's difficulty when it holds.
    Same single-object rationale as `Condition` (see above)."""

    mod: int


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


# --- Draft scene graph (Stage B request shape) ------------------------------
#
# The scene-graph stage drafts structure only; the mechanics stage adds guards,
# effects, check modifiers, and scene prerequisites afterward (see
# src/vn/pipeline/mechanics.py). Requesting the full `Scene` here forces
# Anthropic's structured-output grammar to keep the union-heavy Condition /
# Effect / CheckModifier branches open at every nested array position, which
# compiles past the API's grammar-size limit ("compiled grammar is too large").
# These slim draft models drop every mechanic field the draft never fills, then
# `draft_scene_to_scene` lifts them into canonical `Scene`s with empty mechanics
# for the mechanics stage to patch.


class DraftExitEdge(VNModel):
    target_scene: str = Field(..., min_length=1, description="Id of the outline scene this exit leads to")
    priority: int = Field(default=1, description="Tie-break order when several exits are eligible; lower fires first")


class DraftChoiceOption(VNModel):
    intent: str = Field(..., min_length=1, description="What the player is choosing to do, phrased as the option's intent")
    target: str = Field(..., min_length=1, description="Id of the beat this option routes to; sibling options should target distinct beats and may reconverge later")


class DraftCheckSpec(VNModel):
    difficulty: int = Field(..., description="Target number for the check, typically 10-14")
    on_success: str = Field(..., min_length=1, description="Id of the beat reached when the check succeeds; must differ from on_failure")
    on_failure: str = Field(..., min_length=1, description="Id of the beat reached when the check fails; must differ from on_success")


class DraftBeatBase(VNModel):
    id: str = Field(..., min_length=1, description="Globally unique snake_case beat id, prefixed b_ and usually including the scene stem")
    intent: str = Field(..., min_length=1, description="What this beat accomplishes dramatically, one phrase")
    extension: Extension | None = Field(default=None, description="Set on 1-2 high-tension beats to mark an extension point; deeper_domain names what deeper narration may cover")


class DraftPlainBeat(DraftBeatBase):
    type: Literal["plain"] = "plain"
    next: str | None = Field(default=None, description="Id of the next beat for linear flow; set exactly one of next / exit_edges / exit")
    exit_edges: list[DraftExitEdge] | None = Field(default=None, description="Directed exits to other outline scenes; set exactly one of next / exit_edges / exit")
    exit: Literal["open"] | None = Field(default=None, description="Set to \"open\" for an open exit back to scene selection; set exactly one of next / exit_edges / exit")

    @model_validator(mode="after")
    def exactly_one_routing(self) -> "DraftPlainBeat":
        # Mirror PlainBeat's contract so a malformed draft surfaces during the
        # structured-output parse (caught by request_model → repair loop) rather
        # than later in draft_scene_to_scene where it would escape as a hard error.
        routes = [self.next is not None, self.exit_edges is not None, self.exit is not None]
        if sum(routes) != 1:
            raise ValueError(f"plain beat '{self.id}': exactly one of next / exit_edges / exit required")
        if self.exit_edges is not None and len(self.exit_edges) == 0:
            raise ValueError(f"plain beat '{self.id}': exit_edges must not be empty")
        return self


class DraftCheckBeat(DraftBeatBase):
    type: Literal["check"] = "check"
    check: DraftCheckSpec = Field(..., description="The skill check and its success/failure routing")


class DraftChoiceBeat(DraftBeatBase):
    type: Literal["choice"] = "choice"
    options: list[DraftChoiceOption] = Field(..., min_length=1, description="Player choices; may reroute and reconverge within the scene")


class DraftEndingBeat(DraftBeatBase):
    type: Literal["ending"] = "ending"
    ending_id: str = Field(..., min_length=1, description="Id of the ending this beat realizes, matching an outlined ending id")


DraftBeat = Annotated[DraftPlainBeat | DraftCheckBeat | DraftChoiceBeat | DraftEndingBeat, Field(discriminator="type")]


class DraftScene(VNModel):
    """Structure-only draft of a scene. Mechanics (guards, effects, check modifiers,
    prerequisites) are intentionally absent — a later pass adds them."""

    id: str = Field(..., min_length=1, description="Scene id, matching the outlined scene id")
    intent: str = Field(..., min_length=1, description="What this scene accomplishes in the arc, one phrase")
    entry_beat: str = Field(..., min_length=1, description="Id of the beat the scene starts on")
    beats: list[DraftBeat] = Field(..., min_length=1, description="Beats forming the scene's mini-graph; each beat needs a clear structural job")


class LLMChoiceOption(VNModel):
    """Request-only choice option for Anthropic-compatible structured output."""

    intent: str = Field(..., min_length=1, description="What the player is choosing to do, phrased as the option's intent")
    target: str = Field(..., min_length=1, description="Id of the beat this option routes to; sibling options must target distinct beats")


class LLMBeat(VNModel):
    """Request-only beat shape with no object unions or nullable routing fields.

    The scene graph stage converts this into `DraftBeat`, then into the canonical
    `Beat` union. Invariants that would be expensive in the provider grammar are
    enforced by that conversion and the existing validators.
    """

    id: str = Field(..., min_length=1, description="Globally unique snake_case beat id, prefixed b_ and usually including the scene stem")
    type: Literal["plain", "check", "choice", "ending"] = Field(..., description="Beat kind")
    intent: str = Field(..., min_length=1, description="What this beat accomplishes dramatically, one phrase")
    extension_domain: str = Field(..., description="Empty string, or what deeper narration may cover on this beat")
    route: str = Field(
        ...,
        description="For plain beats only: next:<beat_id>, exit:open, or edges:<scene_id>@<priority>|<scene_id>@<priority>. Empty string for other beat types.",
    )
    check_difficulty: int = Field(..., description="For check beats: target number, typically 10-14. Set 0 otherwise")
    check_success: str = Field(..., description="For check beats: success target beat id, different from check_failure. Empty string otherwise")
    check_failure: str = Field(..., description="For check beats: failure target beat id, different from check_success. Empty string otherwise")
    options: list[LLMChoiceOption] = Field(..., description="For choice beats only; empty list otherwise")
    ending_id: str = Field(..., description="For ending beats only; empty string otherwise")


class LLMScene(VNModel):
    """Anthropic-friendly request model for Stage B.

    It deliberately avoids nested beat unions and nullable routing fields. The
    pipeline converts it to `DraftScene` and then relies on canonical validators.
    """

    id: str = Field(..., min_length=1, description="Scene id, matching the outlined scene id")
    intent: str = Field(..., min_length=1, description="What this scene accomplishes in the arc, one phrase")
    entry_beat: str = Field(..., min_length=1, description="Id of the beat the scene starts on")
    beats: list[LLMBeat] = Field(..., min_length=1, description="Beats forming the scene's mini-graph; beat ids must be globally unique and each beat needs a clear structural job")


def _draft_beat_to_beat(beat: DraftBeat) -> Beat:
    """Lift a draft beat into its canonical `Beat`, with empty mechanics for the
    mechanics stage to patch. Routing and structure carry over unchanged."""
    common = {"id": beat.id, "intent": beat.intent, "extension": beat.extension}
    if isinstance(beat, DraftPlainBeat):
        return PlainBeat(
            **common,
            next=beat.next,
            exit_edges=[ExitEdge(target_scene=edge.target_scene, priority=edge.priority) for edge in beat.exit_edges] if beat.exit_edges is not None else None,
            exit=beat.exit,
        )
    if isinstance(beat, DraftCheckBeat):
        return CheckBeat(**common, check=CheckSpec(difficulty=beat.check.difficulty, on_success=beat.check.on_success, on_failure=beat.check.on_failure))
    if isinstance(beat, DraftChoiceBeat):
        return ChoiceBeat(**common, options=[ChoiceOption(intent=option.intent, target=option.target) for option in beat.options])
    return EndingBeat(**common, ending_id=beat.ending_id)


def draft_scene_to_scene(draft: DraftScene) -> Scene:
    """Convert a structure-only `DraftScene` into a canonical `Scene` with empty
    mechanics, ready for the gate and the mechanics patch."""
    return Scene(id=draft.id, intent=draft.intent, entry_beat=draft.entry_beat, beats=[_draft_beat_to_beat(beat) for beat in draft.beats])


class Meta(VNModel):
    title: str = Field(..., min_length=1)
    protagonist: str = Field(..., min_length=1)


class Script(VNModel):
    meta: Meta
    state_vars: list[StateVar] = Field(default_factory=list)
    start_scene: str = Field(..., min_length=1)
    scenes: list[Scene] = Field(..., min_length=1)
