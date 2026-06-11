"""Intermediate models for the staged generation pipeline (Stage A output + progress events)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.models.vn.script import CheckModifier, Effect, Guard, Scene, StateVar


class VNPipelineModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SceneOutlineItem(VNPipelineModel):
    id: str = Field(..., min_length=1)
    intent: str = Field(..., min_length=1, description="Same semantics as Scene.intent: shown as a choice option at open exits")
    synopsis: str = Field(..., min_length=1, description="Free-form: what happens in this scene, for later stages")
    exit_mode: Literal["open", "directed", "ending"]
    ending_ids: list[str] = Field(default_factory=list, description="Intended ending ids this scene contains (ending scenes only)")


class ScriptOutline(VNPipelineModel):
    """Stage A output: scene-level outline, no beats yet."""

    title: str = Field(..., min_length=1)
    start_scene: str = Field(..., min_length=1)
    scenes: list[SceneOutlineItem] = Field(..., min_length=1)


class BeatEffectsPatch(VNPipelineModel):
    beat_id: str = Field(..., min_length=1)
    effects: list[Effect]


class OptionGuardPatch(VNPipelineModel):
    beat_id: str = Field(..., min_length=1)
    option_index: int = Field(..., ge=0, description="0-based index into the choice beat's options")
    guard: Guard


class ExitEdgeGuardPatch(VNPipelineModel):
    beat_id: str = Field(..., min_length=1)
    edge_index: int = Field(..., ge=0, description="0-based index into the beat's exit_edges")
    guard: Guard


class ScenePatch(VNPipelineModel):
    scene_id: str = Field(..., min_length=1)
    prerequisites: Guard = Field(default_factory=list)
    repeatable: bool | None = None
    forced: int | None = None


class CheckModifiersPatch(VNPipelineModel):
    beat_id: str = Field(..., min_length=1)
    modifiers: list[CheckModifier]


class MechanicsPatch(VNPipelineModel):
    """Stage C output: only the mechanics delta over the drafted scenes.

    The drafted structure (scenes, beats, options, routing) is never re-emitted by the
    LLM — it is patched in code. This keeps the output an order of magnitude smaller
    and makes structural drift impossible.
    """

    state_vars: list[StateVar]
    beat_effects: list[BeatEffectsPatch] = Field(default_factory=list)
    option_guards: list[OptionGuardPatch] = Field(default_factory=list)
    exit_edge_guards: list[ExitEdgeGuardPatch] = Field(default_factory=list)
    scene_patches: list[ScenePatch] = Field(default_factory=list)
    check_modifiers: list[CheckModifiersPatch] = Field(default_factory=list)


class LLMBeatEffectsPatch(VNPipelineModel):
    beat_id: str = Field(..., min_length=1, description="Existing beat id receiving these effects")
    effects: list[str] = Field(..., description='Effect DSL strings, e.g. "trust += 1", "lamp_color = white", "injured = true"')


class LLMOptionGuardPatch(VNPipelineModel):
    beat_id: str = Field(..., min_length=1, description="Existing choice beat id")
    option_index: int = Field(..., ge=0, description="0-based index into the choice beat's options")
    guard: list[str] = Field(..., description='Guard DSL strings with AND semantics, e.g. "trust >= 2", "visited:b_ledger", "not visited:sc_town"')


class LLMExitEdgeGuardPatch(VNPipelineModel):
    beat_id: str = Field(..., min_length=1, description="Existing plain beat id with exit_edges")
    edge_index: int = Field(..., ge=0, description="0-based index into the beat's exit_edges")
    guard: list[str] = Field(..., description='Guard DSL strings with AND semantics, e.g. "alarm == false"')


class LLMScenePatch(VNPipelineModel):
    scene_id: str = Field(..., min_length=1, description="Existing scene id")
    prerequisites: list[str] = Field(..., description='Guard DSL strings controlling open-exit availability, or [] for none')
    repeatable: bool = Field(..., description="Whether this scene may be selected more than once")
    forced: int = Field(..., description="Forced priority, or -1 when this scene is not forced")


class LLMCheckModifiersPatch(VNPipelineModel):
    beat_id: str = Field(..., min_length=1, description="Existing check beat id")
    modifiers: list[str] = Field(..., description='Modifier DSL strings, e.g. "trust >= 2 => +2", "visited:b_alarm => -1"')


class LLMMechanicsPatch(VNPipelineModel):
    """Anthropic-friendly Stage C output.

    The provider sees a flat schema with no unions/nullables. DSL strings are parsed
    into the canonical MechanicsPatch before the full validator and softlock checker
    run.
    """

    state_vars: list[str] = Field(
        ...,
        description='State var DSL strings: "flag name=false", "counter trust max=3 initial=1", or "enum mood values=calm|alert initial=calm"',
    )
    beat_effects: list[LLMBeatEffectsPatch] = Field(..., description="Beat effect patches; use [] when none")
    option_guards: list[LLMOptionGuardPatch] = Field(..., description="Choice option guard patches; use [] when none")
    exit_edge_guards: list[LLMExitEdgeGuardPatch] = Field(..., description="Exit edge guard patches; use [] when none")
    scene_patches: list[LLMScenePatch] = Field(..., description="Scene prerequisite/repeatable/forced patches; use [] when none")
    check_modifiers: list[LLMCheckModifiersPatch] = Field(..., description="Check modifier patches; use [] when none")


class GenerationCheckpoint(VNPipelineModel):
    """Artifacts produced so far by the pipeline; a resumed run skips everything stored here."""

    outline: ScriptOutline | None = None
    scenes: list[Scene] = Field(default_factory=list)


PipelineStage = Literal["outline", "scene_graph", "mechanics"]
PipelineStatus = Literal["started", "passed", "repairing", "failed"]


class PipelineProgress(VNPipelineModel):
    stage: PipelineStage
    status: PipelineStatus
    scene_id: str | None = None
    detail: str = ""
