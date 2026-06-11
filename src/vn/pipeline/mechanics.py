"""Stage C: state vars, effects, guards, and check modifiers over the drafted scenes.

The LLM emits only a MechanicsPatch (the delta over the drafted structure); the final
Script is assembled in code, so the draft cannot drift and the output stays small.
Its gate is the full structural validation plus scope re-checks; the generator
additionally runs the softlock walk as part of this stage's repair loop (final gate).
"""

from src.models.prompt_processor import PromptProcessor
from src.models.vn.input import VNInput
from src.models.vn.pipeline import LLMMechanicsPatch, ScriptOutline
from src.models.vn.script import CheckBeat, ChoiceBeat, Condition, EndingBeat, PlainBeat, Scene, Script
from src.models.vn.validation import ValidationIssue, ValidationReport
from src.vn.pipeline.mechanics_dsl import llm_mechanics_patch_to_patch
from src.vn.pipeline.parsing import request_model
from src.vn.pipeline.patching import apply_mechanics_patch
from src.vn.pipeline.prompts import SYSTEM_PROMPT, mechanics_user_prompt
from src.vn.validator import validate_script

MECHANICS_MAX_TOKENS = 16384


class MechanicsStage:
    def __init__(self, processor: PromptProcessor) -> None:
        self.processor = processor

    def run(self, vn_input: VNInput, outline: ScriptOutline, scenes: list[Scene], feedback: ValidationReport | None = None) -> Script:
        llm_patch = request_model(self.processor, SYSTEM_PROMPT, mechanics_user_prompt(vn_input, outline, scenes, feedback), LLMMechanicsPatch, MECHANICS_MAX_TOKENS)
        patch = llm_mechanics_patch_to_patch(llm_patch)
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
        issues.extend(_state_usage_issues(script))

        return ValidationReport(issues=issues)


def _state_usage_issues(script: Script) -> list[ValidationIssue]:
    var_names = {var.name for var in script.state_vars}
    writes = dict.fromkeys(var_names, 0)
    reads = dict.fromkeys(var_names, 0)

    def count_condition(condition: Condition) -> None:
        if condition.var is not None and condition.var in reads:
            reads[condition.var] += 1

    def count_guard(guard: list[Condition]) -> None:
        for condition in guard:
            count_condition(condition)

    for scene in script.scenes:
        count_guard(scene.prerequisites)
        for beat in scene.beats:
            for effect in beat.effects:
                if effect.var in writes:
                    writes[effect.var] += 1
            if isinstance(beat, PlainBeat):
                for edge in beat.exit_edges or []:
                    count_guard(edge.guard)
            elif isinstance(beat, ChoiceBeat):
                for option in beat.options:
                    count_guard(option.guard)
            elif isinstance(beat, CheckBeat):
                for modifier in beat.check.modifiers:
                    count_condition(modifier)

    issues: list[ValidationIssue] = []
    for name in sorted(var_names):
        if writes[name] == 0:
            issues.append(ValidationIssue(code="state_var_never_written", message=f"state var '{name}' is declared but never written by any beat effect"))
        if reads[name] == 0:
            issues.append(ValidationIssue(code="state_var_never_read", message=f"state var '{name}' is written but never read by any guard, prerequisite, exit edge, or check modifier"))
    return issues
