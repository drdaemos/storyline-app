"""Tests for scenario evaluations: scenarios, mechanical checks, judges and the eval service."""

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_ai import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel

from storyline.agent import WRITER_INSTRUCTIONS, catalog_prompt_version, create_writer_agent, writer_prompt_version
from storyline.evals import EvalError, EvalService, RunRequest, Scenario, ScenarioError, ScenarioTurn, checks, load_scenarios
from storyline.evals.judge import BehaviourJudge, BehaviourReview, CraftComparison, CraftJudge, RoleplayReview, equal_length, session_transcript
from storyline.evals.runner import ScenarioRun, ScenarioRunner, ToolCallRecord, TurnRecord, story_preset
from storyline.mechanics import Mechanic
from storyline.presets import BUNDLED_PRESETS, Preset, PresetCatalog
from storyline.registry import MECHANICS
from storyline.workspace.file_story import FileStory
from storyline.workspace.file_workspace import FileWorkspace

REPO_EVALS = Path(__file__).parents[1] / "evals"
PLAN = "---\nsummary: The plan.\nkeywords: plan\n---\nScene one."


def _turn(**changes: object) -> TurnRecord:
    fields: dict[str, object] = {
        "prompt": "Continue.",
        "reply": "Wrote the next scene.",
        "tool_calls": (),
        "script_before": "",
        "script_after": "New scene.",
        "lore_before": {},
        "lore_after": {"plan.md": PLAN},
        "input_tokens": 10,
        "output_tokens": 5,
        "requests": 2,
    }
    return TurnRecord.model_validate({**fields, **changes})


def _run(*turns: TurnRecord, expected: tuple[ScenarioTurn, ...] | None = None, name: str = "case-1") -> ScenarioRun:
    scenario = Scenario(name="case", description="A case.", turns=expected or tuple(ScenarioTurn(prompt=turn.prompt) for turn in turns))
    return ScenarioRun(case_name=name, scenario=scenario, model_name="test", prompt_version="v", turns=turns)


def _writer_model() -> FunctionModel:
    """A writer that plans on the first turn, appends a paragraph each turn, then replies with a short note."""

    def respond(messages: list[ModelMessage], _: AgentInfo) -> ModelResponse:
        requests = [message for message in messages if isinstance(message, ModelRequest)]
        turn_number = sum(1 for request in requests if not any(isinstance(part, ToolReturnPart) for part in request.parts))
        latest = requests[-1]
        returned = [part for part in latest.parts if isinstance(part, ToolReturnPart)]
        if not returned and turn_number == 1:
            return ModelResponse(parts=[ToolCallPart(tool_name="write_lore", args={"filename": "plan.md", "content": PLAN})])
        if not returned or returned[-1].tool_name == "write_lore":
            return ModelResponse(parts=[ToolCallPart(tool_name="append_to_script", args={"text": f"\n\nThe keeper climbed the stairs, turn {turn_number}."})])
        return ModelResponse(parts=[TextPart(content="Added a scene.")])

    return FunctionModel(respond)


def _structured_model(output: dict[str, object]) -> FunctionModel:
    def respond(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content=json.dumps(output))])

    return FunctionModel(respond)


def _behaviour_output(verdict: str = "yes") -> dict[str, object]:
    criteria = ("follows_direction", "makes_progress", "collaborates", "keeps_canon", "follows_plan", "serves_premise", "applies_feedback", "hands_back_well")
    return {name: {"evidence": f"Turn 1 shows {name}.", "verdict": verdict} for name in criteria}


def _craft_model(prefers: str | None) -> FunctionModel:
    """A judge preferring the story containing ``prefers``, or always the first story shown when None."""

    def respond(messages: list[ModelMessage], _: AgentInfo) -> ModelResponse:
        prompt = str(messages[-1].parts[-1].content)
        story_a = prompt.split("<story-A>")[1].split("</story-A>")[0]
        choice = "A" if prefers is None or prefers in story_a else "B"
        output = {name: {"comparison": f"{choice} is stronger.", "preference": choice} for name in CraftComparison.model_fields}
        return ModelResponse(parts=[TextPart(content=json.dumps(output))])

    return FunctionModel(respond)


