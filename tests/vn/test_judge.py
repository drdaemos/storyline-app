"""M9: LLM-as-a-judge — lens gating, deterministic assembly, digest, progress rule, report."""

import pytest

from src.models.vn import Script
from src.models.vn.judge import (
    DIRECTOR_DIMENSIONS,
    PLAYWRIGHT_DIMENSIONS,
    CraftCheck,
    DimensionAssessment,
    JudgeFinding,
    JudgeLens,
    LensReview,
    LLMCraftCheck,
    LLMDimensionAssessment,
    LLMJudgeFinding,
    LLMLensReview,
    LLMStrengthNote,
    ScriptEvaluation,
    StrengthNote,
)
from src.vn.judge import VNScriptJudge, compare_evaluations, render_markdown
from src.vn.judge.rendering import build_digest, render_digest_text, render_script_text
from src.vn.pipeline.repair import VNGenerationError
from tests.vn.helpers import FakeProcessor


def make_lens_review(lens: JudgeLens, script: Script, score: int = 3, findings: list[JudgeFinding] | None = None) -> LensReview:
    dimensions = PLAYWRIGHT_DIMENSIONS if lens == "playwright" else DIRECTOR_DIMENSIONS
    return LensReview(
        dimensions=[
            DimensionAssessment(
                dimension=name,
                craft_checks=[CraftCheck(check="has_conflict", evidence=f"scene {script.scenes[0].id}", passed=True)],
                analysis="competent but unremarkable",
                score=score,
                score_rationale="meets the 3 anchor",
            )
            for name in dimensions
        ],
        findings=findings or [],
        strengths=[StrengthNote(scene_id=script.scenes[0].id, quote=script.scenes[0].intent, why="strong opening pressure")],
    )


def make_llm_lens_review(lens: JudgeLens, script: Script, score: int = 3, findings: list[JudgeFinding] | None = None) -> LLMLensReview:
    return lens_review_to_llm(make_lens_review(lens, script, score=score, findings=findings))


def lens_review_to_llm(review: LensReview) -> LLMLensReview:
    return LLMLensReview(
        dimensions=[
            LLMDimensionAssessment(
                dimension=assessment.dimension,
                craft_checks=[
                    LLMCraftCheck(check=check.check, evidence=check.evidence, passed=check.passed)
                    for check in assessment.craft_checks
                ],
                analysis=assessment.analysis,
                score=assessment.score,
                score_rationale=assessment.score_rationale,
            )
            for assessment in review.dimensions
        ],
        findings=[
            LLMJudgeFinding(
                severity=finding.severity,
                dimension=finding.dimension,
                scene_id=finding.scene_id or "",
                beat_id=finding.beat_id or "",
                quote=finding.quote,
                issue=finding.issue,
                why_it_matters=finding.why_it_matters,
                suggested_fix=finding.suggested_fix,
                fix_effort=finding.fix_effort,
            )
            for finding in review.findings
        ],
        strengths=[
            LLMStrengthNote(scene_id=strength.scene_id or "", quote=strength.quote, why=strength.why)
            for strength in review.strengths
        ],
    )


def make_finding(script: Script, severity: str = "major", fix_effort: str = "small", dimension: str = "dramatic_structure", scene_id: str | None = None) -> JudgeFinding:
    return JudgeFinding(
        severity=severity,
        dimension=dimension,
        scene_id=scene_id if scene_id is not None else script.scenes[0].id,
        quote=script.scenes[0].intent,
        issue="stakes plateau in the middle",
        why_it_matters="the player loses the dramatic question",
        suggested_fix="escalate the guard's suspicion between visits",
        fix_effort=fix_effort,
    )


class TestVNScriptJudge:
    def test_evaluation_assembled_from_both_lenses(self, locked_granary: Script):
        processor = FakeProcessor([make_llm_lens_review("playwright", locked_granary, score=3), make_llm_lens_review("director", locked_granary, score=4)])
        evaluation = VNScriptJudge(processor).evaluate(locked_granary)

        assert evaluation.script_title == locked_granary.meta.title
        assert set(evaluation.dimension_scores) == set(PLAYWRIGHT_DIMENSIONS) | set(DIRECTOR_DIMENSIONS)
        assert evaluation.overall_score == 3.5
        assert evaluation.verdict == "consider"
        assert processor.calls == [LLMLensReview, LLMLensReview]

    def test_verdict_thresholds(self, locked_granary: Script):
        for score, verdict in [(5, "recommend"), (3, "consider"), (2, "needs_revision")]:
            processor = FakeProcessor([make_llm_lens_review("playwright", locked_granary, score=score), make_llm_lens_review("director", locked_granary, score=score)])
            assert VNScriptJudge(processor).evaluate(locked_granary).verdict == verdict

    def test_priorities_ranked_by_severity_then_effort(self, locked_granary: Script):
        playwright = make_llm_lens_review(
            "playwright",
            locked_granary,
            findings=[make_finding(locked_granary, severity="minor", fix_effort="small"), make_finding(locked_granary, severity="critical", fix_effort="structural")],
        )
        director = make_llm_lens_review("director", locked_granary, findings=[make_finding(locked_granary, severity="critical", fix_effort="small", dimension="choice_meaningfulness")])
        evaluation = VNScriptJudge(FakeProcessor([playwright, director])).evaluate(locked_granary)

        assert [(f.severity, f.fix_effort) for f in evaluation.priorities] == [("critical", "small"), ("critical", "structural"), ("minor", "small")]
        # guidance derives from critical/major findings only
        assert len(evaluation.regeneration_guidance) >= 2
        assert all("stakes plateau" in item or "State var" in item for item in evaluation.regeneration_guidance)

    def test_hallucinated_citation_is_repaired(self, locked_granary: Script):
        bad = make_llm_lens_review("playwright", locked_granary, findings=[make_finding(locked_granary, scene_id="sc_ghost")])
        good = make_llm_lens_review("playwright", locked_granary)
        processor = FakeProcessor([bad, good, make_llm_lens_review("director", locked_granary)])
        evaluation = VNScriptJudge(processor).evaluate(locked_granary)

        assert evaluation.overall_score == 3.0
        assert processor.calls == [LLMLensReview, LLMLensReview, LLMLensReview]

    def test_wrong_dimension_set_exhausts_attempts(self, locked_granary: Script):
        wrong_lens = make_llm_lens_review("director", locked_granary)  # director dims offered for the playwright pass
        with pytest.raises(VNGenerationError):
            VNScriptJudge(FakeProcessor([wrong_lens, wrong_lens]), max_attempts=2).evaluate(locked_granary)

    def test_unparseable_output_is_retried(self, locked_granary: Script):
        processor = FakeProcessor(["garbage", make_llm_lens_review("playwright", locked_granary), make_llm_lens_review("director", locked_granary)])
        evaluation = VNScriptJudge(processor).evaluate(locked_granary)
        assert evaluation.overall_score == 3.0


