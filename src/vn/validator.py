"""Structural hard gates over a script (no LLM, no state-space walk).

Two entry points:
- validate_scene_structure(scene): scene-local checks usable before state vars
  exist (pipeline Stage B gate).
- validate_script(script): everything — id resolution, var/domain checks,
  routing rules, non-gated path invariant (full gate before the softlock walk).

State-dependent properties (dead ends, forced-priority ties among available
scenes) belong to the softlock checker, not here.
"""

from src.models.vn.script import (
    Beat,
    CheckBeat,
    ChoiceBeat,
    Condition,
    CounterVar,
    Effect,
    EndingBeat,
    EnumVar,
    FlagVar,
    PlainBeat,
    Scene,
    Script,
    StateVar,
)
from src.models.vn.validation import ValidationIssue, ValidationReport


def validate_script(script: Script) -> ValidationReport:
    issues: list[ValidationIssue] = []

    declarations = _collect_declarations(script, issues)
    scene_ids = _collect_scene_ids(script, issues)
    all_ids = _collect_all_ids(script, issues, scene_ids)

    if script.start_scene not in scene_ids:
        issues.append(ValidationIssue(code="unknown_start_scene", message=f"start_scene '{script.start_scene}' does not match any scene"))

    for scene in script.scenes:
        issues.extend(_scene_structure_issues(scene))
        issues.extend(_scene_reference_issues(scene, scene_ids, all_ids, declarations))

    duplicate_forced = _duplicate_forced_values(script)
    for value, ids in duplicate_forced.items():
        issues.append(
            ValidationIssue(
                code="duplicate_forced_priority",
                severity="warning",
                message=f"scenes {ids} share forced priority {value}; if ever simultaneously available this is an error (softlock walk verifies)",
            )
        )

    return ValidationReport(issues=issues)


def validate_scene_structure(scene: Scene) -> ValidationReport:
    """Scene-local gate: ids, routing resolution, non-gated path. No var checks."""
    return ValidationReport(issues=_scene_structure_issues(scene))


# --- collection helpers ------------------------------------------------------


def _collect_declarations(script: Script, issues: list[ValidationIssue]) -> dict[str, StateVar]:
    declarations: dict[str, StateVar] = {}
    for var in script.state_vars:
        if var.name in declarations:
            issues.append(ValidationIssue(code="duplicate_state_var", message=f"state var '{var.name}' declared more than once"))
        declarations[var.name] = var
    return declarations


def _collect_scene_ids(script: Script, issues: list[ValidationIssue]) -> set[str]:
    scene_ids: set[str] = set()
    for scene in script.scenes:
        if scene.id in scene_ids:
            issues.append(ValidationIssue(code="duplicate_scene_id", scene_id=scene.id, message=f"scene id '{scene.id}' is not unique"))
        scene_ids.add(scene.id)
    return scene_ids


def _collect_all_ids(script: Script, issues: list[ValidationIssue], scene_ids: set[str]) -> set[str]:
    """Beat ids must be globally unique (visited(id) addresses scenes and beats in one namespace)."""
    all_ids = set(scene_ids)
    for scene in script.scenes:
        for beat in scene.beats:
            if beat.id in all_ids:
                issues.append(ValidationIssue(code="duplicate_beat_id", scene_id=scene.id, beat_id=beat.id, message=f"beat id '{beat.id}' collides with another beat or scene id"))
            all_ids.add(beat.id)
    return all_ids


def _duplicate_forced_values(script: Script) -> dict[int, list[str]]:
    by_value: dict[int, list[str]] = {}
    for scene in script.scenes:
        if scene.forced is not None:
            by_value.setdefault(scene.forced, []).append(scene.id)
    return {value: ids for value, ids in by_value.items() if len(ids) > 1}


# --- scene-local structure ----------------------------------------------------


