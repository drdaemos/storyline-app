"""Domain models for the interactive NPC simulation system."""

from typing import Literal

from pydantic import BaseModel, Field

# --- Ruleset Schema Definitions ---


class DriveSchema(BaseModel):
    """Schema for a single drive in a ruleset."""

    name: str = Field(..., description="Drive name, e.g. 'satiation', 'energy'")
    range_min: int = Field(default=0, description="Minimum value")
    range_max: int = Field(default=10, description="Maximum value")
    default: int = Field(default=5, description="Starting value")
    decay_rate: float = Field(default=0.5, description="Subtracted each turn (always positive)")
    offscreen_baseline: int | None = Field(
        default=None,
        description="Value restored to on re-entry after offscreen. None = frozen offscreen.",
    )


class SkillSchema(BaseModel):
    """Schema for a single skill in a ruleset."""

    name: str = Field(..., description="Skill name, e.g. 'persuasion', 'stealth'")
    range_min: int = Field(default=0, description="Minimum value")
    range_max: int = Field(default=20, description="Maximum value")


class EmotionalDimSchema(BaseModel):
    """Schema for one emotional dimension (global or per-relationship)."""

    name: str = Field(..., description="Dimension name, e.g. 'composure', 'trust'")
    range_min: int = Field(default=0, description="Minimum value")
    range_max: int = Field(default=10, description="Maximum value")
    default: int = Field(default=5, description="Starting value")
    offscreen_baseline: int | None = Field(
        default=None,
        description="Value restored to on re-entry. None = persists offscreen.",
    )


class EmotionalStateSchema(BaseModel):
    """Schema for emotional state dimensions."""

    global_dims: list[EmotionalDimSchema] = Field(default_factory=list, description="Global mood dimensions")
    per_relationship: list[EmotionalDimSchema] = Field(default_factory=list, description="Per-relationship sentiment dimensions")


class RulesetStateSchemas(BaseModel):
    """All state schemas for a ruleset."""

    drives: list[DriveSchema] = Field(default_factory=list)
    skills: list[SkillSchema] = Field(default_factory=list)
    emotional_state: EmotionalStateSchema = Field(default_factory=EmotionalStateSchema)


class RulesetConfig(BaseModel):
    """Configuration for a ruleset."""

    time_per_turn: str = Field(default="1 minute", description="How much time passes per turn")
    importance_threshold: int = Field(default=2, description="Minimum importance for observations to be stored")
    max_event_stream_length: int = Field(default=100, description="Max events per character stream")
    narration_history_size: int = Field(default=5, description="Number of recent narrations to keep for context")
    observation_decay_rate: float = Field(default=0.3, description="Default decay rate for observations")
    reflection_decay_rate: float = Field(default=0.1, description="Default decay rate for reflections")
    observation_initial_decay: float = Field(default=10.0, description="Starting decay for observations")
    reflection_initial_decay: float = Field(default=20.0, description="Starting decay for reflections")


class Ruleset(BaseModel):
    """A ruleset defining the mechanical layer of a simulation."""

    id: str = Field(default="", description="Ruleset ID")
    name: str = Field(..., min_length=1, description="Ruleset name")
    rules_text: str = Field(default="", description="Freeform genre/tone/mechanics description")
    state_schemas: RulesetStateSchemas = Field(default_factory=RulesetStateSchemas)
    config: RulesetConfig = Field(default_factory=RulesetConfig)
    user_id: str = Field(default="anonymous")


# --- World Lore ---


class WorldLore(BaseModel):
    """A single world lore entry (location, faction, history, etc.)."""

    id: str = Field(default="", description="Lore entry ID")
    name: str = Field(..., min_length=1, description="Short title")
    content: str = Field(default="", description="Freeform description")
    tags: list[str] = Field(default_factory=list, description="Freeform tags for organization and filtering")
    user_id: str = Field(default="anonymous")


# --- World State ---


class WorldState(BaseModel):
    """Current world state for a session."""

    location: str = Field(default="", description="Current location name")
    time: str = Field(default="", description="Current in-story time")
    characters_present: list[str] = Field(default_factory=list, description="Character IDs present at location")