class TestDigestAndRendering:
    def test_digest_counts_are_consistent(self, locked_granary: Script):
        digest = build_digest(locked_granary)
        assert digest.scene_count == len(locked_granary.scenes)
        assert digest.beat_count == sum(len(scene.beats) for scene in locked_granary.scenes)
        assert digest.beat_count == digest.plain_beat_count + digest.choice_beat_count + digest.check_beat_count + digest.ending_beat_count
        assert set(digest.ending_ids) == {"end_bargain", "end_flight"}
        assert {usage.name for usage in digest.var_usage} == {var.name for var in locked_granary.state_vars}
        assert set(digest.never_read_vars) == {usage.name for usage in digest.var_usage if usage.reads == 0}

    def test_script_text_mentions_every_scene_and_beat(self, locked_granary: Script):
        text = render_script_text(locked_granary)
        for scene in locked_granary.scenes:
            assert scene.id in text
            for beat in scene.beats:
                assert beat.id in text
        assert "ENDING" in text

    def test_digest_text_flags_unread_vars(self, locked_granary: Script):
        digest = build_digest(locked_granary).model_copy(update={"never_read_vars": ["dummy"], "var_usage": []})
        assert "dummy" not in render_digest_text(digest)  # var lines come from var_usage
        digest = build_digest(locked_granary)
        text = render_digest_text(digest)
        for usage in digest.var_usage:
            assert usage.name in text


class TestReportAndProgress:
    def make_evaluation(self, locked_granary: Script, scores: dict[str, int]) -> ScriptEvaluation:
        overall = round(sum(scores.values()) / len(scores), 2)
        review = make_lens_review("playwright", locked_granary)
        return ScriptEvaluation(
            script_title=locked_granary.meta.title,
            verdict="consider",
            overall_score=overall,
            dimension_scores=scores,
            playwright=review,
            director=make_lens_review("director", locked_granary),
            priorities=[make_finding(locked_granary, severity="critical")],
            regeneration_guidance=["[sc_gate] escalate the guard's suspicion"],
            digest=build_digest(locked_granary),
        )

    def test_markdown_report_contains_scores_findings_and_guidance(self, locked_granary: Script):
        evaluation = self.make_evaluation(locked_granary, {"dramatic_structure": 3, "choice_meaningfulness": 4})
        text = render_markdown(evaluation)
        assert "dramatic_structure" in text
        assert "stakes plateau" in text
        assert "Regeneration guidance" in text
        assert str(evaluation.overall_score) in text

    def test_progress_improved_continues(self, locked_granary: Script):
        baseline = self.make_evaluation(locked_granary, {"a": 2, "b": 2})
        current = self.make_evaluation(locked_granary, {"a": 3, "b": 3})
        delta = compare_evaluations(current, baseline, target_score=4.0)
        assert delta.status == "improved"
        assert delta.recommendation == "continue"
        assert delta.improved_dimensions == ["a", "b"]

    def test_progress_target_reached_stops(self, locked_granary: Script):
        baseline = self.make_evaluation(locked_granary, {"a": 3, "b": 3})
        current = self.make_evaluation(locked_granary, {"a": 4, "b": 5})
        assert compare_evaluations(current, baseline, target_score=4.0).recommendation == "stop_target_reached"

    def test_progress_plateau_stops(self, locked_granary: Script):
        baseline = self.make_evaluation(locked_granary, {"a": 3, "b": 3})
        current = self.make_evaluation(locked_granary, {"a": 3, "b": 3})
        delta = compare_evaluations(current, baseline, target_score=4.0)
        assert delta.status == "plateaued"
        assert delta.recommendation == "stop_plateaued"

    def test_progress_regression_rolls_back(self, locked_granary: Script):
        baseline = self.make_evaluation(locked_granary, {"a": 4, "b": 3})
        current = self.make_evaluation(locked_granary, {"a": 2, "b": 3})
        delta = compare_evaluations(current, baseline, target_score=4.0)
        assert delta.status == "regressed"
        assert delta.recommendation == "rollback"
        assert delta.regressed_dimensions == ["a"]
