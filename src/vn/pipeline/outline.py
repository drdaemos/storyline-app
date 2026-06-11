"""Stage A: input -> scene-level outline, hard-gated on scope and id discipline."""

from src.models.prompt_processor import PromptProcessor
from src.models.vn.input import VNInput
from src.models.vn.pipeline import ScriptOutline
from src.models.vn.validation import ValidationIssue, ValidationReport
from src.vn.pipeline.parsing import request_model
from src.vn.pipeline.prompts import SYSTEM_PROMPT, outline_user_prompt

OUTLINE_MAX_TOKENS = 8192


class OutlineStage:
    def __init__(self, processor: PromptProcessor) -> None:
        self.processor = processor

    def run(self, vn_input: VNInput, feedback: ValidationReport | None = None) -> ScriptOutline:
        return request_model(self.processor, SYSTEM_PROMPT, outline_user_prompt(vn_input, feedback), ScriptOutline, OUTLINE_MAX_TOKENS)

    def gate(self, outline: ScriptOutline, vn_input: VNInput) -> ValidationReport:
        issues: list[ValidationIssue] = []
        scope = vn_input.premise.scope

        # target_scenes is guidance only — the model may add scenes if the story needs them.
        scene_ids = [scene.id for scene in outline.scenes]
        if len(set(scene_ids)) != len(scene_ids):
            issues.append(ValidationIssue(code="duplicate_scene_id", message="outline scene ids are not unique"))
        if outline.start_scene not in scene_ids:
            issues.append(ValidationIssue(code="unknown_start_scene", message=f"start_scene '{outline.start_scene}' is not in the outline"))

        all_ending_ids = [ending_id for scene in outline.scenes for ending_id in scene.ending_ids]
        if len(set(all_ending_ids)) != len(all_ending_ids):
            issues.append(ValidationIssue(code="duplicate_ending_id", message="ending ids are not unique across scenes"))
        if len(all_ending_ids) != scope.target_endings:
            issues.append(ValidationIssue(code="scope_ending_count_mismatch", message=f"outline plans {len(all_ending_ids)} endings, scope requires exactly {scope.target_endings}"))

        for scene in outline.scenes:
            if scene.exit_mode == "ending" and not scene.ending_ids:
                issues.append(ValidationIssue(code="ending_scene_without_endings", scene_id=scene.id, message=f"scene '{scene.id}' has exit_mode 'ending' but no ending_ids"))
            if scene.exit_mode != "ending" and scene.ending_ids:
                issues.append(ValidationIssue(code="misplaced_ending_ids", scene_id=scene.id, message=f"scene '{scene.id}' lists ending_ids but exit_mode is '{scene.exit_mode}'"))

        return ValidationReport(issues=issues)
