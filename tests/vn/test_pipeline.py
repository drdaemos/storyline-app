"""M6: generation pipeline — stage gates, bounded repair, end-to-end with mocked LLM."""

import pytest
from pydantic import BaseModel

from src.models.prompt_processor import PromptProcessor
from src.models.vn import CheckBeat, ChoiceBeat, EndingBeat, FlagVar, PlainBeat, Scene, Script, StateVar, VNInput
from src.models.vn.pipeline import (
    BeatEffectsPatch,
    CheckModifiersPatch,
    ExitEdgeGuardPatch,
    GenerationCheckpoint,
    LLMBeatEffectsPatch,
    LLMCheckModifiersPatch,
    LLMExitEdgeGuardPatch,
    LLMMechanicsPatch,
    LLMOptionGuardPatch,
    LLMScenePatch,
    MechanicsPatch,
    OptionGuardPatch,
    SceneOutlineItem,
    ScenePatch,
    ScriptOutline,
)
from src.models.vn.script import CheckModifier, Condition, DraftScene, Effect, LLMBeat, LLMChoiceOption, LLMScene
from src.models.vn.validation import ValidationIssue, ValidationReport
from src.vn.pipeline.generator import VNScriptGenerator
from src.vn.pipeline.mechanics import MechanicsStage
from src.vn.pipeline.outline import OutlineStage
from src.vn.pipeline.repair import VNGenerationError, run_with_repair
from src.vn.pipeline.scene_graphs import SceneGraphStage


class FakeProcessor(PromptProcessor):
    """Returns queued model outputs in order; a queued string simulates an unparseable response. No real LLM involved."""

    def __init__(self, outputs: list[BaseModel | str]) -> None:
        self.outputs = list(outputs)
        self.calls: list[type] = []

    def get_processor_specific_prompt(self) -> str:
        return ""

    def respond_with_stream(self, prompt, user_prompt, conversation_history=None, max_tokens=None, reasoning=False):
        raise NotImplementedError

    def respond_with_text(self, prompt, user_prompt, conversation_history=None, max_tokens=None, reasoning=False):
        raise NotImplementedError

    def respond_with_model(self, prompt, user_prompt, output_type, conversation_history=None, max_tokens=None, reasoning=False):
        self.calls.append(output_type)
        output = self.outputs.pop(0)
        if isinstance(output, str):
            raise ValueError(f"no structured output: {output}")
        assert isinstance(output, output_type), f"test setup error: expected {output_type}, queued {type(output)}"
        return output


def make_mechanics_patch(script: Script) -> MechanicsPatch:
    """Derive the patch that reproduces `script` when applied over its own scenes."""
    patch = MechanicsPatch(state_vars=script.state_vars)
    for scene in script.scenes:
        if scene.prerequisites or scene.repeatable or scene.forced is not None:
            patch.scene_patches.append(ScenePatch(scene_id=scene.id, prerequisites=scene.prerequisites, repeatable=scene.repeatable or None, forced=scene.forced))
        for beat in scene.beats:
            if beat.effects:
                patch.beat_effects.append(BeatEffectsPatch(beat_id=beat.id, effects=beat.effects))
            if isinstance(beat, ChoiceBeat):
                for index, option in enumerate(beat.options):
                    if option.guard:
                        patch.option_guards.append(OptionGuardPatch(beat_id=beat.id, option_index=index, guard=option.guard))
            if isinstance(beat, PlainBeat) and beat.exit_edges is not None:
                for index, edge in enumerate(beat.exit_edges):
                    if edge.guard:
                        patch.exit_edge_guards.append(ExitEdgeGuardPatch(beat_id=beat.id, edge_index=index, guard=edge.guard))
            if isinstance(beat, CheckBeat) and beat.check.modifiers:
                patch.check_modifiers.append(CheckModifiersPatch(beat_id=beat.id, modifiers=beat.check.modifiers))
    return patch