def _write_scenarios(root: Path) -> tuple[Path, Path]:
    scenarios_dir, seeds_dir = root / "scenarios", root / "seeds"
    scenarios_dir.mkdir(parents=True)
    (seeds_dir / "harbor").mkdir(parents=True)
    (seeds_dir / "harbor" / "script.md").write_text("The harbor was quiet.", encoding="utf-8")
    (scenarios_dir / "fresh.yaml").write_text(
        "description: Start from nothing.\nturns:\n  - prompt: Write me a story.\n    writes: true\n    updates_lore: [plan.md]\n  - prompt: Keep going.\n    writes: true\n",
        encoding="utf-8",
    )
    (scenarios_dir / "harbor.yaml").write_text("description: Continue the harbor.\nseed: harbor\nturns:\n  - prompt: Continue.\n", encoding="utf-8")
    return scenarios_dir, seeds_dir


# Scenarios


def test_scenarios_load_with_their_names_and_seeds(tmp_path) -> None:
    scenarios_dir, seeds_dir = _write_scenarios(tmp_path)

    scenarios = load_scenarios(scenarios_dir, seeds_dir)

    assert [scenario.name for scenario in scenarios] == ["fresh", "harbor"]
    assert scenarios[0].turns[0] == ScenarioTurn(prompt="Write me a story.", writes=True, updates_lore=("plan.md",))
    assert scenarios[1].seed == "harbor"
    assert [scenario.name for scenario in load_scenarios(scenarios_dir, seeds_dir, ["harbor"])] == ["harbor"]


def test_scenario_loading_reports_unknown_names_and_missing_seeds(tmp_path) -> None:
    scenarios_dir, seeds_dir = _write_scenarios(tmp_path)
    (scenarios_dir / "broken.yaml").write_text("description: Missing seed.\nseed: nowhere\nturns:\n  - prompt: Go.\n", encoding="utf-8")

    with pytest.raises(ScenarioError, match="Unknown scenario"):
        load_scenarios(scenarios_dir, seeds_dir, ["absent"])
    with pytest.raises(ScenarioError, match="missing seed"):
        load_scenarios(scenarios_dir, seeds_dir, ["broken"])


def test_invalid_scenario_files_are_reported(tmp_path) -> None:
    scenarios_dir, seeds_dir = _write_scenarios(tmp_path)
    (scenarios_dir / "empty.yaml").write_text("description: No turns.\nturns: []\n", encoding="utf-8")

    with pytest.raises(ScenarioError, match="Invalid scenario"):
        load_scenarios(scenarios_dir, seeds_dir, ["empty"])


def test_repository_scenarios_are_valid() -> None:
    scenarios = load_scenarios(REPO_EVALS / "scenarios", REPO_EVALS / "seeds")

    assert scenarios
    assert all(scenario.description.strip() for scenario in scenarios)


# Prose diagnostics


def test_slop_index_counts_listed_words_and_phrases_per_thousand_words() -> None:
    clean = checks.slop_index("The kettle boiled. She poured two cups and sat down by the window.")
    sloppy = checks.slop_index("She couldn't help but feel a sense of dread. Her voice was barely above a whisper.")

    assert clean.value < sloppy.value
    assert "voice barely" in sloppy.detail


def test_stock_vocabulary_counts_the_words_llm_stories_converge_on() -> None:
    finding = checks.stock_vocabulary("Elias kept the lighthouse. The lighthouse keeper's name was Elias.")

    assert finding.value == 5
    assert "lighthouse ×2" in finding.detail


def test_not_x_but_y_constructions_are_quoted() -> None:
    finding = checks.not_x_but_y("It was not the cold that woke her but the silence.")

    assert finding.value > 0
    assert "not the cold that woke her but" in finding.detail


