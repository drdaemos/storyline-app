"""Running scenario evaluations and comparing two runs, with results written to an output directory.

A run directory doubles as a Storyline workspace: each case's story is a subdirectory with its conversation
history, so ``storyline write --workspace <run dir> --story <case>`` opens it in the terminal UI.
"""

import asyncio
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel
from pydantic_ai.models import Model
from pydantic_evals import Case, Dataset, increment_eval_metric
from pydantic_evals.evaluators import Evaluator
from pydantic_evals.reporting import EvaluationReport, ReportCase

from storyline.agent import catalog_prompt_version, create_writer_agent
from storyline.evals.evaluators import BehaviourCriteria, HabitChecks, MechanicsUse, ProseDiagnostics
from storyline.evals.judge import BehaviourJudge, CraftComparison, CraftJudge, PairwiseResult
from storyline.evals.runner import ScenarioRun, ScenarioRunner, story_preset
from storyline.evals.scenarios import Scenario, load_scenarios
from storyline.presets import BUNDLED_PRESETS
from storyline.registry import MECHANICS

RUN_INFO_FILENAME = "run.json"
INSTRUCTIONS_FILENAME = "instructions.md"
SUMMARY_FILENAME = "summary.md"
CASE_SUFFIX = ".run.json"
WEB_SEARCH_TOOL = "web_search"


class EvalError(ValueError):
    """Raised when an evaluation cannot be started or its inputs are unusable."""


class RunInfo(BaseModel):
    """What a run directory was produced with."""

    model_name: str
    prompt_version: str
    judge_model_name: str | None
    repeat: int
    scenarios: tuple[str, ...]
    created: datetime


@dataclass(frozen=True)
class RunRequest:
    """One evaluation run: which scenarios, with which writer and judge, written where."""

    scenario_names: Sequence[str]
    model_name: str
    instructions: str
    out_dir: Path
    judge_model_name: str | None = None
    repeat: int = 1
    max_concurrency: int = 2
    show_progress: bool = True


class EvalService:
    """Runs scenarios against the writer agent and compares runs; the boundary the CLI talks to."""

    def __init__(self, *, scenarios_dir: Path, seeds_dir: Path) -> None:
        self._scenarios_dir = scenarios_dir
        self._seeds_dir = seeds_dir

    async def run(self, request: RunRequest, *, writer_model: Model | str, judge_model: Model | str | None) -> Path:
        """Play every requested scenario, check and judge the results, and return the summary file."""
        scenarios = load_scenarios(self._scenarios_dir, self._seeds_dir, request.scenario_names)
        if request.out_dir.exists() and any(request.out_dir.iterdir()):
            raise EvalError(f"Output directory is not empty: {request.out_dir}")
        request.out_dir.mkdir(parents=True, exist_ok=True)

        version = catalog_prompt_version(request.instructions, BUNDLED_PRESETS, MECHANICS)
        info = RunInfo(
            model_name=request.model_name,
            prompt_version=version,
            judge_model_name=request.judge_model_name if judge_model is not None else None,
            repeat=request.repeat,
            scenarios=tuple(scenario.name for scenario in scenarios),
            created=datetime.now(UTC),
        )
        (request.out_dir / RUN_INFO_FILENAME).write_text(info.model_dump_json(indent=2), encoding="utf-8")
        (request.out_dir / INSTRUCTIONS_FILENAME).write_text(request.instructions, encoding="utf-8")

        runner = ScenarioRunner(create_writer_agent(instructions=request.instructions), model=writer_model, seeds_dir=self._seeds_dir)
        played: Counter[str] = Counter()

        async def play(scenario: Scenario) -> ScenarioRun:
            played[scenario.name] += 1
            case_name = f"{scenario.name}-{played[scenario.name]}"
            story_dir = request.out_dir / case_name
            turns = await runner.run(scenario, story_dir)
            run = ScenarioRun(case_name=case_name, scenario=scenario, model_name=request.model_name, prompt_version=version, preset=await story_preset(story_dir), turns=turns)
            (request.out_dir / f"{case_name}{CASE_SUFFIX}").write_text(run.model_dump_json(indent=2), encoding="utf-8")
            _record_usage(run)
            return run

        evaluators: list[Evaluator[Scenario, ScenarioRun, None]] = [HabitChecks(), MechanicsUse(), ProseDiagnostics()]
        if judge_model is not None:
            evaluators.append(BehaviourCriteria(judge=BehaviourJudge(judge_model)))
        dataset = Dataset[Scenario, ScenarioRun, None](name="storyline-writer", cases=[Case(name=scenario.name, inputs=scenario) for scenario in scenarios], evaluators=evaluators)
        report = await dataset.evaluate(play, name=request.out_dir.name, max_concurrency=request.max_concurrency, repeat=request.repeat, progress=request.show_progress)

        summary = request.out_dir / SUMMARY_FILENAME
        summary.write_text(render_run_summary(info, report), encoding="utf-8")
        return summary

    async def compare(self, run_a: Path, run_b: Path, *, judge_model: Model | str, out_file: Path, max_concurrency: int = 2) -> Path:
        """Judge the stories of matching cases from two run directories side by side and return the summary file."""
        cases_a, cases_b = _load_cases(run_a), _load_cases(run_b)
        shared = sorted(set(cases_a) & set(cases_b))
        if not shared:
            raise EvalError(f"{run_a} and {run_b} have no cases in common.")

        judge = CraftJudge(judge_model)
        limit = asyncio.Semaphore(max_concurrency)

        async def judge_pair(name: str) -> PairwiseResult:
            async with limit:
                return await judge.compare(cases_a[name], cases_b[name])

        results = await asyncio.gather(*(judge_pair(name) for name in shared))
        unmatched = sorted(set(cases_a) ^ set(cases_b))
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(render_comparison(run_a, run_b, results, unmatched), encoding="utf-8")
        return out_file


