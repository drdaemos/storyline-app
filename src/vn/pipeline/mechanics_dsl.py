"""Parse request-only mechanics DSL into canonical patch models."""

import re
import shlex
from collections.abc import Callable

from pydantic import ValidationError

from src.models.vn.pipeline import (
    BeatEffectsPatch,
    CheckModifiersPatch,
    ExitEdgeGuardPatch,
    LLMMechanicsPatch,
    MechanicsPatch,
    OptionGuardPatch,
    ScenePatch,
)
from src.models.vn.script import CheckModifier, Condition, CounterVar, Effect, EnumVar, FlagVar, StateValue, StateVar
from src.models.vn.validation import ValidationIssue, ValidationReport
from src.vn.pipeline.parsing import VNParseError

_EFFECT_RE = re.compile(r"^(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*(?P<op>\+=|-=|=)\s*(?P<value>.+)$")
_GUARD_RE = re.compile(r"^(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*(?P<op>==|=|>=|<=)\s*(?P<value>.+)$")


def llm_mechanics_patch_to_patch(patch: LLMMechanicsPatch) -> MechanicsPatch:
    """Convert the flat mechanics DSL patch into the canonical `MechanicsPatch`."""
    issues: list[ValidationIssue] = []

    state_vars = _collect(issues, patch.state_vars, _parse_state_var, "state_vars")
    beat_effects = [
        BeatEffectsPatch(beat_id=item.beat_id, effects=_collect(issues, item.effects, _parse_effect, "beat_effects", beat_id=item.beat_id))
        for item in patch.beat_effects
    ]
    option_guards = [
        OptionGuardPatch(beat_id=item.beat_id, option_index=item.option_index, guard=_parse_guard_list(issues, item.guard, "option_guards", item.beat_id))
        for item in patch.option_guards
    ]
    exit_edge_guards = [
        ExitEdgeGuardPatch(beat_id=item.beat_id, edge_index=item.edge_index, guard=_parse_guard_list(issues, item.guard, "exit_edge_guards", item.beat_id))
        for item in patch.exit_edge_guards
    ]
    scene_patches = [
        ScenePatch(
            scene_id=item.scene_id,
            prerequisites=_parse_guard_list(issues, item.prerequisites, "scene_patches", scene_id=item.scene_id),
            repeatable=item.repeatable,
            forced=None if item.forced < 0 else item.forced,
        )
        for item in patch.scene_patches
    ]
    check_modifiers = [
        CheckModifiersPatch(beat_id=item.beat_id, modifiers=_collect(issues, item.modifiers, _parse_modifier, "check_modifiers", beat_id=item.beat_id))
        for item in patch.check_modifiers
    ]

    if issues:
        raise VNParseError(ValidationReport(issues=issues))

    try:
        return MechanicsPatch(
            state_vars=state_vars,
            beat_effects=beat_effects,
            option_guards=option_guards,
            exit_edge_guards=exit_edge_guards,
            scene_patches=scene_patches,
            check_modifiers=check_modifiers,
        )
    except ValidationError as exc:
        raise VNParseError(_validation_error_report(exc)) from exc


def _collect[T](
    issues: list[ValidationIssue],
    values: list[str],
    parser: Callable[[str], T],
    patch_kind: str,
    beat_id: str | None = None,
    scene_id: str | None = None,
) -> list[T]:
    parsed: list[T] = []
    for value in values:
        try:
            parsed.append(parser(value))
        except ValueError as exc:
            issues.append(ValidationIssue(code="output_parse_error", beat_id=beat_id, scene_id=scene_id, message=f"{patch_kind}: {exc}"))
    return parsed


def _parse_guard_list(issues: list[ValidationIssue], values: list[str], patch_kind: str, beat_id: str | None = None, scene_id: str | None = None) -> list[Condition]:
    return _collect(issues, values, _parse_condition, patch_kind, beat_id=beat_id, scene_id=scene_id)