def make_llm_mechanics_patch(script: Script) -> LLMMechanicsPatch:
    """Derive the Anthropic-friendly mechanics DSL patch for `script`."""
    patch = make_mechanics_patch(script)
    return LLMMechanicsPatch(
        state_vars=[_state_var_to_dsl(var) for var in patch.state_vars],
        beat_effects=[
            LLMBeatEffectsPatch(beat_id=item.beat_id, effects=[_effect_to_dsl(effect) for effect in item.effects])
            for item in patch.beat_effects
        ],
        option_guards=[
            LLMOptionGuardPatch(beat_id=item.beat_id, option_index=item.option_index, guard=[_condition_to_dsl(condition) for condition in item.guard])
            for item in patch.option_guards
        ],
        exit_edge_guards=[
            LLMExitEdgeGuardPatch(beat_id=item.beat_id, edge_index=item.edge_index, guard=[_condition_to_dsl(condition) for condition in item.guard])
            for item in patch.exit_edge_guards
        ],
        scene_patches=[
            LLMScenePatch(
                scene_id=item.scene_id,
                prerequisites=[_condition_to_dsl(condition) for condition in item.prerequisites],
                repeatable=bool(item.repeatable),
                forced=-1 if item.forced is None else item.forced,
            )
            for item in patch.scene_patches
        ],
        check_modifiers=[
            LLMCheckModifiersPatch(beat_id=item.beat_id, modifiers=[_modifier_to_dsl(modifier) for modifier in item.modifiers])
            for item in patch.check_modifiers
        ],
    )


def _state_var_to_dsl(var: StateVar) -> str:
    if var.type == "flag":
        return f"flag {var.name}={_value_to_dsl(var.initial)}"
    if var.type == "counter":
        return f"counter {var.name} max={var.max} initial={var.initial}"
    return f"enum {var.name} values={'|'.join(var.values)} initial={var.initial}"


def _effect_to_dsl(effect: Effect) -> str:
    if effect.op == "set":
        return f"{effect.var} = {_value_to_dsl(effect.value)}"
    op = "+=" if effect.op == "inc" else "-="
    return f"{effect.var} {op} {_value_to_dsl(effect.value)}"


def _modifier_to_dsl(modifier: CheckModifier) -> str:
    return f"{_condition_to_dsl(modifier)} => {modifier.mod:+d}"


def _condition_to_dsl(condition: Condition) -> str:
    if condition.is_visited:
        prefix = "not " if condition.value is False else ""
        return f"{prefix}visited:{condition.visited}"
    return f"{condition.var} {condition.op} {_value_to_dsl(condition.value)}"


def _value_to_dsl(value: bool | int | str) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def scene_to_draft(scene: Scene) -> DraftScene:
    """Strip mechanics from a canonical `Scene` to the structure-only `DraftScene`
    the scene-graph stage actually requests from the LLM (the inverse of
    `draft_scene_to_scene`). Mechanics are reapplied later by the mechanics patch."""
    beats: list[dict[str, object]] = []
    for beat in scene.beats:
        common: dict[str, object] = {"id": beat.id, "intent": beat.intent, "type": beat.type, "extension": beat.extension}
        if isinstance(beat, PlainBeat):
            beats.append({**common, "next": beat.next, "exit": beat.exit, "exit_edges": [{"target_scene": edge.target_scene, "priority": edge.priority} for edge in beat.exit_edges] if beat.exit_edges is not None else None})
        elif isinstance(beat, CheckBeat):
            beats.append({**common, "check": {"difficulty": beat.check.difficulty, "on_success": beat.check.on_success, "on_failure": beat.check.on_failure}})
        elif isinstance(beat, ChoiceBeat):
            beats.append({**common, "options": [{"intent": option.intent, "target": option.target} for option in beat.options]})
        else:
            assert isinstance(beat, EndingBeat)
            beats.append({**common, "ending_id": beat.ending_id})
    return DraftScene.model_validate({"id": scene.id, "intent": scene.intent, "entry_beat": scene.entry_beat, "beats": beats})


def scene_to_llm_scene(scene: Scene) -> LLMScene:
    beats: list[LLMBeat] = []
    for beat in scene.beats:
        extension_domain = beat.extension.deeper_domain if beat.extension is not None else ""
        if isinstance(beat, PlainBeat):
            beats.append(
                LLMBeat(
                    id=beat.id,
                    type="plain",
                    intent=beat.intent,
                    extension_domain=extension_domain,
                    route=_plain_route_to_dsl(beat),
                    check_difficulty=0,
                    check_success="",
                    check_failure="",
                    options=[],
                    ending_id="",
                )
            )
        elif isinstance(beat, CheckBeat):
            beats.append(
                LLMBeat(
                    id=beat.id,
                    type="check",
                    intent=beat.intent,
                    extension_domain=extension_domain,
                    route="",
                    check_difficulty=beat.check.difficulty,
                    check_success=beat.check.on_success,
                    check_failure=beat.check.on_failure,
                    options=[],
                    ending_id="",
                )
            )
        elif isinstance(beat, ChoiceBeat):
            beats.append(
                LLMBeat(
                    id=beat.id,
                    type="choice",
                    intent=beat.intent,
                    extension_domain=extension_domain,
                    route="",
                    check_difficulty=0,
                    check_success="",
                    check_failure="",
                    options=[LLMChoiceOption(intent=option.intent, target=option.target) for option in beat.options],
                    ending_id="",
                )
            )
        else:
            assert isinstance(beat, EndingBeat)
            beats.append(
                LLMBeat(
                    id=beat.id,
                    type="ending",
                    intent=beat.intent,
                    extension_domain=extension_domain,
                    route="",
                    check_difficulty=0,
                    check_success="",
                    check_failure="",
                    options=[],
                    ending_id=beat.ending_id,
                )
            )
    return LLMScene(id=scene.id, intent=scene.intent, entry_beat=scene.entry_beat, beats=beats)