def render_run_summary(info: RunInfo, report: EvaluationReport[Scenario, ScenarioRun, None]) -> str:
    """Markdown summary: tallies per check and criterion first, then every case with its evidence."""
    lines = [
        f"# Eval run {report.name}",
        "",
        f"Writer `{info.model_name}` · prompt `{info.prompt_version}` · judge `{info.judge_model_name or 'none'}` · repeat {info.repeat}",
        "",
    ]
    cases = sorted(report.cases, key=lambda case: case.output.case_name)
    lines += _tallies(cases)
    for case in cases:
        lines += _case_section(case)
    if report.failures:
        lines += ["## Failed cases", ""]
        lines += [f"- {failure.name}: {failure.error_message}" for failure in report.failures]
    return "\n".join(lines) + "\n"


def render_comparison(run_a: Path, run_b: Path, results: Sequence[PairwiseResult], unmatched: Sequence[str]) -> str:
    """Markdown summary of pairwise outcomes per dimension, then each case's comparisons in both orders."""
    lines = [f"# Craft comparison: A = {run_a.name}, B = {run_b.name}", "", _describe_run("A", run_a), _describe_run("B", run_b), ""]
    lines += [
        "Each case is judged twice, once with each story shown first. A or B means both orders agreed; a lean means one",
        "order preferred it and the other saw no difference; split means the orders disagreed.",
        "",
        "| dimension | A | lean A | same | split | lean B | B |",
        "|---|---|---|---|---|---|---|",
    ]
    for dimension in CraftComparison.model_fields:
        counts = Counter(result.dimensions[dimension].outcome for result in results)
        lines.append(f"| {dimension} | " + " | ".join(str(counts[outcome]) for outcome in ("A", "lean A", "same", "split", "lean B", "B")) + " |")
    for result in results:
        lines += ["", f"## {result.case_name}", ""]
        for dimension, outcome in result.dimensions.items():
            lines.append(f"- **{dimension}: {outcome.outcome}**")
            lines.append(f"  - A shown first, chose {outcome.a_first.preference}: {outcome.a_first.comparison}")
            lines.append(f"  - B shown first, chose {outcome.b_first.preference}: {outcome.b_first.comparison}")
    if unmatched:
        lines += ["", f"Cases present in only one run: {', '.join(unmatched)}"]
    return "\n".join(lines) + "\n"


def _record_usage(run: ScenarioRun) -> None:
    """Token and request counts come from the traced model calls; web searches are counted here."""
    increment_eval_metric("web_searches", sum(1 for turn in run.turns for call in turn.tool_calls if call.name == WEB_SEARCH_TOOL))


def _tallies(cases: Sequence[ReportCase[Scenario, ScenarioRun, None]]) -> list[str]:
    passed: dict[str, list[bool]] = defaultdict(list)
    verdicts: dict[str, Counter[str]] = defaultdict(Counter)
    for case in cases:
        for name, assertion in case.assertions.items():
            passed[name].append(assertion.value)
        for name, label in case.labels.items():
            verdicts[name][label.value] += 1
    lines = []
    if passed:
        lines += ["## Habit checks", "", "| check | passed |", "|---|---|"]
        lines += [f"| {name} | {sum(results)}/{len(results)} |" for name, results in passed.items()]
        lines.append("")
    if verdicts:
        lines += ["## Behaviour criteria", "", "| criterion | yes | partly | no | n/a |", "|---|---|---|---|---|"]
        lines += [f"| {name} | {counts['yes']} | {counts['partly']} | {counts['no']} | {counts['n/a']} |" for name, counts in verdicts.items()]
        lines.append("")
    return lines


def _case_section(case: ReportCase[Scenario, ScenarioRun, None]) -> list[str]:
    run = case.output
    lines = [f"## {run.case_name}", "", f"{run.scenario.description.strip()}", ""]
    lines += [f"- {'pass' if result.value else 'FAIL'} {name}: {result.reason}" for name, result in case.assertions.items()]
    lines += [f"- {name}: **{result.value}** — {result.reason}" for name, result in case.labels.items()]
    lines += [f"- {name}: {result.value} — {result.reason}" for name, result in case.scores.items()]
    metrics = ", ".join(f"{name} {value}" for name, value in case.metrics.items())
    lines += [f"- usage: {metrics}" if metrics else "- usage: none recorded", f"- duration: {case.task_duration:.0f}s"]
    lines += [f"- evaluator failed: {failure.name}: {failure.error_message}" for failure in case.evaluator_failures]
    lines.append("")
    return lines


def _load_cases(run_dir: Path) -> dict[str, ScenarioRun]:
    if not run_dir.is_dir():
        raise EvalError(f"Not a run directory: {run_dir}")
    runs = [ScenarioRun.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted(run_dir.glob(f"*{CASE_SUFFIX}"))]
    return {run.case_name: run for run in runs}


def _describe_run(label: str, run_dir: Path) -> str:
    info_path = run_dir / RUN_INFO_FILENAME
    if not info_path.is_file():
        return f"- {label}: {run_dir}"
    info = RunInfo.model_validate_json(info_path.read_text(encoding="utf-8"))
    return f"- {label}: writer `{info.model_name}`, prompt `{info.prompt_version}`"