def _parse_state_var(text: str) -> StateVar:
    parts = shlex.split(text)
    if len(parts) < 2:
        raise ValueError(f"invalid state var '{text}'")
    kind = parts[0]
    name, inline_initial = _name_and_inline_value(parts[1])
    params = _parse_params(parts[2:])
    if inline_initial is not None:
        params["initial"] = inline_initial

    if kind == "flag":
        initial = _parse_bool(params.get("initial", "false"))
        return FlagVar(name=name, initial=initial)
    if kind == "counter":
        if "max" not in params:
            raise ValueError(f"counter '{name}' requires max=N")
        return CounterVar(name=name, max=_parse_int(params["max"]), initial=_parse_int(params.get("initial", "0")))
    if kind == "enum":
        values_text = params.get("values")
        if values_text is None:
            raise ValueError(f"enum '{name}' requires values=a|b")
        values = [value.strip() for value in re.split(r"[|,]", values_text) if value.strip()]
        if not values:
            raise ValueError(f"enum '{name}' requires at least one value")
        initial = params.get("initial", values[0])
        return EnumVar(name=name, values=values, initial=initial)
    raise ValueError(f"unknown state var kind '{kind}'")


def _parse_effect(text: str) -> Effect:
    match = _EFFECT_RE.fullmatch(text.strip())
    if match is None:
        raise ValueError(f"invalid effect '{text}'")
    var = match.group("var")
    raw_op = match.group("op")
    raw_value = match.group("value")
    if raw_op == "=":
        return Effect(var=var, op="set", value=_parse_value(raw_value))
    value = _parse_int(raw_value)
    return Effect(var=var, op="inc" if raw_op == "+=" else "dec", value=value)


def _parse_condition(text: str) -> Condition:
    cleaned = text.strip()
    if cleaned.startswith("not visited:"):
        visited = cleaned.removeprefix("not visited:").strip()
        if not visited:
            raise ValueError(f"invalid visited condition '{text}'")
        return Condition(visited=visited, value=False)
    if cleaned.startswith("visited:"):
        visited = cleaned.removeprefix("visited:").strip()
        if not visited:
            raise ValueError(f"invalid visited condition '{text}'")
        return Condition(visited=visited)

    match = _GUARD_RE.fullmatch(cleaned)
    if match is None:
        raise ValueError(f"invalid guard '{text}'")
    op = "==" if match.group("op") == "=" else match.group("op")
    return Condition(var=match.group("var"), op=op, value=_parse_value(match.group("value")))


def _parse_modifier(text: str) -> CheckModifier:
    condition_text, separator, mod_text = text.partition("=>")
    if not separator:
        raise ValueError(f"modifier '{text}' must use '<guard> => <mod>'")
    condition = _parse_condition(condition_text)
    return CheckModifier(var=condition.var, op=condition.op, visited=condition.visited, value=condition.value, mod=_parse_int(mod_text))


def _parse_params(parts: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for part in parts:
        key, separator, value = part.partition("=")
        if not separator or not key or not value:
            raise ValueError(f"invalid parameter '{part}'")
        params[key] = value
    return params


def _name_and_inline_value(text: str) -> tuple[str, str | None]:
    name, separator, value = text.partition("=")
    if not name:
        raise ValueError(f"invalid name '{text}'")
    return name, value if separator else None


def _parse_value(text: str) -> StateValue:
    stripped = text.strip().strip("\"'")
    lower = stripped.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    try:
        return int(stripped)
    except ValueError:
        return stripped


def _parse_bool(text: str) -> bool:
    value = _parse_value(text)
    if isinstance(value, bool):
        return value
    raise ValueError(f"expected boolean value, got '{text}'")


def _parse_int(text: str) -> int:
    try:
        return int(text.strip())
    except ValueError as exc:
        raise ValueError(f"expected integer value, got '{text}'") from exc


def _validation_error_report(exc: ValidationError) -> ValidationReport:
    return ValidationReport(
        issues=[ValidationIssue(code="output_parse_error", message=str(error.get("msg", error))) for error in exc.errors()]
    )