def test_short_paragraph_rate_ignores_dialogue() -> None:
    finding = checks.short_paragraph_rate('He waited.\n\n"No."\n\nThe rain went on all night against the shed roof.')

    assert finding.detail == "He waited."


def test_self_repetition_finds_phrases_reused_across_turns() -> None:
    turns = (_turn(script_after="The wind came hard off the sea again."), _turn(script_before="x", script_after="x\n\nThe wind came hard off the sea and she ran."))

    finding = checks.self_repetition(turns)

    assert finding.value > 0
    assert "the wind came hard off" in finding.detail


# Habit checks


def test_writing_expectations_are_checked_per_turn() -> None:
    expected = (ScenarioTurn(prompt="Write.", writes=True), ScenarioTurn(prompt="Just talk.", writes=False))
    run = _run(_turn(), _turn(script_before="Scene.", script_after="Scene. More."), expected=expected)

    check = checks.writes_when_expected(run)

    assert not check.passed
    assert check.detail == "turn 2: script.md changed"


def test_expected_lore_updates_are_checked() -> None:
    expected = (ScenarioTurn(prompt="Feedback.", updates_lore=("style.md",)),)

    assert not checks.updates_expected_lore(_run(_turn(), expected=expected)).passed
    assert checks.updates_expected_lore(_run(_turn(lore_after={"style.md": "Plain."}), expected=expected)).passed


def test_a_plan_is_required_once_prose_is_written() -> None:
    assert checks.keeps_a_plan(_run(_turn())).passed
    assert not checks.keeps_a_plan(_run(_turn(lore_after={}))).passed
    assert checks.keeps_a_plan(_run(_turn(script_after="", lore_after={}))).passed


def test_replies_may_reason_at_length_but_not_repeat_story_prose() -> None:
    prose = "The door swung open and the cold came in like a held breath released at last."
    copied = _run(_turn(script_after=prose, reply=f"Here it is: {prose}"))
    reasoning = _run(_turn(reply="word " * 300))

    assert "reply repeats prose" in checks.replies_leave_prose_in_the_story(copied).detail
    assert not checks.replies_leave_prose_in_the_story(copied).passed
    assert checks.replies_leave_prose_in_the_story(reasoning).passed


def test_edits_that_resend_unchanged_text_are_flagged() -> None:
    padding = "x" * 400
    wasteful = ToolCallRecord(name="edit_script", arguments=json.dumps({"find": f"{padding} old", "replace": f"{padding} new"}))
    minimal = ToolCallRecord(name="edit_script", arguments=json.dumps({"find": "old", "replace": "new"}))

    assert not checks.edits_send_only_changes(_run(_turn(tool_calls=(wasteful,)))).passed
    assert checks.edits_send_only_changes(_run(_turn(tool_calls=(minimal,)))).passed


# Runner


@pytest.mark.asyncio
async def test_runner_records_each_turn_in_a_fresh_story(tmp_path) -> None:
    scenarios_dir, seeds_dir = _write_scenarios(tmp_path)
    scenario = load_scenarios(scenarios_dir, seeds_dir, ["fresh"])[0]

    runner = ScenarioRunner(create_writer_agent(), model=_writer_model(), seeds_dir=seeds_dir)
    turns = await runner.run(scenario, tmp_path / "out" / "fresh-1")

    assert [turn.prompt for turn in turns] == ["Write me a story.", "Keep going."]
    assert turns[0].changed_lore == ("plan.md",)
    assert [call.name for call in turns[0].tool_calls] == ["write_lore", "append_to_script"]
    assert "turn 2" in turns[1].new_prose and "turn 1" not in turns[1].new_prose
    assert turns[1].reply == "Added a scene."
    assert (tmp_path / "out" / "fresh-1" / ".storyline-history.json").is_file()


