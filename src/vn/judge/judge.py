"""VNScriptJudge: two-lens LLM-as-a-judge over a generated script.

Each lens (playwright, interactivity director) is one structured-output call,
hard-gated in code: the dimension set must match the lens exactly and every cited
scene/beat id must exist in the script (hallucinated citations are rejected and fed
back through the same bounded repair loop the generation pipeline uses). Scores,
verdict, priority ranking, and regeneration guidance are assembled deterministically
— the LLM never aggregates its own numbers."""

from pydantic import ValidationError

from src.models.prompt_processor import PromptProcessor
from src.models.vn.input import VNInput
from src.models.vn.judge import (
    DIRECTOR_DIMENSIONS,
    PLAYWRIGHT_DIMENSIONS,
    CraftCheck,
    DimensionAssessment,
    FixEffort,
    JudgeFinding,
    JudgeLens,
    LensReview,
    LLMLensReview,
    ScriptEvaluation,
    Severity,
    StrengthNote,
    Verdict,
)
from src.models.vn.script import Script
from src.models.vn.validation import ValidationIssue, ValidationReport
from src.vn.judge.prompts import DIRECTOR_SYSTEM_PROMPT, PLAYWRIGHT_SYSTEM_PROMPT, lens_user_prompt
from src.vn.judge.rendering import build_digest, render_digest_text, render_script_text
from src.vn.pipeline.parsing import VNParseError, request_model
from src.vn.pipeline.repair import run_with_repair

LENS_MAX_TOKENS = 16384
DEFAULT_JUDGE_ATTEMPTS = 2
MAX_FINDINGS_PER_LENS = 7

_SEVERITY_RANK: dict[Severity, int] = {"critical": 0, "major": 1, "minor": 2, "polish": 3}
_EFFORT_RANK: dict[FixEffort, int] = {"small": 0, "moderate": 1, "structural": 2}


def _empty_to_none(value: str) -> str | None:
    stripped = value.strip()
    return stripped or None


