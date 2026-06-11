"""Mechanics patch application: the LLM emits only the delta; the Script is assembled in code."""

import pytest

from src.models.vn import CheckBeat, ChoiceBeat, PlainBeat, Scene, Script
from src.models.vn.pipeline import BeatEffectsPatch, MechanicsPatch, OptionGuardPatch, SceneOutlineItem, ScriptOutline
from src.vn.pipeline.parsing import VNParseError
from src.vn.pipeline.patching import apply_mechanics_patch
from tests.vn.test_pipeline import make_mechanics_patch


@pytest.fixture
def outline() -> ScriptOutline:
    return ScriptOutline(
        title="The Locked Granary",
        start_scene="sc_gate",
        scenes=[
            SceneOutlineItem(id="sc_gate", intent="x", synopsis="s", exit_mode="open"),
            SceneOutlineItem(id="sc_granary", intent="x", synopsis="s", exit_mode="directed"),
            SceneOutlineItem(id="sc_reckoning", intent="x", synopsis="s", exit_mode="ending", ending_ids=["end_bargain", "end_flight"]),
        ],
    )


def _strip_mechanics(scene: Scene) -> Scene:
    """A drafted scene as stage B would produce it: structure only, no state wiring."""
    beats = []
    for beat in scene.beats:
        updates: dict[str, object] = {"effects": []}
        if isinstance(beat, ChoiceBeat):
            updates["options"] = [option.model_copy(update={"guard": []}) for option in beat.options]
        if isinstance(beat, PlainBeat) and beat.exit_edges is not None:
            updates["exit_edges"] = [edge.model_copy(update={"guard": []}) for edge in beat.exit_edges]
        if isinstance(beat, CheckBeat):
            updates["check"] = beat.check.model_copy(update={"modifiers": []})
        beats.append(beat.model_copy(update=updates))
    return scene.model_copy(update={"prerequisites": [], "repeatable": False, "forced": None, "beats": beats})


class TestApplyMechanicsPatch:
    def test_patch_over_stripped_draft_reproduces_the_full_script(self, locked_granary: Script, outline):
        """Every mechanics feature (effects, option guards, exit-edge guards, prerequisites,
        forced, check modifiers, state vars) round-trips through the patch."""
        drafted = [_strip_mechanics(scene) for scene in locked_granary.scenes]
        patch = make_mechanics_patch(locked_granary)

        script = apply_mechanics_patch(outline, drafted, "Mara", patch)

        assert script == locked_granary

    def test_patch_only_touches_what_it_names(self, locked_granary: Script, outline):
        drafted = [_strip_mechanics(scene) for scene in locked_granary.scenes]
        patch = MechanicsPatch(state_vars=[])

        script = apply_mechanics_patch(outline, drafted, "Mara", patch)

        assert script.scenes == drafted
        assert script.state_vars == []
        assert script.meta.title == "The Locked Granary"
        assert script.meta.protagonist == "Mara"
        assert script.start_scene == "sc_gate"

    def test_unknown_beat_reference_is_reported_not_applied(self, locked_granary: Script, outline):
        drafted = [_strip_mechanics(scene) for scene in locked_granary.scenes]
        patch = MechanicsPatch(state_vars=[], beat_effects=[BeatEffectsPatch(beat_id="b_ghost", effects=[])])

        with pytest.raises(VNParseError) as exc_info:
            apply_mechanics_patch(outline, drafted, "Mara", patch)

        issues = exc_info.value.report.issues
        assert [issue.code for issue in issues] == ["patch_application_error"]
        assert issues[0].beat_id == "b_ghost"

    def test_option_index_out_of_range_is_reported(self, locked_granary: Script, outline):
        drafted = [_strip_mechanics(scene) for scene in locked_granary.scenes]
        choice_beat = next(beat for scene in drafted for beat in scene.beats if isinstance(beat, ChoiceBeat))
        patch = MechanicsPatch(state_vars=[], option_guards=[OptionGuardPatch(beat_id=choice_beat.id, option_index=99, guard=[])])

        with pytest.raises(VNParseError) as exc_info:
            apply_mechanics_patch(outline, drafted, "Mara", patch)

        assert "patch_application_error" in {issue.code for issue in exc_info.value.report.issues}