@pytest.mark.asyncio
async def test_runner_starts_from_a_copy_of_the_seed(tmp_path) -> None:
    scenarios_dir, seeds_dir = _write_scenarios(tmp_path)
    scenario = load_scenarios(scenarios_dir, seeds_dir, ["harbor"])[0]

    turns = await ScenarioRunner(create_writer_agent(), model=_writer_model(), seeds_dir=seeds_dir).run(scenario, tmp_path / "out" / "harbor-1")

    assert turns[0].script_before == "The harbor was quiet."
    assert (seeds_dir / "harbor" / "script.md").read_text(encoding="utf-8") == "The harbor was quiet."


# Judges


@pytest.mark.asyncio
async def test_behaviour_judge_returns_a_verdict_with_evidence_per_criterion() -> None:
    review = await BehaviourJudge(_structured_model(_behaviour_output("partly"))).review(_run(_turn()))

    assert review.keeps_canon.verdict == "partly"
    assert review.keeps_canon.evidence == "Turn 1 shows keeps_canon."


def test_session_transcript_shows_turns_changes_and_final_lore() -> None:
    expected = (ScenarioTurn(prompt="Continue."),)
    scenario = Scenario(name="case", description="A case.", turns=expected, judge_notes="Watch the radio.")
    run = ScenarioRun(case_name="case-1", scenario=scenario, model_name="m", prompt_version="v", turns=(_turn(),))

    transcript = session_transcript(run)

    assert "Watch the radio." in transcript
    assert "<lore-changed>plan.md</lore-changed>" in transcript
    assert "New scene." in transcript
    assert '<file name="plan.md">' in transcript


@pytest.mark.asyncio
async def test_craft_judge_reports_a_winner_when_both_orders_agree() -> None:
    run_a = _run(_turn(script_after="An alpha story."), name="case-1")
    run_b = _run(_turn(script_after="A beta story!!"), name="case-1")

    result = await CraftJudge(_craft_model(prefers="alpha")).compare(run_a, run_b)

    assert {outcome.outcome for outcome in result.dimensions.values()} == {"A"}
    assert result.dimensions["plot"].b_first.preference == "A"


@pytest.mark.asyncio
async def test_craft_judge_reports_a_split_when_the_orders_disagree() -> None:
    run_a, run_b = _run(_turn(script_after="An alpha story.")), _run(_turn(script_after="A beta story!!"))

    result = await CraftJudge(_craft_model(prefers=None)).compare(run_a, run_b)

    assert {outcome.outcome for outcome in result.dimensions.values()} == {"split"}


def test_compared_stories_are_cut_to_the_same_length_at_paragraph_boundaries() -> None:
    first, second = equal_length("One.\n\nTwo.\n\nThree.", "Short.", limit=1000)

    assert first == "One."
    assert second == "Short."


# Service


@pytest.mark.asyncio
async def test_eval_run_saves_runs_checks_and_judgements(tmp_path) -> None:
    scenarios_dir, seeds_dir = _write_scenarios(tmp_path)
    out_dir = tmp_path / "runs" / "baseline"
    request = RunRequest(scenario_names=(), model_name="test-writer", instructions="Write well.", out_dir=out_dir, judge_model_name="test-judge", repeat=2, show_progress=False)

    summary = await EvalService(scenarios_dir=scenarios_dir, seeds_dir=seeds_dir).run(request, writer_model=_writer_model(), judge_model=_structured_model(_behaviour_output()))

    text = summary.read_text(encoding="utf-8")
    assert sorted(path.name for path in out_dir.glob("*.run.json")) == ["fresh-1.run.json", "fresh-2.run.json", "harbor-1.run.json", "harbor-2.run.json"]
    assert (out_dir / "instructions.md").read_text(encoding="utf-8") == "Write well."
    assert "| writes_when_expected | 4/4 |" in text
    assert "| follows_direction | 4 | 0 | 0 | 0 |" in text
    assert "stock_words: 2.0 — keeper ×2" in text
    assert await FileWorkspace(out_dir).list_stories() == ("fresh-1", "fresh-2", "harbor-1", "harbor-2")