def _scene_structure_issues(scene: Scene) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    beats_by_id: dict[str, Beat] = {}
    for beat in scene.beats:
        if beat.id in beats_by_id:
            issues.append(ValidationIssue(code="duplicate_beat_id_in_scene", scene_id=scene.id, beat_id=beat.id, message=f"beat id '{beat.id}' duplicated within scene"))
        beats_by_id[beat.id] = beat

    if scene.entry_beat not in beats_by_id:
        issues.append(ValidationIssue(code="unknown_entry_beat", scene_id=scene.id, message=f"entry_beat '{scene.entry_beat}' is not a beat of scene '{scene.id}'"))

    for beat in scene.beats:
        for target in _in_scene_targets(beat):
            if target not in beats_by_id:
                issues.append(ValidationIssue(code="unknown_beat_ref", scene_id=scene.id, beat_id=beat.id, message=f"beat '{beat.id}' routes to unknown in-scene beat '{target}'"))
        if isinstance(beat, PlainBeat) and beat.exit_edges is not None:
            priorities = [edge.priority for edge in beat.exit_edges]
            if len(set(priorities)) != len(priorities):
                issues.append(ValidationIssue(code="equal_exit_priorities", scene_id=scene.id, beat_id=beat.id, message=f"exit node '{beat.id}' has exit edges with equal priorities"))

    if scene.entry_beat in beats_by_id and not _non_gated_path_reaches_exit(scene, beats_by_id):
        issues.append(
            ValidationIssue(
                code="no_non_gated_path",
                scene_id=scene.id,
                message=f"scene '{scene.id}': the non-gated subgraph does not connect entry to an exit or ending",
            )
        )

    return issues


def _in_scene_targets(beat: Beat) -> list[str]:
    if isinstance(beat, PlainBeat):
        return [beat.next] if beat.next is not None else []
    if isinstance(beat, CheckBeat):
        return [beat.check.on_success, beat.check.on_failure]
    if isinstance(beat, ChoiceBeat):
        return [option.target for option in beat.options]
    return []


def _non_gated_successors(beat: Beat) -> list[str]:
    """Successors reachable without satisfying any guard. Both check outcomes count:
    a check is not a gate (both branches must lead somewhere)."""
    if isinstance(beat, PlainBeat):
        return [beat.next] if beat.next is not None else []
    if isinstance(beat, CheckBeat):
        return [beat.check.on_success, beat.check.on_failure]
    if isinstance(beat, ChoiceBeat):
        return [option.target for option in beat.options if not option.guard]
    return []


def _is_exit_node(beat: Beat) -> bool:
    if isinstance(beat, EndingBeat):
        return True
    return isinstance(beat, PlainBeat) and (beat.exit_edges is not None or beat.exit is not None)


def _non_gated_path_reaches_exit(scene: Scene, beats_by_id: dict[str, Beat]) -> bool:
    frontier = [scene.entry_beat]
    seen: set[str] = set()
    while frontier:
        beat_id = frontier.pop()
        if beat_id in seen or beat_id not in beats_by_id:
            continue
        seen.add(beat_id)
        beat = beats_by_id[beat_id]
        if _is_exit_node(beat):
            return True
        frontier.extend(_non_gated_successors(beat))
    return False


# --- references and domains ----------------------------------------------------