class VNScriptJudge:
    def __init__(self, processor: PromptProcessor, max_attempts: int = DEFAULT_JUDGE_ATTEMPTS) -> None:
        self.processor = processor
        self.max_attempts = max_attempts

    def evaluate(self, script: Script, vn_input: VNInput | None = None) -> ScriptEvaluation:
        digest = build_digest(script)
        digest_text = render_digest_text(digest)
        script_text = render_script_text(script)

        playwright = self._lens_review(script, "playwright", vn_input, digest_text, script_text)
        director = self._lens_review(script, "director", vn_input, digest_text, script_text)

        scores = {assessment.dimension: assessment.score for review in (playwright, director) for assessment in review.dimensions}
        overall = round(sum(scores.values()) / len(scores), 2)
        priorities = sorted(
            [*playwright.findings, *director.findings],
            key=lambda finding: (_SEVERITY_RANK[finding.severity], _EFFORT_RANK[finding.fix_effort]),
        )
        return ScriptEvaluation(
            script_title=script.meta.title,
            verdict=self._verdict(overall),
            overall_score=overall,
            dimension_scores=dict(scores),
            playwright=playwright,
            director=director,
            priorities=priorities,
            regeneration_guidance=self._guidance(priorities, digest_never_read=digest.never_read_vars),
            digest=digest,
        )

    def _lens_review(self, script: Script, lens: JudgeLens, vn_input: VNInput | None, digest_text: str, script_text: str) -> LensReview:
        system_prompt = PLAYWRIGHT_SYSTEM_PROMPT if lens == "playwright" else DIRECTOR_SYSTEM_PROMPT
        return run_with_repair(
            produce=lambda feedback: self._coerce_lens_review(
                request_model(
                    self.processor,
                    system_prompt,
                    lens_user_prompt(lens, vn_input, digest_text, script_text, feedback),
                    LLMLensReview,
                    LENS_MAX_TOKENS,
                )
            ),
            gate=lambda review: self._gate(review, lens, script),
            max_attempts=self.max_attempts,
        )

    def _coerce_lens_review(self, review: LLMLensReview) -> LensReview:
        try:
            return LensReview(
                dimensions=[
                    DimensionAssessment(
                        dimension=assessment.dimension,
                        craft_checks=[
                            CraftCheck(check=check.check, evidence=check.evidence, passed=check.passed)
                            for check in assessment.craft_checks
                        ],
                        analysis=assessment.analysis,
                        score=assessment.score,
                        score_rationale=assessment.score_rationale,
                    )
                    for assessment in review.dimensions
                ],
                findings=[
                    JudgeFinding(
                        severity=finding.severity,
                        dimension=finding.dimension,
                        scene_id=_empty_to_none(finding.scene_id),
                        beat_id=_empty_to_none(finding.beat_id),
                        quote=finding.quote,
                        issue=finding.issue,
                        why_it_matters=finding.why_it_matters,
                        suggested_fix=finding.suggested_fix,
                        fix_effort=finding.fix_effort,
                    )
                    for finding in review.findings
                ],
                strengths=[
                    StrengthNote(scene_id=_empty_to_none(strength.scene_id), quote=strength.quote, why=strength.why)
                    for strength in review.strengths
                ],
            )
        except ValidationError as exc:
            raise VNParseError(
                ValidationReport(issues=[ValidationIssue(code="output_parse_error", message=str(error.get("msg", error))) for error in exc.errors()])
            ) from exc

    def _gate(self, review: LensReview, lens: JudgeLens, script: Script) -> ValidationReport:
        """Reject reviews with the wrong dimension set or citations of ids that do not exist."""
        issues: list[ValidationIssue] = []
        expected = set(PLAYWRIGHT_DIMENSIONS if lens == "playwright" else DIRECTOR_DIMENSIONS)
        got = [assessment.dimension for assessment in review.dimensions]
        if len(got) != len(set(got)):
            issues.append(ValidationIssue(code="duplicate_dimension", message=f"dimensions assessed more than once: {sorted({d for d in got if got.count(d) > 1})}"))
        missing = expected - set(got)
        extra = set(got) - expected
        if missing:
            issues.append(ValidationIssue(code="missing_dimension", message=f"missing {lens} dimensions: {sorted(missing)}"))
        if extra:
            issues.append(ValidationIssue(code="wrong_lens_dimension", message=f"dimensions outside the {lens} lens: {sorted(extra)}"))
        if len(review.findings) > MAX_FINDINGS_PER_LENS:
            issues.append(ValidationIssue(code="too_many_findings", message=f"{len(review.findings)} findings; rank and keep at most 5"))

        scene_ids = {scene.id for scene in script.scenes}
        beat_ids = {beat.id for scene in script.scenes for beat in scene.beats}
        for finding in review.findings:
            if finding.scene_id is not None and finding.scene_id not in scene_ids:
                issues.append(ValidationIssue(code="unknown_scene_id", message=f"finding cites scene '{finding.scene_id}' which does not exist"))
            if finding.beat_id is not None and finding.beat_id not in beat_ids:
                issues.append(ValidationIssue(code="unknown_beat_id", message=f"finding cites beat '{finding.beat_id}' which does not exist"))
        for strength in review.strengths:
            if strength.scene_id is not None and strength.scene_id not in scene_ids:
                issues.append(ValidationIssue(code="unknown_scene_id", message=f"strength cites scene '{strength.scene_id}' which does not exist"))
        return ValidationReport(issues=issues)

    def _verdict(self, overall: float) -> Verdict:
        if overall >= 4.0:
            return "recommend"
        if overall >= 3.0:
            return "consider"
        return "needs_revision"

    def _guidance(self, priorities: list[JudgeFinding], digest_never_read: list[str]) -> list[str]:
        guidance = [
            f"[{finding.scene_id or 'global'}] {finding.issue} Direction: {finding.suggested_fix}"
            for finding in priorities
            if finding.severity in ("critical", "major")
        ]
        guidance.extend(
            f"[global] State var '{name}' is written but never read; make its consequences visible through guards or checks, or remove it."
            for name in digest_never_read
        )
        return guidance