def scenes_as_llm_scenes(script: Script) -> list[LLMScene]:
    """The scene-graph stage outputs for `script`, in order."""
    return [scene_to_llm_scene(scene) for scene in script.scenes]


def _plain_route_to_dsl(beat: PlainBeat) -> str:
    if beat.next is not None:
        return f"next:{beat.next}"
    if beat.exit == "open":
        return "exit:open"
    assert beat.exit_edges is not None
    return "edges:" + "|".join(f"{edge.target_scene}@{edge.priority}" for edge in beat.exit_edges)


@pytest.fixture
def vn_input() -> VNInput:
    return VNInput.model_validate(
        {
            "characters": [{"name": "Mara", "background": "a thief", "protagonist": True}],
            "setting": {"world_description": "a small town"},
            "rules": "low fantasy",
            "premise": {
                "synopsis": "steal the ledger from the granary",
                "protagonist_goal": "clear her name",
                "scope": {"target_scenes": 3, "target_endings": 2},
            },
        }
    )


@pytest.fixture
def outline() -> ScriptOutline:
    return ScriptOutline(
        title="The Locked Granary",
        start_scene="sc_gate",
        scenes=[
            SceneOutlineItem(id="sc_gate", intent="Talk your way past the granary guard", synopsis="Mara gets past the guard", exit_mode="open"),
            SceneOutlineItem(id="sc_granary", intent="Search the granary for the ledger", synopsis="Mara searches", exit_mode="directed"),
            SceneOutlineItem(id="sc_reckoning", intent="Face the granary master", synopsis="Confrontation", exit_mode="ending", ending_ids=["end_bargain", "end_flight"]),
        ],
    )


class TestOutlineGate:
    def test_valid_outline_passes(self, outline, vn_input):
        stage = OutlineStage(FakeProcessor([]))
        assert stage.gate(outline, vn_input).valid

    def test_scene_count_differing_from_target_is_allowed(self, outline, vn_input):
        extra = outline.model_copy(update={"scenes": [*outline.scenes, SceneOutlineItem(id="sc_extra", intent="x", synopsis="s", exit_mode="directed")]})
        assert OutlineStage(FakeProcessor([])).gate(extra, vn_input).valid

    def test_ending_count_mismatch(self, outline, vn_input):
        scenes = [scene.model_copy(update={"ending_ids": ["end_bargain"]}) if scene.id == "sc_reckoning" else scene for scene in outline.scenes]
        bad = outline.model_copy(update={"scenes": scenes})
        codes = {issue.code for issue in OutlineStage(FakeProcessor([])).gate(bad, vn_input).errors}
        assert "scope_ending_count_mismatch" in codes

    def test_unknown_start_scene(self, outline, vn_input):
        bad = outline.model_copy(update={"start_scene": "sc_ghost"})
        codes = {issue.code for issue in OutlineStage(FakeProcessor([])).gate(bad, vn_input).errors}
        assert "unknown_start_scene" in codes

    def test_misplaced_ending_ids(self, outline, vn_input):
        scenes = [scene.model_copy(update={"ending_ids": ["end_x"]}) if scene.id == "sc_gate" else scene for scene in outline.scenes]
        bad = outline.model_copy(update={"scenes": scenes})
        codes = {issue.code for issue in OutlineStage(FakeProcessor([])).gate(bad, vn_input).errors}
        assert "misplaced_ending_ids" in codes