@pytest.mark.asyncio
async def test_eval_run_refuses_a_used_output_directory(tmp_path) -> None:
    scenarios_dir, seeds_dir = _write_scenarios(tmp_path)
    out_dir = tmp_path / "runs" / "used"
    out_dir.mkdir(parents=True)
    (out_dir / "summary.md").write_text("old", encoding="utf-8")
    request = RunRequest(scenario_names=(), model_name="m", instructions="i", out_dir=out_dir, show_progress=False)

    with pytest.raises(EvalError, match="not empty"):
        await EvalService(scenarios_dir=scenarios_dir, seeds_dir=seeds_dir).run(request, writer_model=_writer_model(), judge_model=None)


@pytest.mark.asyncio
async def test_eval_compare_tallies_outcomes_per_dimension(tmp_path) -> None:
    scenarios_dir, seeds_dir = _write_scenarios(tmp_path)
    service = EvalService(scenarios_dir=scenarios_dir, seeds_dir=seeds_dir)
    for name in ("a", "b"):
        request = RunRequest(scenario_names=("fresh",), model_name="m", instructions=f"Prompt {name}.", out_dir=tmp_path / name, show_progress=False)
        await service.run(request, writer_model=_writer_model(), judge_model=None)

    summary = await service.compare(tmp_path / "a", tmp_path / "b", judge_model=_craft_model(prefers=None), out_file=tmp_path / "compare.md")

    text = summary.read_text(encoding="utf-8")
    assert "| plot | 0 | 0 | 0 | 1 | 0 | 0 |" in text
    assert "## fresh-1" in text


@pytest.mark.asyncio
async def test_eval_compare_needs_shared_cases(tmp_path) -> None:
    scenarios_dir, seeds_dir = _write_scenarios(tmp_path)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()

    with pytest.raises(EvalError, match="no cases in common"):
        await EvalService(scenarios_dir=scenarios_dir, seeds_dir=seeds_dir).compare(tmp_path / "a", tmp_path / "b", judge_model=_craft_model(prefers=None), out_file=tmp_path / "c.md")


# Story presets


def _roleplay_output(verdict: str = "yes") -> dict[str, object]:
    return {name: {"evidence": f"Turn 1 shows {name}.", "verdict": verdict} for name in RoleplayReview.model_fields}


def _table_scenario(scenarios_dir: Path) -> None:
    (scenarios_dir / "table.yaml").write_text("description: A table.\npreset: roleplay\nturns:\n  - prompt: Hello.\n", encoding="utf-8")


def test_scenario_preset_loads_for_seedless_scenarios_only(tmp_path) -> None:
    scenarios_dir, seeds_dir = _write_scenarios(tmp_path)
    _table_scenario(scenarios_dir)
    (scenarios_dir / "odd.yaml").write_text("description: Odd.\npreset: nonesuch\nturns:\n  - prompt: Hello.\n", encoding="utf-8")
    (scenarios_dir / "both.yaml").write_text("description: Both.\nseed: harbor\npreset: roleplay\nturns:\n  - prompt: Hello.\n", encoding="utf-8")

    assert load_scenarios(scenarios_dir, seeds_dir, ["table"])[0].preset == "roleplay"
    assert load_scenarios(scenarios_dir, seeds_dir, ["harbor"])[0].preset is None
    with pytest.raises(ScenarioError, match="odd"):
        load_scenarios(scenarios_dir, seeds_dir, ["odd"])
    with pytest.raises(ScenarioError, match="both"):
        load_scenarios(scenarios_dir, seeds_dir, ["both"])


