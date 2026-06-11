"""Anthropic-friendly VN request models and conversion layers."""

import pytest
from pydantic import BaseModel

from src.models.vn.judge import LLMLensReview
from src.models.vn.pipeline import (
    LLMBeatEffectsPatch,
    LLMCheckModifiersPatch,
    LLMMechanicsPatch,
    LLMOptionGuardPatch,
    LLMScenePatch,
)
from src.models.vn.script import LLMBeat, LLMChoiceOption, LLMScene
from src.vn.pipeline.mechanics_dsl import llm_mechanics_patch_to_patch
from src.vn.pipeline.parsing import VNParseError
from src.vn.pipeline.scene_graph_conversion import llm_scene_to_draft_scene


class TestSchemaBudget:
    @pytest.mark.parametrize("model", [LLMScene, LLMMechanicsPatch, LLMLensReview])
    def test_request_models_have_no_unions_or_optional_fields(self, model: type[BaseModel]):
        stats = _schema_stats(model)
        assert stats["anyOf"] == 0
        assert stats["oneOf"] == 0
        assert stats["optional"] == 0


class TestSceneGraphConversion:
    def test_flat_scene_converts_to_draft_scene(self):
        scene = LLMScene(
            id="sc_gate",
            intent="Open the gate",
            entry_beat="b_start",
            beats=[
                LLMBeat(
                    id="b_start",
                    type="plain",
                    intent="Approach",
                    extension_domain="the guard's suspicious posture",
                    route="next:b_choose",
                    check_difficulty=0,
                    check_success="",
                    check_failure="",
                    options=[],
                    ending_id="",
                ),
                LLMBeat(
                    id="b_choose",
                    type="choice",
                    intent="Choose an approach",
                    extension_domain="",
                    route="",
                    check_difficulty=0,
                    check_success="",
                    check_failure="",
                    options=[LLMChoiceOption(intent="Talk", target="b_check")],
                    ending_id="",
                ),
                LLMBeat(
                    id="b_check",
                    type="check",
                    intent="Risk persuasion",
                    extension_domain="",
                    route="",
                    check_difficulty=12,
                    check_success="b_exit",
                    check_failure="b_recover",
                    options=[],
                    ending_id="",
                ),
                LLMBeat(
                    id="b_recover",
                    type="plain",
                    intent="Recover awkwardly",
                    extension_domain="",
                    route="next:b_exit",
                    check_difficulty=0,
                    check_success="",
                    check_failure="",
                    options=[],
                    ending_id="",
                ),
                LLMBeat(
                    id="b_exit",
                    type="plain",
                    intent="Leave",
                    extension_domain="",
                    route="edges:sc_next@2|sc_secret@1",
                    check_difficulty=0,
                    check_success="",
                    check_failure="",
                    options=[],
                    ending_id="",
                ),
            ],
        )

        draft = llm_scene_to_draft_scene(scene)

        assert draft.id == "sc_gate"
        assert draft.beats[0].extension is not None
        assert draft.beats[-1].exit_edges is not None
        assert [edge.target_scene for edge in draft.beats[-1].exit_edges] == ["sc_next", "sc_secret"]

    def test_same_target_check_raises_parse_error(self):
        scene = LLMScene(
            id="sc_gate",
            intent="Open the gate",
            entry_beat="b_check",
            beats=[
                LLMBeat(
                    id="b_check",
                    type="check",
                    intent="Risk persuasion",
                    extension_domain="",
                    route="",
                    check_difficulty=12,
                    check_success="b_exit",
                    check_failure="b_exit",
                    options=[],
                    ending_id="",
                ),
                LLMBeat(
                    id="b_exit",
                    type="plain",
                    intent="Leave",
                    extension_domain="",
                    route="exit:open",
                    check_difficulty=0,
                    check_success="",
                    check_failure="",
                    options=[],
                    ending_id="",
                ),
            ],
        )

        with pytest.raises(VNParseError) as exc_info:
            llm_scene_to_draft_scene(scene)

        assert "output_parse_error" in {issue.code for issue in exc_info.value.report.errors}

    def test_duplicate_choice_targets_raise_parse_error(self):
        scene = LLMScene(
            id="sc_gate",
            intent="Open the gate",
            entry_beat="b_choice",
            beats=[
                LLMBeat(
                    id="b_choice",
                    type="choice",
                    intent="Choose how to answer",
                    extension_domain="",
                    route="",
                    check_difficulty=0,
                    check_success="",
                    check_failure="",
                    options=[LLMChoiceOption(intent="Tell the truth", target="b_exit"), LLMChoiceOption(intent="Deflect", target="b_exit")],
                    ending_id="",
                ),
                LLMBeat(
                    id="b_exit",
                    type="plain",
                    intent="Leave",
                    extension_domain="",
                    route="exit:open",
                    check_difficulty=0,
                    check_success="",
                    check_failure="",
                    options=[],
                    ending_id="",
                ),
            ],
        )

        with pytest.raises(VNParseError) as exc_info:
            llm_scene_to_draft_scene(scene)

        assert "output_parse_error" in {issue.code for issue in exc_info.value.report.errors}

    def test_invalid_plain_route_raises_parse_error(self):
        scene = LLMScene(
            id="sc_gate",
            intent="Open the gate",
            entry_beat="b_start",
            beats=[
                LLMBeat(
                    id="b_start",
                    type="plain",
                    intent="Approach",
                    extension_domain="",
                    route="",
                    check_difficulty=0,
                    check_success="",
                    check_failure="",
                    options=[],
                    ending_id="",
                )
            ],
        )

        with pytest.raises(VNParseError) as exc_info:
            llm_scene_to_draft_scene(scene)

        assert "output_parse_error" in {issue.code for issue in exc_info.value.report.errors}


