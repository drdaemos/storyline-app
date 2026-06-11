"""Apply a MechanicsPatch to the drafted scenes, assembling the final Script in code.

The LLM never re-emits the drafted structure; patches reference existing ids. A patch
that references unknown ids raises VNParseError so the repair loop can feed the exact
problems back, just like a malformed JSON response.
"""

from src.models.vn.pipeline import MechanicsPatch, ScriptOutline
from src.models.vn.script import CheckBeat, ChoiceBeat, PlainBeat, Scene, Script
from src.models.vn.validation import ValidationIssue, ValidationReport
from src.vn.pipeline.parsing import VNParseError


def apply_mechanics_patch(outline: ScriptOutline, scenes: list[Scene], protagonist: str, patch: MechanicsPatch) -> Script:
    issues: list[ValidationIssue] = []
    patched_scenes = {scene.id: scene for scene in scenes}
    beat_locations = {beat.id: scene.id for scene in scenes for beat in scene.beats}

    def replace_beat(beat_id: str, **updates: object) -> None:
        scene = patched_scenes[beat_locations[beat_id]]
        beats = [beat.model_copy(update=updates) if beat.id == beat_id else beat for beat in scene.beats]
        patched_scenes[scene.id] = scene.model_copy(update={"beats": beats})

    def find_beat(beat_id: str, patch_kind: str) -> object | None:
        scene_id = beat_locations.get(beat_id)
        if scene_id is None:
            issues.append(ValidationIssue(code="patch_application_error", beat_id=beat_id, message=f"{patch_kind}: beat '{beat_id}' does not exist in the drafted scenes"))
            return None
        return next(beat for beat in patched_scenes[scene_id].beats if beat.id == beat_id)

    for effects_patch in patch.beat_effects:
        if find_beat(effects_patch.beat_id, "beat_effects") is not None:
            replace_beat(effects_patch.beat_id, effects=effects_patch.effects)

    for option_patch in patch.option_guards:
        beat = find_beat(option_patch.beat_id, "option_guards")
        if beat is None:
            continue
        if not isinstance(beat, ChoiceBeat) or option_patch.option_index >= len(beat.options):
            issues.append(
                ValidationIssue(code="patch_application_error", beat_id=option_patch.beat_id, message=f"option_guards: beat '{option_patch.beat_id}' has no option index {option_patch.option_index}")
            )
            continue
        options = [option.model_copy(update={"guard": option_patch.guard}) if index == option_patch.option_index else option for index, option in enumerate(beat.options)]
        replace_beat(option_patch.beat_id, options=options)

    for edge_patch in patch.exit_edge_guards:
        beat = find_beat(edge_patch.beat_id, "exit_edge_guards")
        if beat is None:
            continue
        if not isinstance(beat, PlainBeat) or beat.exit_edges is None or edge_patch.edge_index >= len(beat.exit_edges):
            issues.append(
                ValidationIssue(code="patch_application_error", beat_id=edge_patch.beat_id, message=f"exit_edge_guards: beat '{edge_patch.beat_id}' has no exit edge index {edge_patch.edge_index}")
            )
            continue
        edges = [edge.model_copy(update={"guard": edge_patch.guard}) if index == edge_patch.edge_index else edge for index, edge in enumerate(beat.exit_edges)]
        replace_beat(edge_patch.beat_id, exit_edges=edges)

    for modifiers_patch in patch.check_modifiers:
        beat = find_beat(modifiers_patch.beat_id, "check_modifiers")
        if beat is None:
            continue
        if not isinstance(beat, CheckBeat):
            issues.append(ValidationIssue(code="patch_application_error", beat_id=modifiers_patch.beat_id, message=f"check_modifiers: beat '{modifiers_patch.beat_id}' is not a check beat"))
            continue
        replace_beat(modifiers_patch.beat_id, check=beat.check.model_copy(update={"modifiers": modifiers_patch.modifiers}))

    for scene_patch in patch.scene_patches:
        scene = patched_scenes.get(scene_patch.scene_id)
        if scene is None:
            issues.append(ValidationIssue(code="patch_application_error", scene_id=scene_patch.scene_id, message=f"scene_patches: scene '{scene_patch.scene_id}' does not exist"))
            continue
        updates: dict[str, object] = {"prerequisites": scene_patch.prerequisites}
        if scene_patch.repeatable is not None:
            updates["repeatable"] = scene_patch.repeatable
        if scene_patch.forced is not None:
            updates["forced"] = scene_patch.forced
        patched_scenes[scene.id] = scene.model_copy(update=updates)

    if issues:
        raise VNParseError(ValidationReport(issues=issues))

    return Script.model_validate(
        {
            "meta": {"title": outline.title, "protagonist": protagonist},
            "state_vars": patch.state_vars,
            "start_scene": outline.start_scene,
            "scenes": [patched_scenes[scene.id].model_dump() for scene in scenes],
        }
    )