def _scene_reference_issues(scene: Scene, scene_ids: set[str], all_ids: set[str], declarations: dict[str, StateVar]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for condition in scene.prerequisites:
        issues.extend(_condition_issues(condition, declarations, all_ids, scene.id, None, context="prerequisite"))

    for beat in scene.beats:
        for effect in beat.effects:
            issues.extend(_effect_issues(effect, declarations, scene.id, beat.id))
        if isinstance(beat, PlainBeat) and beat.exit_edges is not None:
            for edge in beat.exit_edges:
                if edge.target_scene not in scene_ids:
                    issues.append(ValidationIssue(code="unknown_scene_ref", scene_id=scene.id, beat_id=beat.id, message=f"exit edge targets unknown scene '{edge.target_scene}'"))
                for condition in edge.guard:
                    issues.extend(_condition_issues(condition, declarations, all_ids, scene.id, beat.id, context="exit edge guard"))
        if isinstance(beat, ChoiceBeat):
            for option in beat.options:
                for condition in option.guard:
                    issues.extend(_condition_issues(condition, declarations, all_ids, scene.id, beat.id, context="option guard"))
        if isinstance(beat, CheckBeat):
            for modifier in beat.check.modifiers:
                issues.extend(_condition_issues(modifier, declarations, all_ids, scene.id, beat.id, context="check modifier"))

    return issues


def _condition_issues(condition: Condition, declarations: dict[str, StateVar], all_ids: set[str], scene_id: str, beat_id: str | None, context: str) -> list[ValidationIssue]:
    if condition.is_visited:
        if condition.visited not in all_ids:
            return [ValidationIssue(code="unknown_visited_ref", scene_id=scene_id, beat_id=beat_id, message=f"{context}: visited('{condition.visited}') matches no scene or beat id")]
        return []

    assert condition.var is not None  # narrowed by is_var; guaranteed by the model validator
    declaration = declarations.get(condition.var)
    if declaration is None:
        return [ValidationIssue(code="unknown_var_ref", scene_id=scene_id, beat_id=beat_id, message=f"{context}: condition references undeclared var '{condition.var}'")]

    issues: list[ValidationIssue] = []
    if condition.op in (">=", "<="):
        if not isinstance(declaration, CounterVar):
            issues.append(ValidationIssue(code="invalid_condition_op", scene_id=scene_id, beat_id=beat_id, message=f"{context}: ordered comparison on non-counter var '{condition.var}'"))
        elif not isinstance(condition.value, int) or isinstance(condition.value, bool):
            issues.append(ValidationIssue(code="condition_value_out_of_domain", scene_id=scene_id, beat_id=beat_id, message=f"{context}: ordered comparison on '{condition.var}' requires an int value"))
    elif not _value_in_domain(condition.value, declaration):
        issues.append(ValidationIssue(code="condition_value_out_of_domain", scene_id=scene_id, beat_id=beat_id, message=f"{context}: value {condition.value!r} outside domain of '{condition.var}'"))
    return issues


def _effect_issues(effect: Effect, declarations: dict[str, StateVar], scene_id: str, beat_id: str) -> list[ValidationIssue]:
    declaration = declarations.get(effect.var)
    if declaration is None:
        return [ValidationIssue(code="unknown_var_ref", scene_id=scene_id, beat_id=beat_id, message=f"effect references undeclared var '{effect.var}'")]

    if isinstance(declaration, FlagVar):
        if effect.op != "set" or not isinstance(effect.value, bool):
            return [ValidationIssue(code="invalid_effect", scene_id=scene_id, beat_id=beat_id, message=f"flag '{effect.var}' only supports set with a bool value")]
    elif isinstance(declaration, CounterVar):
        if not isinstance(effect.value, int) or isinstance(effect.value, bool):
            return [ValidationIssue(code="invalid_effect", scene_id=scene_id, beat_id=beat_id, message=f"counter '{effect.var}' requires an int effect value")]
    elif isinstance(declaration, EnumVar):
        if effect.op != "set":
            return [ValidationIssue(code="invalid_effect", scene_id=scene_id, beat_id=beat_id, message=f"enum '{effect.var}' only supports set")]
        if effect.value not in declaration.values:
            return [ValidationIssue(code="invalid_effect", scene_id=scene_id, beat_id=beat_id, message=f"enum '{effect.var}': value {effect.value!r} not in declared values")]
    return []


def _value_in_domain(value: bool | int | str, declaration: StateVar) -> bool:
    if isinstance(declaration, FlagVar):
        return isinstance(value, bool)
    if isinstance(declaration, CounterVar):
        return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= declaration.max
    return value in declaration.values
