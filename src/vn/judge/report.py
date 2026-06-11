"""Human-readable markdown rendering of a ScriptEvaluation (and optional progress delta)."""

from src.models.vn.judge import EvaluationDelta, JudgeLens, LensReview, ScriptEvaluation


def _lens_section(title: str, lens: JudgeLens, review: LensReview) -> list[str]:
    lines = [f"## {title}"]
    for assessment in review.dimensions:
        lines.append(f"### {assessment.dimension} — {assessment.score}/5")
        for check in assessment.craft_checks:
            mark = "x" if check.passed else " "
            lines.append(f"- [{mark}] `{check.check}` — {check.evidence}")
        lines.append("")
        lines.append(assessment.analysis)
        lines.append("")
        lines.append(f"*Anchor:* {assessment.score_rationale}")
        lines.append("")
    if review.strengths:
        lines.append(f"### Strengths to preserve ({lens})")
        for strength in review.strengths:
            location = f" `{strength.scene_id}`" if strength.scene_id else ""
            lines.append(f"- {strength.why}{location} — “{strength.quote}”")
        lines.append("")
    return lines


def render_markdown(evaluation: ScriptEvaluation, delta: EvaluationDelta | None = None) -> str:
    lines = [
        f"# Script review: {evaluation.script_title}",
        "",
        f"**Verdict:** {evaluation.verdict} · **Overall score:** {evaluation.overall_score}/5",
        "",
        "| Dimension | Score |",
        "|---|---|",
    ]
    lines.extend(f"| {name} | {score} |" for name, score in evaluation.dimension_scores.items())
    lines.append("")

    if delta is not None:
        lines.append("## Progress vs baseline")
        lines.append(f"**{delta.status}** ({delta.baseline_score} → {delta.current_score}, Δ {delta.overall_delta:+.2f}) — recommendation: **{delta.recommendation}**")
        for dim in delta.dimensions:
            if dim.delta != 0:
                lines.append(f"- {dim.dimension}: {dim.baseline} → {dim.current} ({dim.delta:+d})")
        lines.append("")

    if evaluation.priorities:
        lines.append("## Prioritized findings")
        for index, finding in enumerate(evaluation.priorities, start=1):
            location = "/".join(part for part in [finding.scene_id, finding.beat_id] if part) or "global"
            lines.append(f"{index}. **[{finding.severity}]** `{location}` ({finding.dimension}, {finding.fix_effort} fix)")
            lines.append(f"   - Issue: {finding.issue}")
            lines.append(f"   - Why it matters: {finding.why_it_matters}")
            lines.append(f"   - Direction: {finding.suggested_fix}")
        lines.append("")

    lines.extend(_lens_section("Playwright lens (dramatic craft)", "playwright", evaluation.playwright))
    lines.extend(_lens_section("Director lens (interactive craft)", "director", evaluation.director))

    if evaluation.regeneration_guidance:
        lines.append("## Regeneration guidance")
        lines.append("Feed this block to `vn-generate --guidance` for the next iteration:")
        lines.append("")
        lines.extend(f"- {item}" for item in evaluation.regeneration_guidance)
        lines.append("")

    digest = evaluation.digest
    lines.append("## Structure digest")
    lines.append(
        f"{digest.scene_count} scenes, {digest.beat_count} beats "
        f"({digest.choice_beat_count} choice, {digest.check_beat_count} check, {digest.ending_beat_count} ending); "
        f"endings: {', '.join(digest.ending_ids) or 'none'}"
    )
    if digest.never_read_vars:
        lines.append(f"State vars written but never read: {', '.join(digest.never_read_vars)}")
    return "\n".join(lines) + "\n"