def test_repository_roleplay_scenarios_name_a_preset_or_a_roleplay_seed() -> None:
    scenarios = {scenario.name: scenario for scenario in load_scenarios(REPO_EVALS / "scenarios", REPO_EVALS / "seeds")}

    assert scenarios["roleplay-kickoff"].preset == "roleplay"
    assert scenarios["roleplay-kickoff"].seed is None
    assert {scenario.seed for name, scenario in scenarios.items() if name.startswith("roleplay-") and name != "roleplay-kickoff"} == {"quarantine-port"}


@pytest.mark.asyncio
async def test_runner_creates_a_seedless_story_as_the_scenarios_preset(tmp_path) -> None:
    scenarios_dir, seeds_dir = _write_scenarios(tmp_path)
    _table_scenario(scenarios_dir)
    scenario = load_scenarios(scenarios_dir, seeds_dir, ["table"])[0]

    await ScenarioRunner(create_writer_agent(), model=_writer_model(), seeds_dir=seeds_dir).run(scenario, tmp_path / "out" / "table-1")

    setup = await FileStory(tmp_path / "out" / "table-1").read_setup()
    assert setup.preset == "roleplay"
    assert set(BUNDLED_PRESETS.get("roleplay").mechanics) <= set(setup.mechanics)
    assert await story_preset(tmp_path / "out" / "table-1") == "roleplay"


@pytest.mark.asyncio
async def test_runner_records_the_preset_of_a_seed_and_defaults_to_co_writing(tmp_path) -> None:
    scenarios_dir, seeds_dir = _write_scenarios(tmp_path)
    shutil.copytree(REPO_EVALS / "seeds" / "quarantine-port", seeds_dir / "quarantine-port")
    (scenarios_dir / "port.yaml").write_text("description: Port.\nseed: quarantine-port\nturns:\n  - prompt: Continue.\n", encoding="utf-8")
    runner = ScenarioRunner(create_writer_agent(), model=_writer_model(), seeds_dir=seeds_dir)

    await runner.run(load_scenarios(scenarios_dir, seeds_dir, ["port"])[0], tmp_path / "out" / "port-1")
    await runner.run(load_scenarios(scenarios_dir, seeds_dir, ["fresh"])[0], tmp_path / "out" / "fresh-1")

    assert await story_preset(tmp_path / "out" / "port-1") == "roleplay"
    assert await story_preset(tmp_path / "out" / "fresh-1") == "co-writing"


@pytest.mark.asyncio
async def test_eval_run_records_the_preset_on_each_case(tmp_path) -> None:
    scenarios_dir, seeds_dir = _write_scenarios(tmp_path)
    _table_scenario(scenarios_dir)
    request = RunRequest(scenario_names=("table", "fresh"), model_name="w", instructions="Write well.", out_dir=tmp_path / "runs" / "a", show_progress=False)

    await EvalService(scenarios_dir=scenarios_dir, seeds_dir=seeds_dir).run(request, writer_model=_writer_model(), judge_model=None)

    saved = {path.name: ScenarioRun.model_validate_json(path.read_text(encoding="utf-8")) for path in (tmp_path / "runs" / "a").glob("*.run.json")}
    assert saved["table-1.run.json"].preset == "roleplay"
    assert saved["fresh-1.run.json"].preset == "co-writing"


# Sealed content and mechanics use


SEALED_FILE = "---\nsummary: Vera.\nkeywords: vera\n---\nShe sells the patrol times to the guild for one mark a night."


def test_sealed_content_in_a_reply_fails_the_check_with_turn_file_and_words() -> None:
    clean = _turn(lore_after={"sealed/vera.md": SEALED_FILE}, reply="Vera is a character you will meet.")
    leaking = _turn(lore_after={"sealed/vera.md": SEALED_FILE}, reply="Careful: she sells the patrol times to the guild, you know.")

    assert checks.keeps_sealed_content_out_of_replies(_run(clean)).passed
    result = checks.keeps_sealed_content_out_of_replies(_run(clean, leaking))
    assert not result.passed
    assert "turn 2" in result.detail and "sealed/vera.md" in result.detail and "sells the patrol times to the" in result.detail


