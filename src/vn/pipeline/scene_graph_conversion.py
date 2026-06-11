"""Convert Anthropic-friendly scene graph output into canonical draft scenes."""

from pydantic import ValidationError

from src.models.vn.script import DraftScene, LLMBeat, LLMScene
from src.models.vn.validation import ValidationIssue, ValidationReport
from src.vn.pipeline.parsing import VNParseError


def llm_scene_to_draft_scene(scene: LLMScene) -> DraftScene:
    """Convert the flat request-only scene shape into `DraftScene`.

    Provider-enforced structured output keeps only cheap shape constraints. This
    conversion restores the richer routing semantics and lets model validators
    catch malformed beats inside the usual repair loop.
    """
    beat_dicts: list[dict[str, object]] = []
    issues: list[ValidationIssue] = []
    for beat in scene.beats:
        try:
            beat_dicts.append(_llm_beat_to_draft_dict(beat))
        except ValueError as exc:
            issues.append(ValidationIssue(code="output_parse_error", beat_id=beat.id, message=str(exc)))

    if issues:
        raise VNParseError(ValidationReport(issues=issues))

    try:
        return DraftScene.model_validate(
            {
                "id": scene.id,
                "intent": scene.intent,
                "entry_beat": scene.entry_beat,
                "beats": beat_dicts,
            }
        )
    except ValidationError as exc:
        raise VNParseError(_validation_error_report(exc, scene.id)) from exc


def _llm_beat_to_draft_dict(beat: LLMBeat) -> dict[str, object]:
    common: dict[str, object] = {
        "id": beat.id,
        "type": beat.type,
        "intent": beat.intent,
        "extension": {"deeper_domain": beat.extension_domain.strip()} if beat.extension_domain.strip() else None,
    }
    if beat.type == "plain":
        return {**common, **_parse_route(beat)}
    if beat.type == "check":
        if beat.check_difficulty <= 0:
            raise ValueError(f"check beat '{beat.id}' requires a positive check_difficulty")
        success = beat.check_success.strip()
        failure = beat.check_failure.strip()
        if not success or not failure:
            raise ValueError(f"check beat '{beat.id}' requires check_success and check_failure")
        if success == failure:
            raise ValueError(f"check beat '{beat.id}' success and failure must target different beats")
        return {
            **common,
            "check": {
                "difficulty": beat.check_difficulty,
                "on_success": success,
                "on_failure": failure,
            },
        }
    if beat.type == "choice":
        targets = [option.target.strip() for option in beat.options]
        if len(set(targets)) != len(targets):
            raise ValueError(f"choice beat '{beat.id}' options must target distinct beats")
        return {
            **common,
            "options": [{"intent": option.intent, "target": target} for option, target in zip(beat.options, targets, strict=True)],
        }
    if not beat.ending_id.strip():
        raise ValueError(f"ending beat '{beat.id}' requires ending_id")
    return {**common, "ending_id": beat.ending_id.strip()}


def _parse_route(beat: LLMBeat) -> dict[str, object]:
    route = beat.route.strip()
    if route.startswith("next:"):
        target = route.removeprefix("next:").strip()
        if not target:
            raise ValueError(f"plain beat '{beat.id}' has an empty next route")
        return {"next": target}
    if route in {"exit:open", "open"}:
        return {"exit": "open"}
    if route.startswith("edges:"):
        raw_edges = route.removeprefix("edges:").strip()
        if not raw_edges:
            raise ValueError(f"plain beat '{beat.id}' has no exit edges")
        return {"exit_edges": _parse_exit_edges(raw_edges, beat.id)}
    raise ValueError(f"plain beat '{beat.id}' route must be next:<beat>, exit:open, or edges:<scene>@<priority>|...")


def _parse_exit_edges(raw_edges: str, beat_id: str) -> list[dict[str, object]]:
    edges: list[dict[str, object]] = []
    for index, raw_edge in enumerate(raw_edges.split("|"), start=1):
        edge = raw_edge.strip()
        if not edge:
            raise ValueError(f"plain beat '{beat_id}' has an empty exit edge")
        scene_id, separator, priority_text = edge.partition("@")
        scene_id = scene_id.strip()
        if not scene_id:
            raise ValueError(f"plain beat '{beat_id}' has an exit edge with no scene id")
        if separator:
            try:
                priority = int(priority_text.strip())
            except ValueError as exc:
                raise ValueError(f"plain beat '{beat_id}' has non-integer exit priority '{priority_text}'") from exc
        else:
            priority = index
        edges.append({"target_scene": scene_id, "priority": priority})
    return edges


def _validation_error_report(exc: ValidationError, scene_id: str) -> ValidationReport:
    return ValidationReport(
        issues=[
            ValidationIssue(code="output_parse_error", scene_id=scene_id, message=str(error.get("msg", error)))
            for error in exc.errors()
        ]
    )