# --- Intent System ---


class SuccessCondition(BaseModel):
    """How to determine if an intent's goal is met."""

    type: Literal["drive_threshold", "narrative"] = Field(..., description="Condition type")
    drive: str | None = Field(default=None, description="Drive name (if drive_threshold)")
    operator: str | None = Field(default=None, description="Comparison operator (if drive_threshold)")
    threshold: float | None = Field(default=None, description="Threshold value (if drive_threshold)")
    description: str | None = Field(default=None, description="How to know it's done (if narrative)")


class Intent(BaseModel):
    """A character's current goal."""

    goal: str = Field(..., description="What they want to achieve")
    success_condition: SuccessCondition = Field(..., description="How to determine completion")
    source_refs: list[str] = Field(default_factory=list, description="Event IDs or drive names that motivated this")


# --- Character State ---


class EmotionalStateData(BaseModel):
    """Runtime emotional state for a character."""

    global_state: dict[str, float] = Field(default_factory=dict, description="Global mood: {dim_name: value}")
    per_relationship: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Per-relationship: {target_name: {dim_name: value}}",
    )


class CharacterStateData(BaseModel):
    """Per-character per-session runtime state."""

    drives: dict[str, float] = Field(default_factory=dict, description="{drive_name: current_value}")
    skills: dict[str, float] = Field(default_factory=dict, description="{skill_name: current_value}")
    emotional_state: EmotionalStateData = Field(default_factory=EmotionalStateData)
    active_intent: Intent | None = Field(default=None, description="Current goal (NPC only)")
    is_present: bool = Field(default=True, description="Whether at user's current location")
    intended_destination: str | None = Field(default=None, description="Where heading if offscreen")
    last_departure_tick: int | None = Field(default=None, description="Turn when character left")


# --- Event Stream ---


class Observation(BaseModel):
    """An extracted observation from narration."""

    subject: str = Field(..., description="Character or entity this concerns")
    content: str = Field(..., description="Third-person factual description")
    importance: int = Field(..., ge=1, le=5, description="Importance 1-5")
    visibility: Literal["public", "actor_only"] = Field(default="public")
    actor: str | None = Field(default=None, description="Actor for actor_only visibility")


class ReflectionResult(BaseModel):
    """A character's first-person reflection."""

    subject: list[str] = Field(..., description="Character(s) or entity this is about")
    content: str = Field(..., description="First-person thought")
    importance: int = Field(..., ge=2, le=5, description="Importance 2-5")
    source_observation_ids: list[str] = Field(default_factory=list, description="IDs of source observations")


class EventData(BaseModel):
    """A single event in a character's event stream."""

    id: str = Field(default="", description="Event ID (e.g. obs-50, ref-10)")
    session_id: str = Field(default="")
    character_id: str = Field(default="", description="Which NPC's stream")
    type: Literal["observation", "reflection"] = Field(...)
    tick: int = Field(default=0, description="Turn number when created")
    subject: list[str] = Field(default_factory=list, description="Character/entity names")
    content: str = Field(default="", description="Natural language description")
    importance: int = Field(default=2, ge=1, le=5)
    decay_rate: float = Field(default=0.3)
    initial_decay: float = Field(default=10.0)
    source_refs: list[str] = Field(default_factory=list, description="Event IDs this derives from")
    visibility: Literal["public", "actor_only"] | None = Field(default=None, description="Observations only")


# --- Pipeline Step Models ---


class InputClassification(BaseModel):
    """Result of classifying user freeform input."""

    type: Literal["action", "relocation", "time_skip"] = Field(...)
    parsed_target: str | None = Field(default=None)
    action_text: str | None = Field(default=None)


class CharacterAction(BaseModel):
    """A character's action for this turn."""

    type: Literal["action", "dialogue", "reaction"] = Field(...)
    target: str | None = Field(default=None, description="Target character or None")
    description: str = Field(..., description="What they do or say")


class ActionWithReasoning(BaseModel):
    """Action generation output with reasoning."""

    reasoning: str = Field(default="", description="Why this action right now")
    action: CharacterAction = Field(...)


