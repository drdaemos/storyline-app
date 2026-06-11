"""Models for the VN script judge (M9): structured craft assessment of a generated script.

The judge assesses dramatic/interactive craft, not structural validity (the validator
and softlock checker own validity). Two lens reviews (playwright, interactivity director)
are produced by the LLM; the final ScriptEvaluation is assembled in code.

Field order inside LensReview is deliberate: evidence and analysis come before scores,
so an autoregressive judge commits to reasoning before committing to a number.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.models.vn.pipeline import VNPipelineModel


class VNJudgeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


JudgeLens = Literal["playwright", "director"]

PlaywrightDimension = Literal[
    "premise_fidelity",
    "dramatic_structure",
    "scene_craft",
    "character_utilization",
    "tone_consistency",
]

DirectorDimension = Literal[
    "choice_meaningfulness",
    "branch_divergence",
    "consequence_payoff",
    "ending_differentiation",
    "player_agency",
]

DimensionName = PlaywrightDimension | DirectorDimension

PLAYWRIGHT_DIMENSIONS: tuple[PlaywrightDimension, ...] = (
    "premise_fidelity",
    "dramatic_structure",
    "scene_craft",
    "character_utilization",
    "tone_consistency",
)

DIRECTOR_DIMENSIONS: tuple[DirectorDimension, ...] = (
    "choice_meaningfulness",
    "branch_divergence",
    "consequence_payoff",
    "ending_differentiation",
    "player_agency",
)

Severity = Literal["critical", "major", "minor", "polish"]
FixEffort = Literal["small", "moderate", "structural"]
Verdict = Literal["recommend", "consider", "needs_revision"]


class CraftCheck(VNJudgeModel):
    """One binary craft test inside a dimension; evidence cites ids from the script."""

    check: str = Field(..., min_length=1, description="snake_case name of the binary craft test")
    evidence: str = Field(..., min_length=1, description="What in the script (scene/beat ids + intent excerpts) decides this check")
    passed: bool


class DimensionAssessment(VNJudgeModel):
    """Anchored per-dimension verdict. Checks and analysis precede the score on purpose."""

    dimension: DimensionName
    craft_checks: list[CraftCheck] = Field(..., min_length=1)
    analysis: str = Field(..., min_length=1, description="Reasoning over the evidence; written before the score is chosen")
    score: int = Field(..., ge=1, le=5)
    score_rationale: str = Field(..., min_length=1, description="Which anchor of the 1-5 scale this script meets and why")


class JudgeFinding(VNJudgeModel):
    """One prioritized, located problem with a concrete fix direction."""

    severity: Severity
    dimension: DimensionName
    scene_id: str | None = None
    beat_id: str | None = None
    quote: str = Field(..., min_length=1, description="Verbatim intent/synopsis excerpt the finding is about")
    issue: str = Field(..., min_length=1)
    why_it_matters: str = Field(..., min_length=1, description="Impact on the player/dramatic contract")
    suggested_fix: str = Field(..., min_length=1, description="Concrete direction, phrased as an option, not a rewrite")
    fix_effort: FixEffort


class StrengthNote(VNJudgeModel):
    """What works and must survive any revision (prevents fix-induced regressions)."""

    scene_id: str | None = None
    quote: str = Field(..., min_length=1)
    why: str = Field(..., min_length=1)


class LensReview(VNJudgeModel):
    """LLM output for one lens pass (playwright or interactivity director)."""

    dimensions: list[DimensionAssessment] = Field(..., min_length=1)
    findings: list[JudgeFinding] = Field(default_factory=list)
    strengths: list[StrengthNote] = Field(default_factory=list)


class LLMCraftCheck(VNJudgeModel):
    """Request-only craft check without union-bearing dimension types."""

    check: str = Field(..., min_length=1, description="snake_case name of the binary craft test")
    evidence: str = Field(..., min_length=1, description="What in the script decides this check")
    passed: bool


class LLMDimensionAssessment(VNJudgeModel):
    """Request-only assessment; dimension is validated after conversion."""

    dimension: str = Field(..., min_length=1, description="One of the exact requested dimension names")
    craft_checks: list[LLMCraftCheck] = Field(..., min_length=1)
    analysis: str = Field(..., min_length=1, description="Reasoning over the evidence; written before the score is chosen")
    score: int = Field(..., ge=1, le=5)
    score_rationale: str = Field(..., min_length=1, description="Which anchor of the 1-5 scale this script meets and why")


class LLMJudgeFinding(VNJudgeModel):
    """Request-only finding. Empty scene_id/beat_id means omitted."""

    severity: Severity
    dimension: str = Field(..., min_length=1, description="One of the exact requested dimension names")
    scene_id: str = Field(..., description="Existing scene id, or empty string for a global finding")
    beat_id: str = Field(..., description="Existing beat id where applicable, or empty string")
    quote: str = Field(..., min_length=1, description="Verbatim intent/synopsis excerpt")
    issue: str = Field(..., min_length=1)
    why_it_matters: str = Field(..., min_length=1, description="Impact on the player/dramatic contract")
    suggested_fix: str = Field(..., min_length=1, description="Concrete direction, phrased as an option, not a rewrite")
    fix_effort: FixEffort


class LLMStrengthNote(VNJudgeModel):
    """Request-only strength note. Empty scene_id means global."""

    scene_id: str = Field(..., description="Existing scene id, or empty string")
    quote: str = Field(..., min_length=1)
    why: str = Field(..., min_length=1)


class LLMLensReview(VNJudgeModel):
    """Anthropic-friendly request model for one judge lens.

    It avoids nullable citation fields and the `DimensionName` union. The judge
    converts this to `LensReview`, then applies the same gate checks as before.
    """

    dimensions: list[LLMDimensionAssessment] = Field(..., min_length=1)
    findings: list[LLMJudgeFinding] = Field(..., description="Ranked findings; use [] when none")
    strengths: list[LLMStrengthNote] = Field(..., description="Strengths worth preserving; use [] when none")


# --- Deterministic structural digest (computed in code, fed to the judge) -----


class ChoiceBeatDigest(VNPipelineModel):
    scene_id: str
    beat_id: str
    option_count: int
    guarded_option_count: int
    distinct_target_count: int


class StateVarUsage(VNPipelineModel):
    name: str
    type: str
    writes: int = Field(..., description="Effects writing this var")
    reads: int = Field(..., description="Guards/prerequisites/check modifiers reading this var")


class ScriptDigest(VNPipelineModel):
    """Branch/flag summary the judge cannot reliably reconstruct from script text."""

    scene_count: int
    beat_count: int
    plain_beat_count: int
    choice_beat_count: int
    check_beat_count: int
    ending_beat_count: int
    ending_ids: list[str]
    scenes_with_open_exit: list[str]
    forced_scenes: list[str]
    repeatable_scenes: list[str]
    choice_beats: list[ChoiceBeatDigest]
    var_usage: list[StateVarUsage]
    never_read_vars: list[str]
    never_written_vars: list[str]


class ScriptEvaluation(VNJudgeModel):
    """Final report assembled in code from the two lens reviews."""

    script_title: str
    verdict: Verdict
    overall_score: float = Field(..., ge=1.0, le=5.0)
    dimension_scores: dict[str, int] = Field(..., description="dimension name -> 1-5 score; the numeric trail for cross-iteration progress tracking")
    playwright: LensReview
    director: LensReview
    priorities: list[JudgeFinding] = Field(..., description="All findings, ranked by severity then fix effort")
    regeneration_guidance: list[str] = Field(..., description="Compact directives derived from critical/major findings, feedable into the next generation run")
    digest: ScriptDigest


# --- Iteration progress (computed in code; numeric stopping rule for the loop) -


ProgressStatus = Literal["improved", "plateaued", "regressed"]
ProgressRecommendation = Literal["stop_target_reached", "stop_plateaued", "continue", "rollback"]


class DimensionDelta(VNJudgeModel):
    dimension: str
    baseline: int
    current: int
    delta: int


class EvaluationDelta(VNJudgeModel):
    """Numeric comparison of an evaluation against a baseline run, so a
    self-improvement loop has an objective stop condition instead of
    flipping back and forth on qualitative feedback."""

    baseline_score: float
    current_score: float
    overall_delta: float
    dimensions: list[DimensionDelta]
    improved_dimensions: list[str]
    regressed_dimensions: list[str]
    status: ProgressStatus
    recommendation: ProgressRecommendation
