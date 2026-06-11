"""Bounded local repair loop: re-run one producer with gate feedback until it passes or attempts run out."""

from collections.abc import Callable
from typing import TypeVar

from src.models.vn.validation import ValidationReport
from src.vn.pipeline.parsing import VNParseError

T = TypeVar("T")

DEFAULT_MAX_ATTEMPTS = 3


class VNGenerationError(Exception):
    """A pipeline stage kept failing its hard gate after bounded repairs."""

    def __init__(self, message: str, report: ValidationReport) -> None:
        super().__init__(message)
        self.report = report


def run_with_repair(
    produce: Callable[[ValidationReport | None], T],
    gate: Callable[[T], ValidationReport],
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    on_repair: Callable[[ValidationReport], None] | None = None,
) -> T:
    """Call produce (with the previous failing report as feedback, if any) until gate passes.

    A VNParseError from produce counts as a failed attempt and its report becomes the feedback.
    Raises VNGenerationError with the last report after max_attempts failures.
    """
    feedback: ValidationReport | None = None
    report = ValidationReport()
    for _ in range(max_attempts):
        try:
            candidate = produce(feedback)
        except VNParseError as exc:
            report = exc.report
        else:
            report = gate(candidate)
            if report.valid:
                return candidate
        feedback = report
        if on_repair is not None:
            on_repair(report)
    raise VNGenerationError(f"stage failed its gate after {max_attempts} attempts", report)
