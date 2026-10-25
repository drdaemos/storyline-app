"""pydantic-evals evaluators over scenario runs.

Habit checks report as assertions, prose diagnostics as measured values, and behaviour criteria as labels
(yes / partly / no / n/a); every result carries its evidence as the reason.
"""

from dataclasses import dataclass

from pydantic_evals.evaluators import EvaluationReason, Evaluator, EvaluatorContext

from storyline.evals import checks
from storyline.evals.judge import BehaviourJudge
from storyline.evals.runner import ScenarioRun
from storyline.evals.scenarios import Scenario

type RunContext = EvaluatorContext[Scenario, ScenarioRun, None]


@dataclass
class HabitChecks(Evaluator[Scenario, ScenarioRun, None]):
    """Whether the agent worked the way the writer prompt asks."""

    def evaluate(self, ctx: RunContext) -> dict[str, EvaluationReason]:
        run = ctx.output
        results = {
            "writes_when_expected": checks.writes_when_expected(run),
            "updates_expected_lore": checks.updates_expected_lore(run),
            "keeps_a_plan": checks.keeps_a_plan(run),
            "replies_leave_prose_in_the_story": checks.replies_leave_prose_in_the_story(run),
            "edits_send_only_changes": checks.edits_send_only_changes(run),
            "keeps_sealed_content_out_of_replies": checks.keeps_sealed_content_out_of_replies(run),
        }
        return {name: EvaluationReason(value=check.passed, reason=check.detail) for name, check in results.items()}


@dataclass
class MechanicsUse(Evaluator[Scenario, ScenarioRun, None]):
    """How much the agent used the roleplay mechanics; measured, not judged, since summary stretches need no review or roll."""

    def evaluate(self, ctx: RunContext) -> dict[str, EvaluationReason]:
        run = ctx.output
        results = {
            "prose_turns_without_review": checks.prose_turns_without_review(run),
            "review_calls": checks.tool_call_count(run, checks.REVIEW_TOOL),
            "roll_calls": checks.tool_call_count(run, checks.ROLL_TOOL),
            "clock_ticks": checks.tool_call_count(run, checks.CLOCK_TOOL),
        }
        return {name: EvaluationReason(value=finding.value, reason=finding.detail) for name, finding in results.items()}


@dataclass
class ProseDiagnostics(Evaluator[Scenario, ScenarioRun, None]):
    """Published prose metrics over everything the agent wrote in the run."""

    def evaluate(self, ctx: RunContext) -> dict[str, EvaluationReason]:
        run = ctx.output
        prose = "\n\n".join(turn.new_prose for turn in run.turns if turn.new_prose)
        results = {
            "slop_index": checks.slop_index(prose),
            "stock_words": checks.stock_vocabulary(prose),
            "not_x_but_y_per_1k_words": checks.not_x_but_y(prose),
            "short_paragraphs_per_1k_chars": checks.short_paragraph_rate(prose),
            "repeated_5grams_pct": checks.self_repetition(run.turns),
        }
        return {name: EvaluationReason(value=finding.value, reason=finding.detail) for name, finding in results.items()}


@dataclass
class BehaviourCriteria(Evaluator[Scenario, ScenarioRun, None]):
    """The behaviour judge's verdict on each criterion, with its evidence."""

    judge: BehaviourJudge

    async def evaluate(self, ctx: RunContext) -> dict[str, EvaluationReason]:
        review = await self.judge.review(ctx.output)
        return {name: EvaluationReason(value=verdict.verdict, reason=verdict.evidence) for name, verdict in review}

    def build_serialization_arguments(self) -> dict[str, object]:
        """The judge holds a live agent; keep it out of the serialized evaluator spec."""
        return {}