class TestSceneGraphGate:
    def test_matching_scene_passes(self, locked_granary: Script, outline):
        scene = locked_granary.scenes[2]  # sc_reckoning with both endings
        report = SceneGraphStage(FakeProcessor([])).gate(scene, outline.scenes[2])
        assert report.valid, [issue.message for issue in report.errors]

    def test_scene_id_mismatch(self, locked_granary: Script, outline):
        report = SceneGraphStage(FakeProcessor([])).gate(locked_granary.scenes[0], outline.scenes[2])
        assert "scene_id_mismatch" in {issue.code for issue in report.errors}

    def test_ending_mismatch(self, locked_granary: Script, outline):
        item = outline.scenes[2].model_copy(update={"ending_ids": ["end_bargain"]})
        report = SceneGraphStage(FakeProcessor([])).gate(locked_granary.scenes[2], item)
        assert "outline_ending_mismatch" in {issue.code for issue in report.errors}

    def test_exit_mode_mismatch(self, locked_granary: Script, outline):
        item = outline.scenes[0].model_copy(update={"exit_mode": "directed"})  # sc_gate actually has an open exit
        report = SceneGraphStage(FakeProcessor([])).gate(locked_granary.scenes[0], item)
        assert "exit_mode_mismatch" in {issue.code for issue in report.errors}


class TestMechanicsGate:
    def test_state_var_written_but_never_read_is_repair_feedback(self, locked_granary: Script, vn_input):
        first_scene = locked_granary.scenes[0]
        first_beat = first_scene.beats[0].model_copy(
            update={"effects": [*first_scene.beats[0].effects, Effect(var="unused_signal", op="set", value=True)]}
        )
        script = locked_granary.model_copy(
            update={
                "state_vars": [*locked_granary.state_vars, FlagVar(name="unused_signal", initial=False)],
                "scenes": [first_scene.model_copy(update={"beats": [first_beat, *first_scene.beats[1:]]}), *locked_granary.scenes[1:]],
            }
        )

        report = MechanicsStage(FakeProcessor([])).gate(script, vn_input)

        assert "state_var_never_read" in {issue.code for issue in report.errors}


class TestRepairLoop:
    def test_feedback_passed_on_retry(self):
        seen_feedback: list[ValidationReport | None] = []
        bad = ValidationReport(issues=[ValidationIssue(code="boom", message="bad")])

        def produce(feedback):
            seen_feedback.append(feedback)
            return len(seen_feedback)

        result = run_with_repair(produce, gate=lambda candidate: ValidationReport() if candidate >= 2 else bad, max_attempts=3)
        assert result == 2
        assert seen_feedback[0] is None
        assert seen_feedback[1] is bad

    def test_raises_after_max_attempts(self):
        bad = ValidationReport(issues=[ValidationIssue(code="boom", message="bad")])
        with pytest.raises(VNGenerationError) as exc_info:
            run_with_repair(lambda feedback: 0, gate=lambda candidate: bad, max_attempts=2)
        assert exc_info.value.report is bad


