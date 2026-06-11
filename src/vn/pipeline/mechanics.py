"""Stage C: state vars, effects, guards, and check modifiers over the drafted scenes.

The LLM emits only a MechanicsPatch (the delta over the drafted structure); the final
Script is assembled in code, so the draft cannot drift and the output stays small.
Its gate is the full structural validation plus scope re-checks; the generator
additionally runs the softlock walk as part of this stage's repair loop (final gate).
"""

from src.models.prompt_processor import PromptProcessor
from src.models.vn.input import VNInput
from src.models.vn.pipeline import MechanicsPatch, ScriptOutline
from src.models.vn.script import EndingBeat, Scene, Script
from src.models.vn.validation import ValidationIssue, ValidationReport
from src.vn.pipeline.parsing import request_model
from src.vn.pipeline.patching import apply_mechanics_patch
from src.vn.pipeline.prompts import SYSTEM_PROMPT, mechanics_user_prompt
from src.vn.validator import validate_script

MECHANICS_MAX_TOKENS = 16384


class MechanicsStage:
    def __init__(self, processor: PromptProcessor) -> None:
        self.processor = processor

    def run(self, vn_input: VNInput, outline: ScriptOutline, scenes: list[Scene], feedback: ValidationReport | None = None) -> Script:
        patch = request_model(self.processor, SYSTEM_PROMPT, mechanics_user_prompt(vn_input, outline, scenes, feedback), MechanicsPatch, MECHANICS_MAX_TOKENS)
        protagonist = next(character.name for character in vn_input.characters if character.protagonist)
        return apply_mechanics_patch(outline, scenes, protagonist, patch)

    def gate(self, script: Script, vn_input: VNInput) -> ValidationReport:
        report = validate_script(script)
        issues = list(report.issues)
        scope = vn_input.premise.scope

        # scene count is guidance only; endings remain a hard scope requirement
        ending_count = sum(1 for scene in script.scenes for beat in scene.beats if isinstance(beat, EndingBeat))
        if ending_count != scope.target_endings:
            issues.append(ValidationIssue(code="scope_ending_count_mismatch", message=f"script has {ending_count} endings, scope requires exactly {scope.target_endings}"))

        return ValidationReport(issues=issues)