class DriveEffect(BaseModel):
    """A drive change caused by an action."""

    drive: str = Field(..., description="Drive name")
    change: float = Field(..., description="Change amount")


class GMActionEvaluation(BaseModel):
    """GM evaluation for a single action."""

    character: str = Field(..., description="Character name")
    action_summary: str = Field(default="", description="Brief restatement")
    reasoning: str = Field(default="", description="Why check/no check")
    check_required: bool = Field(default=False)
    skill: str | None = Field(default=None)
    dc: int | None = Field(default=None)
    contested_with: str | None = Field(default=None)
    drive_effects: list[DriveEffect] = Field(default_factory=list)
    departure: bool = Field(default=False)


class GMEvaluationResult(BaseModel):
    """Full GM evaluation output."""

    evaluations: list[GMActionEvaluation] = Field(default_factory=list)


class ActionOutcome(BaseModel):
    """Result of dice resolution for an action."""

    character: str = Field(...)
    action_summary: str = Field(default="")
    result: Literal["success", "failure"] = Field(...)
    roll_details: str | None = Field(default=None, description="e.g. '14 vs DC 13'")
    gm_evaluation: GMActionEvaluation | None = Field(default=None, description="Original GM evaluation")


class StateDiff(BaseModel):
    """A proposed state change from character processing."""

    stat: str = Field(..., description="Stat name")
    target: str | None = Field(default=None, description="Target character (per-relationship) or None (global)")
    change: float = Field(..., description="Change amount")
    reasoning: str = Field(default="", description="What caused this")


class CharacterProcessingResult(BaseModel):
    """Output of character processing step (6.7)."""

    state_diffs: list[StateDiff] = Field(default_factory=list)
    reflection: ReflectionResult | None = Field(default=None)


class ContinuationOption(BaseModel):
    """A suggested next action for the user."""

    type: Literal["action", "dialogue", "relocation", "time_skip"] = Field(...)
    description: str = Field(..., description="Short phrase describing the action")
    target: str | None = Field(default=None, description="Character, location, or time")


class ContinuationOptionsResult(BaseModel):
    """Output of continuation options step (6.9)."""

    options: list[ContinuationOption] = Field(default_factory=list)


class IntentReevaluation(BaseModel):
    """Output of intent reevaluation (6.8a)."""

    reasoning: str = Field(default="")
    keep: bool = Field(default=True)


class IntentCompletionCheck(BaseModel):
    """Output of intent completion check (6.8c)."""

    reasoning: str = Field(default="")
    complete: bool = Field(default=False)


class ObservationExtractionResult(BaseModel):
    """Output of observation extraction step (6.6)."""

    observations: list[Observation] = Field(default_factory=list)


# --- Turn & Session ---


class TurnRequest(BaseModel):
    """Request to execute a turn."""

    session_id: str = Field(...)
    input_type: Literal["action", "relocation", "time_skip"] = Field(default="action")
    content: str = Field(..., description="User's input text")
    option_index: int | None = Field(default=None, description="Selected continuation option index")
    processor_type: str = Field(default="google", description="Large model processor type")
    mini_processor_type: str | None = Field(default=None, description="Mini model processor type")
    backup_processor_type: str | None = Field(default=None)


class TurnSnapshot(BaseModel):
    """Complete serializable state at a turn boundary."""

    world_state: WorldState = Field(default_factory=WorldState)
    character_states: dict[str, CharacterStateData] = Field(default_factory=dict, description="{char_id: state}")
    turn_counter: int = Field(default=0)
    narration_history: list[str] = Field(default_factory=list, description="Last K narrations")
    location_history: list[dict] = Field(default_factory=list)


class OffscreenSummaryResult(BaseModel):
    """Output of offscreen summary for NPC entry."""

    offscreen_observations: list[dict] = Field(default_factory=list)
    arrival_observations: list[Observation] = Field(default_factory=list)
    state_diffs: list[dict] = Field(default_factory=list)


class TimeSkipSummaryResult(BaseModel):
    """Output of time skip summary."""

    summary: str = Field(default="")
    npc_observations: list[dict] = Field(default_factory=list)
