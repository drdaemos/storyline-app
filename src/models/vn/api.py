"""Request/response models for the VN API router."""

from pydantic import BaseModel, ConfigDict, Field

from src.models.vn.input import VNInput
from src.models.vn.pipeline import ScriptOutline
from src.models.vn.runtime import EngineEvent, EngineView, VNAction
from src.models.vn.script import Scene, Script
from src.models.vn.validation import ValidationReport


class VNApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VNScriptSummary(VNApiModel):
    id: str
    title: str
    validation_status: str
    scene_count: int
    ending_count: int
    created_at: str
    updated_at: str


class VNScriptDetail(VNApiModel):
    id: str
    title: str
    validation_status: str
    script: Script
    created_at: str
    updated_at: str


class ImportVNScriptRequest(VNApiModel):
    script: Script


class ImportVNScriptResponse(VNApiModel):
    script_id: str
    validation_status: str
    report: ValidationReport


class ValidateVNScriptRequest(VNApiModel):
    script: Script


class GenerateVNScriptRequest(VNApiModel):
    input: VNInput
    processor_type: str = "claude-sonnet"


class VNGenerationJobSummary(VNApiModel):
    """A failed (resumable) or still-running generation run, including everything produced so far."""

    job_id: str
    status: str
    error: str | None = None
    processor_type: str
    synopsis: str
    outline: ScriptOutline | None = None
    completed_scenes: list[str] = Field(default_factory=list)
    scenes: list[Scene] = Field(default_factory=list)
    created_at: str
    updated_at: str


class CreateVNSessionRequest(VNApiModel):
    script_id: str
    seed: int | None = None


class NarrateVNSessionRequest(VNApiModel):
    processor_type: str = "claude-sonnet"


class AdvanceVNSessionRequest(VNApiModel):
    action: VNAction


class VNNarrationEntry(VNApiModel):
    event_index: int
    text: str


class VNSessionView(VNApiModel):
    session_id: str
    script_id: str
    script_title: str
    status: str
    view: EngineView
    new_events: list[EngineEvent] = Field(default_factory=list)
    event_log: list[EngineEvent] = Field(default_factory=list)
    narration_log: list[VNNarrationEntry] = Field(default_factory=list)


class VNSessionSummary(VNApiModel):
    session_id: str
    script_id: str
    script_title: str
    status: str
    created_at: str
    updated_at: str