class TestMechanicsDsl:
    def test_dsl_patch_converts_to_canonical_patch(self):
        patch = LLMMechanicsPatch(
            state_vars=["flag has_key=false", "counter trust max=3 initial=1", "enum lamp values=amber|white initial=amber"],
            beat_effects=[LLMBeatEffectsPatch(beat_id="b_take_key", effects=["has_key = true", "trust += 1", "lamp = white"])],
            option_guards=[LLMOptionGuardPatch(beat_id="b_choice", option_index=1, guard=["has_key == true", "trust >= 2"])],
            exit_edge_guards=[],
            scene_patches=[LLMScenePatch(scene_id="sc_secret", prerequisites=["visited:b_take_key"], repeatable=False, forced=-1)],
            check_modifiers=[LLMCheckModifiersPatch(beat_id="b_check", modifiers=["trust >= 2 => +2", "not visited:b_alarm => -1"])],
        )

        canonical = llm_mechanics_patch_to_patch(patch)

        assert [var.name for var in canonical.state_vars] == ["has_key", "trust", "lamp"]
        assert canonical.beat_effects[0].effects[1].op == "inc"
        assert canonical.option_guards[0].guard[1].value == 2
        assert canonical.scene_patches[0].prerequisites[0].visited == "b_take_key"
        assert canonical.check_modifiers[0].modifiers[0].mod == 2

    def test_invalid_dsl_raises_parse_error(self):
        patch = LLMMechanicsPatch(
            state_vars=["counter trust initial=1"],
            beat_effects=[],
            option_guards=[],
            exit_edge_guards=[],
            scene_patches=[],
            check_modifiers=[],
        )

        with pytest.raises(VNParseError) as exc_info:
            llm_mechanics_patch_to_patch(patch)

        assert "output_parse_error" in {issue.code for issue in exc_info.value.report.errors}

    @pytest.mark.parametrize("guard", ["has_key", "not has_key"])
    def test_bare_flag_guards_raise_parse_error(self, guard: str):
        patch = LLMMechanicsPatch(
            state_vars=["flag has_key=false"],
            beat_effects=[],
            option_guards=[LLMOptionGuardPatch(beat_id="b_choice", option_index=0, guard=[guard])],
            exit_edge_guards=[],
            scene_patches=[],
            check_modifiers=[],
        )

        with pytest.raises(VNParseError) as exc_info:
            llm_mechanics_patch_to_patch(patch)

        assert "output_parse_error" in {issue.code for issue in exc_info.value.report.errors}


def _schema_stats(model: type[BaseModel]) -> dict[str, int]:
    schema = model.model_json_schema()
    dicts = list(_walk_dicts(schema))
    objects = [item for item in dicts if item.get("type") == "object" or "properties" in item]
    optional = 0
    for item in objects:
        required = set(item.get("required", []))
        optional += sum(name not in required for name in item.get("properties", {}))
    return {
        "optional": optional,
        "anyOf": sum(1 for item in dicts if "anyOf" in item),
        "oneOf": sum(1 for item in dicts if "oneOf" in item),
    }


def _walk_dicts(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)
