"""Structured-output requests for pipeline stages.

Stages request their output model via the processor's structured-output support
(no JSON schema in the prompt). SDK-level parse failures become VNParseError
carrying a ValidationReport, so the bounded repair loop retries them with the
failure as feedback, exactly like gate failures.
"""

from pydantic import BaseModel

from src.models.prompt_processor import PromptProcessor
from src.models.vn.validation import ValidationIssue, ValidationReport


class VNParseError(Exception):
    """The LLM response could not be turned into the stage's output model."""

    def __init__(self, report: ValidationReport) -> None:
        super().__init__("; ".join(issue.message for issue in report.issues))
        self.report = report


def request_model[T: BaseModel](processor: PromptProcessor, system_prompt: str, user_prompt: str, output_type: type[T], max_tokens: int) -> T:
    try:
        return processor.respond_with_model(prompt=system_prompt, user_prompt=user_prompt, output_type=output_type, max_tokens=max_tokens)
    except ValueError as exc:  # covers SDK "no/unparseable structured output" and pydantic ValidationError
        raise VNParseError(ValidationReport(issues=[ValidationIssue(code="output_parse_error", message=str(exc))])) from exc