def test_sealed_header_text_is_not_counted_and_no_sealed_files_passes() -> None:
    header_echo = _turn(lore_after={"sealed/vera.md": SEALED_FILE}, reply="summary vera keywords vera")

    assert checks.keeps_sealed_content_out_of_replies(_run(header_echo)).passed
    result = checks.keeps_sealed_content_out_of_replies(_run(_turn()))
    assert result.passed and "no sealed files" in result.detail


def test_mechanics_use_counts_prose_turns_without_review_and_tool_calls() -> None:
    reviewed = _turn(script_after="Scene.", tool_calls=(ToolCallRecord(name="request_review", arguments="{}"), ToolCallRecord(name="roll", arguments="{}"), ToolCallRecord(name="roll", arguments="{}")))
    unreviewed = _turn(script_before="Scene.", script_after="Scene. More.", tool_calls=(ToolCallRecord(name="tick_clock", arguments="{}"),))
    summary_only = _turn(script_before="Scene. More.", script_after="Scene. More.")
    run = _run(reviewed, unreviewed, summary_only)

    assert checks.prose_turns_without_review(run).value == 1
    assert checks.prose_turns_without_review(run).detail.startswith("1 of 2 prose turns")
    assert checks.tool_call_count(run, "request_review").value == 1
    assert checks.tool_call_count(run, "roll").value == 2
    assert checks.tool_call_count(run, "tick_clock").value == 1
    assert checks.tool_call_count(_run(_turn()), "roll").value == 0


@pytest.mark.asyncio
async def test_mechanics_use_and_sealed_check_appear_in_the_run_summary(tmp_path) -> None:
    scenarios_dir, seeds_dir = _write_scenarios(tmp_path)
    request = RunRequest(scenario_names=("fresh",), model_name="w", instructions="Write well.", out_dir=tmp_path / "runs" / "m", show_progress=False)

    summary = await EvalService(scenarios_dir=scenarios_dir, seeds_dir=seeds_dir).run(request, writer_model=_writer_model(), judge_model=None)

    text = summary.read_text(encoding="utf-8")
    assert "keeps_sealed_content_out_of_replies" in text
    assert "prose_turns_without_review: 2.0 — 2 of 2 prose turns" in text
    assert "review_calls: 0.0" in text


# Roleplay judge


def _capturing_model(output: dict[str, object], seen: list[str]) -> FunctionModel:
    def respond(messages: list[ModelMessage], _: AgentInfo) -> ModelResponse:
        seen.append(str(messages[-1].parts[-1].content))
        return ModelResponse(parts=[TextPart(content=json.dumps(output))])

    return FunctionModel(respond)


@pytest.mark.asyncio
async def test_judge_uses_the_roleplay_criteria_for_roleplay_runs_only() -> None:
    roleplay_run = _run(_turn()).model_copy(update={"preset": "roleplay"})

    roleplay = await BehaviourJudge(_structured_model(_roleplay_output("partly"))).review(roleplay_run)
    co_writing = await BehaviourJudge(_structured_model(_behaviour_output())).review(_run(_turn()))

    assert isinstance(roleplay, RoleplayReview)
    assert roleplay.nobody_folds_without_cause.verdict == "partly"
    assert isinstance(co_writing, BehaviourReview)
    with pytest.raises(ValidationError):
        RoleplayReview.model_validate(_behaviour_output())


def test_roleplay_review_has_the_criteria_the_design_names() -> None:
    assert set(RoleplayReview.model_fields) == {
        "keeps_canon",
        "serves_premise",
        "cast_acts_on_sheets",
        "nobody_folds_without_cause",
        "no_moral_commentary",
        "paces_scenes",
        "hands_back_at_hard_move",
        "respects_persona_autonomy",
        "keeps_secrets_at_table",
        "interviews_before_play",
    }