class TestGeneratorEndToEnd:
    def test_clean_run(self, vn_input, outline, locked_granary: Script):
        processor = FakeProcessor([outline, *scenes_as_llm_scenes(locked_granary), make_llm_mechanics_patch(locked_granary)])
        progress = []
        script = VNScriptGenerator(processor).generate(vn_input, on_progress=progress.append)

        assert script == locked_granary
        assert processor.calls == [ScriptOutline, LLMScene, LLMScene, LLMScene, LLMMechanicsPatch]
        stages = [(p.stage, p.status) for p in progress]
        assert stages == [
            ("outline", "started"),
            ("outline", "passed"),
            ("scene_graph", "started"),
            ("scene_graph", "passed"),
            ("scene_graph", "started"),
            ("scene_graph", "passed"),
            ("scene_graph", "started"),
            ("scene_graph", "passed"),
            ("mechanics", "started"),
            ("mechanics", "passed"),
        ]

    def test_checkpoint_reported_after_each_artifact(self, vn_input, outline, locked_granary: Script):
        processor = FakeProcessor([outline, *scenes_as_llm_scenes(locked_granary), make_llm_mechanics_patch(locked_granary)])
        checkpoints: list[GenerationCheckpoint] = []
        VNScriptGenerator(processor).generate(vn_input, on_checkpoint=checkpoints.append)

        assert len(checkpoints) == 1 + len(locked_granary.scenes)  # outline, then one per scene
        assert checkpoints[0].outline == outline
        assert checkpoints[0].scenes == []
        assert [scene.id for scene in checkpoints[-1].scenes] == [scene.id for scene in locked_granary.scenes]

    def test_resume_skips_checkpointed_work(self, vn_input, outline, locked_granary: Script):
        checkpoint = GenerationCheckpoint(outline=outline, scenes=[locked_granary.scenes[0]])
        processor = FakeProcessor([*scenes_as_llm_scenes(locked_granary)[1:], make_llm_mechanics_patch(locked_granary)])  # neither outline nor the first scene are requested again
        progress = []
        script = VNScriptGenerator(processor).generate(vn_input, on_progress=progress.append, checkpoint=checkpoint)

        assert script == locked_granary
        assert processor.calls == [LLMScene, LLMScene, LLMMechanicsPatch]
        started_scenes = [p.scene_id for p in progress if p.stage == "scene_graph" and p.status == "started"]
        assert started_scenes == ["sc_granary", "sc_reckoning"]
        assert not any(p.stage == "outline" and p.status == "started" for p in progress)

    def test_unparseable_output_is_repaired(self, vn_input, outline, locked_granary: Script):
        """A response the SDK cannot parse counts as a failed attempt with parse feedback."""
        processor = FakeProcessor(["Sure! Here is your outline: it has three scenes.", outline, *scenes_as_llm_scenes(locked_granary), make_llm_mechanics_patch(locked_granary)])
        progress = []
        script = VNScriptGenerator(processor).generate(vn_input, on_progress=progress.append)

        assert script == locked_granary
        repairing = [p for p in progress if p.status == "repairing"]
        assert len(repairing) == 1
        assert repairing[0].stage == "outline"
        assert "output_parse_error" in repairing[0].detail

    def test_mechanics_repair_then_success(self, vn_input, outline, locked_granary: Script):
        good = make_llm_mechanics_patch(locked_granary)
        broken = good.model_copy(update={"state_vars": []})  # guards now reference undeclared vars
        processor = FakeProcessor([outline, *scenes_as_llm_scenes(locked_granary), broken, good])
        progress = []
        script = VNScriptGenerator(processor).generate(vn_input, on_progress=progress.append)

        assert script == locked_granary
        repairing = [p for p in progress if p.status == "repairing"]
        assert len(repairing) == 1
        assert repairing[0].stage == "mechanics"
        assert "unknown_var_ref" in repairing[0].detail

    def test_persistent_failure_raises(self, vn_input, outline, locked_granary: Script):
        broken = make_llm_mechanics_patch(locked_granary).model_copy(update={"state_vars": []})
        processor = FakeProcessor([outline, *scenes_as_llm_scenes(locked_granary), broken, broken, broken])
        with pytest.raises(VNGenerationError) as exc_info:
            VNScriptGenerator(processor).generate(vn_input)
        assert "unknown_var_ref" in {issue.code for issue in exc_info.value.report.errors}

    def test_softlock_caught_by_final_gate(self):
        """A structurally valid script whose open-exit pool can come up empty must be rejected."""
        vn_input = VNInput.model_validate(
            {
                "characters": [{"name": "Mara", "protagonist": True}],
                "premise": {"synopsis": "s", "protagonist_goal": "g", "scope": {"target_scenes": 2, "target_endings": 1}},
            }
        )
        # sc_b requires visited(b_end), which only flips once sc_b is entered: never available.
        softlocked = Script.model_validate(
            {
                "meta": {"title": "T", "protagonist": "Mara"},
                "state_vars": [],
                "start_scene": "sc_a",
                "scenes": [
                    {"id": "sc_a", "intent": "x", "entry_beat": "b1", "beats": [{"id": "b1", "type": "plain", "intent": "x", "exit": "open"}]},
                    {
                        "id": "sc_b",
                        "intent": "x",
                        "prerequisites": [{"visited": "b_end"}],
                        "entry_beat": "b_end",
                        "beats": [{"id": "b_end", "type": "ending", "intent": "x", "ending_id": "end_1"}],
                    },
                ],
            }
        )
        outline = ScriptOutline(
            title="T",
            start_scene="sc_a",
            scenes=[
                SceneOutlineItem(id="sc_a", intent="x", synopsis="s", exit_mode="open"),
                SceneOutlineItem(id="sc_b", intent="x", synopsis="s", exit_mode="ending", ending_ids=["end_1"]),
            ],
        )
        patch = make_llm_mechanics_patch(softlocked)
        processor = FakeProcessor([outline, *scenes_as_llm_scenes(softlocked), patch, patch, patch])
        with pytest.raises(VNGenerationError) as exc_info:
            VNScriptGenerator(processor).generate(vn_input)
        assert "dead_end" in {issue.code for issue in exc_info.value.report.errors}
