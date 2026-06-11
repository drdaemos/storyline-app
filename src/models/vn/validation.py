"""Validation report models shared by the structural validator, softlock checker, and pipeline gates."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["error", "warning"]


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: Severity = "error"
    message: str
    scene_id: str | None = None
    beat_id: str | None = None
    # Optional state witness for softlock findings: var assignment at the failing node.
    state: dict[str, bool | int | str] | None = None


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def valid(self) -> bool:
        return not self.errors

    def merged(self, other: "ValidationReport") -> "ValidationReport":
        return ValidationReport(issues=[*self.issues, *other.issues])