@pytest.mark.asyncio
async def test_roleplay_judge_sees_sealed_files_marked_and_the_tool_calls() -> None:
    seen: list[str] = []
    calls = (ToolCallRecord(name="roll", arguments='{"question": "Does Thale believe her?", "odds": "unlikely"}'), ToolCallRecord(name="tick_clock", arguments='{"clock_id": "hidden"}'))
    run = _run(_turn(tool_calls=calls, lore_after={"plan.md": PLAN, "sealed/vera.md": SEALED_FILE})).model_copy(update={"preset": "roleplay"})

    await BehaviourJudge(_capturing_model(_roleplay_output(), seen)).review(run)

    assert 'name="sealed/vera.md" sealed="true"' in seen[0]
    assert "<sealed-files>" in seen[0] and "sealed/vera.md" in seen[0].split("</sealed-files>")[0]
    tool_calls = seen[0].split("<tool-calls>")[1].split("</tool-calls>")[0]
    assert "- roll" in tool_calls and "Does Thale believe her?" in tool_calls
    assert "- tick_clock" in tool_calls and "hidden" not in tool_calls


@pytest.mark.asyncio
async def test_roleplay_run_with_a_judge_tallies_roleplay_criteria(tmp_path) -> None:
    scenarios_dir, seeds_dir = _write_scenarios(tmp_path)
    _table_scenario(scenarios_dir)
    request = RunRequest(scenario_names=("table",), model_name="w", instructions="Write well.", out_dir=tmp_path / "runs" / "j", judge_model_name="j", show_progress=False)

    summary = await EvalService(scenarios_dir=scenarios_dir, seeds_dir=seeds_dir).run(request, writer_model=_writer_model(), judge_model=_structured_model(_roleplay_output()))

    assert "| cast_acts_on_sheets | 1 | 0 | 0 | 0 |" in summary.read_text(encoding="utf-8")


# Prompt version


def _preset(**changes: object) -> Preset:
    fields: dict[str, object] = {"id": "alpha", "title": "Alpha", "description": "d", "mechanics": (), "layer": "Layer.", "skills_dir": None, "review_checklist": "Check."}
    return Preset(**{**fields, **changes})  # type: ignore[arg-type]


class _PromptedMechanic(Mechanic):
    id = "prompted"
    description = "d"

    def __init__(self, text: str) -> None:
        self._text = text

    @property
    def prompt(self) -> str:
        return self._text


def test_catalog_prompt_version_changes_with_any_preset_or_mechanic_text() -> None:
    def version(preset: Preset, mechanic_text: str = "Mechanic.", core: str = "Core.") -> str:
        return catalog_prompt_version(core, PresetCatalog(presets={preset.id: preset}), {"prompted": _PromptedMechanic(mechanic_text)})

    base = version(_preset())

    assert version(_preset()) == base
    assert version(_preset(layer="Another layer.")) != base
    assert version(_preset(review_checklist="Another check.")) != base
    assert version(_preset(), mechanic_text="Another mechanic.") != base
    assert version(_preset(), core="Another core.") != base


def test_catalog_prompt_version_covers_preset_skills(tmp_path) -> None:
    skill = tmp_path / "skills" / "scene"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("One.", encoding="utf-8")
    catalog = PresetCatalog(presets={"alpha": _preset(skills_dir=tmp_path / "skills")})
    before = catalog_prompt_version("Core.", catalog, {})

    (skill / "SKILL.md").write_text("Two.", encoding="utf-8")

    assert catalog_prompt_version("Core.", catalog, {}) != before


def test_bundled_catalog_version_is_stable_and_differs_from_the_default_preset_alone() -> None:
    version = catalog_prompt_version(WRITER_INSTRUCTIONS, BUNDLED_PRESETS, MECHANICS)

    assert version == catalog_prompt_version(WRITER_INSTRUCTIONS, BUNDLED_PRESETS, MECHANICS)
    assert version != writer_prompt_version(WRITER_INSTRUCTIONS, BUNDLED_PRESETS.get("co-writing"))
