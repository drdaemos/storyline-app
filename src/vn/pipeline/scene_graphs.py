"""Stage B: per-scene beat mini-graphs, hard-gated per scene (failures stay local)."""

from pydantic import ValidationError

from src.models.prompt_processor import PromptProcessor
from src.models.vn.input import VNInput
from src.models.vn.pipeline import SceneOutlineItem, ScriptOutline
from src.models.vn.script import EndingBeat, LLMScene, PlainBeat, Scene, draft_scene_to_scene
from src.models.vn.validation import ValidationIssue, ValidationReport
from src.vn.pipeline.parsing import VNParseError, request_model
from src.vn.pipeline.prompts import SYSTEM_PROMPT, scene_graph_user_prompt
from src.vn.pipeline.scene_graph_conversion import llm_scene_to_draft_scene
from src.vn.validator import validate_scene_structure

SCENE_MAX_TOKENS = 8192


class SceneGraphStage:
    def __init__(self, processor: PromptProcessor) -> None:
        self.processor = processor

    def run(self, vn_input: VNInput, outline: ScriptOutline, item: SceneOutlineItem, feedback: ValidationReport | None = None) -> Scene:
        # Request an Anthropic-friendly flat scene shape, then convert to the
        # richer DraftScene/Scene models in code. This keeps provider grammar free
        # of beat unions and nullable routing fields.
        llm_scene = request_model(self.processor, SYSTEM_PROMPT, scene_graph_user_prompt(vn_input, outline, item, feedback), LLMScene, SCENE_MAX_TOKENS)
        draft = llm_scene_to_draft_scene(llm_scene)
        # Lifting the draft into the canonical Scene re-runs the stricter Scene/Beat
        # validators. Convert any failure into a VNParseError so the bounded repair
        # loop retries with the message as feedback, instead of crashing the job.
        try:
            return draft_scene_to_scene(draft)
        except ValidationError as exc:
            issues = [ValidationIssue(code="output_parse_error", scene_id=draft.id, message=str(err.get("msg", err))) for err in exc.errors()]
            raise VNParseError(ValidationReport(issues=issues)) from exc
        except ValueError as exc:
            raise VNParseError(ValidationReport(issues=[ValidationIssue(code="output_parse_error", scene_id=draft.id, message=str(exc))])) from exc

    def gate(self, scene: Scene, item: SceneOutlineItem) -> ValidationReport:
        report = validate_scene_structure(scene)
        issues = list(report.issues)

        if scene.id != item.id:
            issues.append(ValidationIssue(code="scene_id_mismatch", scene_id=scene.id, message=f"scene id '{scene.id}' does not match the outlined id '{item.id}'"))

        actual_endings = {beat.ending_id for beat in scene.beats if isinstance(beat, EndingBeat)}
        if actual_endings != set(item.ending_ids):
            issues.append(
                ValidationIssue(
                    code="outline_ending_mismatch",
                    scene_id=scene.id,
                    message=f"scene endings {sorted(actual_endings)} do not match outlined ending_ids {sorted(item.ending_ids)}",
                )
            )

        if not self._conforms_to_exit_mode(scene, item.exit_mode):
            issues.append(ValidationIssue(code="exit_mode_mismatch", scene_id=scene.id, message=f"scene '{scene.id}' does not realize outlined exit_mode '{item.exit_mode}'"))

        return ValidationReport(issues=issues)

    def _conforms_to_exit_mode(self, scene: Scene, exit_mode: str) -> bool:
        if exit_mode == "ending":
            return any(isinstance(beat, EndingBeat) for beat in scene.beats)
        if exit_mode == "open":
            return any(isinstance(beat, PlainBeat) and beat.exit == "open" for beat in scene.beats)
        return any(isinstance(beat, PlainBeat) and beat.exit_edges is not None for beat in scene.beats)
