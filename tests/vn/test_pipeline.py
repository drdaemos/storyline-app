"""M6: generation pipeline — stage gates, bounded repair, end-to-end with mocked LLM."""

import pytest
from pydantic import BaseModel

from src.models.prompt_processor import PromptProcessor
from src.models.vn import CheckBeat, ChoiceBeat, PlainBeat, Scene, Script, VNInput
from src.models.vn.pipeline import (
    BeatEffectsPatch,
    CheckModifiersPatch,
    ExitEdgeGuardPatch,
    GenerationCheckpoint,
    MechanicsPatch,
    OptionGuardPatch,
    SceneOutlineItem,
    ScenePatch,
    ScriptOutline,
)
from src.models.vn.validation import ValidationIssue, ValidationReport
from src.vn.pipeline.generator import VNScriptGenerator
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
        processor = FakeProcessor([outline, *locked_granary.scenes, make_mechanics_patch(locked_granary)])
        progress = []
        script = VNScriptGenerator(processor).generate(vn_input, on_progress=progress.append)

        assert script == locked_granary
        assert processor.calls == [ScriptOutline, Scene, Scene, Scene, MechanicsPatch]
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
        processor = FakeProcessor([outline, *locked_granary.scenes, make_mechanics_patch(locked_granary)])
        checkpoints: list[GenerationCheckpoint] = []
        VNScriptGenerator(processor).generate(vn_input, on_checkpoint=checkpoints.append)

        assert len(checkpoints) == 1 + len(locked_granary.scenes)  # outline, then one per scene
        assert checkpoints[0].outline == outline
        assert checkpoints[0].scenes == []
        assert [scene.id for scene in checkpoints[-1].scenes] == [scene.id for scene in locked_granary.scenes]

    def test_resume_skips_checkpointed_work(self, vn_input, outline, locked_granary: Script):
        checkpoint = GenerationCheckpoint(outline=outline, scenes=[locked_granary.scenes[0]])
        processor = FakeProcessor([*locked_granary.scenes[1:], make_mechanics_patch(locked_granary)])  # neither outline nor the first scene are requested again
        progress = []
        script = VNScriptGenerator(processor).generate(vn_input, on_progress=progress.append, checkpoint=checkpoint)

        assert script == locked_granary
        assert processor.calls == [Scene, Scene, MechanicsPatch]
        started_scenes = [p.scene_id for p in progress if p.stage == "scene_graph" and p.status == "started"]
        assert started_scenes == ["sc_granary", "sc_reckoning"]
        assert not any(p.stage == "outline" and p.status == "started" for p in progress)

    def test_unparseable_output_is_repaired(self, vn_input, outline, locked_granary: Script):
        """A response the SDK cannot parse counts as a failed attempt with parse feedback."""
        processor = FakeProcessor(["Sure! Here is your outline: it has three scenes.", outline, *locked_granary.scenes, make_mechanics_patch(locked_granary)])
        progress = []
        script = VNScriptGenerator(processor).generate(vn_input, on_progress=progress.append)

        assert script == locked_granary
        repairing = [p for p in progress if p.status == "repairing"]
        assert len(repairing) == 1
        assert repairing[0].stage == "outline"
        assert "output_parse_error" in repairing[0].detail

    def test_mechanics_repair_then_success(self, vn_input, outline, locked_granary: Script):
        good = make_mechanics_patch(locked_granary)
        broken = good.model_copy(update={"state_vars": []})  # guards now reference undeclared vars
        processor = FakeProcessor([outline, *locked_granary.scenes, broken, good])
        progress = []
        script = VNScriptGenerator(processor).generate(vn_input, on_progress=progress.append)

        assert script == locked_granary
        repairing = [p for p in progress if p.status == "repairing"]
        assert len(repairing) == 1
        assert repairing[0].stage == "mechanics"
        assert "unknown_var_ref" in repairing[0].detail

    def test_persistent_failure_raises(self, vn_input, outline, locked_granary: Script):
        broken = make_mechanics_patch(locked_granary).model_copy(update={"state_vars": []})
        processor = FakeProcessor([outline, *locked_granary.scenes, broken, broken, broken])
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
        patch = make_mechanics_patch(softlocked)
        processor = FakeProcessor([outline, *softlocked.scenes, patch, patch, patch])
        with pytest.raises(VNGenerationError) as exc_info:
            VNScriptGenerator(processor).generate(vn_input)
        assert "dead_end" in {issue.code for issue in exc_info.value.report.errors}
