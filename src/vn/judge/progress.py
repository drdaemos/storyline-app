"""Numeric progress tracking between judge runs.

A self-improvement loop needs an objective stop condition, not just qualitative
feedback — otherwise revisions flip back and forth indefinitely. The comparison is
pure code over the persisted dimension scores: improved / plateaued / regressed,
plus an explicit recommendation (stop on target or plateau, roll back on regression)."""

from src.models.vn.judge import DimensionDelta, EvaluationDelta, ProgressRecommendation, ProgressStatus, ScriptEvaluation

DEFAULT_TARGET_SCORE = 4.0
PLATEAU_EPSILON = 0.15


def compare_evaluations(
    current: ScriptEvaluation,
    baseline: ScriptEvaluation,
    target_score: float = DEFAULT_TARGET_SCORE,
    epsilon: float = PLATEAU_EPSILON,
) -> EvaluationDelta:
    shared = sorted(set(current.dimension_scores) & set(baseline.dimension_scores))
    dimensions = [
        DimensionDelta(
            dimension=name,
            baseline=baseline.dimension_scores[name],
            current=current.dimension_scores[name],
            delta=current.dimension_scores[name] - baseline.dimension_scores[name],
        )
        for name in shared
    ]
    overall_delta = round(current.overall_score - baseline.overall_score, 2)

    status: ProgressStatus
    if overall_delta > epsilon:
        status = "improved"
    elif overall_delta < -epsilon:
        status = "regressed"
    else:
        status = "plateaued"

    recommendation: ProgressRecommendation
    if current.overall_score >= target_score:
        recommendation = "stop_target_reached"
    elif status == "regressed":
        recommendation = "rollback"
    elif status == "plateaued":
        recommendation = "stop_plateaued"
    else:
        recommendation = "continue"

    return EvaluationDelta(
        baseline_score=baseline.overall_score,
        current_score=current.overall_score,
        overall_delta=overall_delta,
        dimensions=dimensions,
        improved_dimensions=[d.dimension for d in dimensions if d.delta > 0],
        regressed_dimensions=[d.dimension for d in dimensions if d.delta < 0],
        status=status,
        recommendation=recommendation,
    )
