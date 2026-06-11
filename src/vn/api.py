"""FastAPI router for the VN engine. Thin handlers only: parse -> service -> response."""

import json
import queue
import threading
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.auth import UserIdDep
from src.models.prompt_processor_factory import PromptProcessorFactory
from src.models.vn.api import (
    AdvanceVNSessionRequest,
    CreateVNSessionRequest,
    GenerateVNScriptRequest,
    ImportVNScriptRequest,
    ImportVNScriptResponse,
    NarrateVNSessionRequest,
    ValidateVNScriptRequest,
    VNGenerationJobSummary,
    VNScriptDetail,
    VNScriptSummary,
    VNSessionSummary,
    VNSessionView,
)
from src.models.vn.pipeline import PipelineProgress
from src.models.vn.validation import ValidationReport
from src.vn.engine import VNRuntimeError
from src.vn.narrator import VNNarrator
from src.vn.pipeline.generator import VNScriptGenerator
from src.vn.pipeline.repair import VNGenerationError
from src.vn.registry import VNGenerationJobRegistry, VNScriptRegistry, VNSessionRegistry
from src.vn.service import VNConflictError, VNNotFoundError, VNService

router = APIRouter(prefix="/api/vn", tags=["vn"])

_service: VNService | None = None


def get_vn_service() -> VNService:
    global _service
    if _service is None:
        _service = VNService(VNScriptRegistry(), VNSessionRegistry(), VNGenerationJobRegistry())
    return _service


VNServiceDep = Annotated[VNService, Depends(get_vn_service)]


@router.post("/scripts/validate")
async def validate_script_endpoint(request: ValidateVNScriptRequest, user_id: UserIdDep, service: VNServiceDep) -> ValidationReport:
    return service.validate(request.script)


@router.post("/scripts")
async def import_script(request: ImportVNScriptRequest, user_id: UserIdDep, service: VNServiceDep) -> ImportVNScriptResponse:
    script_id, status, report = service.import_script(request.script, user_id)
    return ImportVNScriptResponse(script_id=script_id, validation_status=status, report=report)


@router.get("/scripts")
async def list_scripts(user_id: UserIdDep, service: VNServiceDep) -> list[VNScriptSummary]:
    return service.list_scripts(user_id)


@router.get("/scripts/{script_id}")
async def get_script(script_id: str, user_id: UserIdDep, service: VNServiceDep) -> VNScriptDetail:
    try:
        return service.get_script(script_id, user_id)
    except VNNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/scripts/{script_id}")
async def delete_script(script_id: str, user_id: UserIdDep, service: VNServiceDep) -> dict[str, str]:
    try:
        service.delete_script(script_id, user_id)
    except VNNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"message": "deleted"}


@router.post("/scripts/generate")
async def generate_script(request: GenerateVNScriptRequest, user_id: UserIdDep, service: VNServiceDep) -> StreamingResponse:
    """Run the staged generation pipeline as a persistent job, streaming progress as Server-Sent Events:
    data: {"type": "started", "job_id": ...}
    data: {"type": "progress", "stage": ..., "status": ..., "scene_id": ..., "detail": ...}
    data: {"type": "complete", "script_id": ..., "validation_status": ...}
    data: {"type": "error", "job_id": ..., "error": ..., "issues": [...]}

    Passed stages are checkpointed; after an error the job can be resumed via its job_id.
    """
    job_id = service.start_generation_job(request.input, request.processor_type, user_id)
    generator = VNScriptGenerator(PromptProcessorFactory.create_processor(request.processor_type))
    return StreamingResponse(_generation_event_stream(service, generator, job_id, user_id), media_type="text/event-stream")


@router.post("/generation-jobs/{job_id}/resume")
async def resume_generation_job(job_id: str, user_id: UserIdDep, service: VNServiceDep) -> StreamingResponse:
    """Resume a failed generation job from its checkpoint; same SSE stream as /scripts/generate."""
    try:
        job = service.get_generation_job(job_id, user_id)
    except VNNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    generator = VNScriptGenerator(PromptProcessorFactory.create_processor(job.processor_type))
    return StreamingResponse(_generation_event_stream(service, generator, job_id, user_id), media_type="text/event-stream")


@router.get("/generation-jobs")
async def list_generation_jobs(user_id: UserIdDep, service: VNServiceDep) -> list[VNGenerationJobSummary]:
    return service.list_generation_jobs(user_id)


@router.delete("/generation-jobs/{job_id}")
async def delete_generation_job(job_id: str, user_id: UserIdDep, service: VNServiceDep) -> dict[str, str]:
    try:
        service.delete_generation_job(job_id, user_id)
    except VNNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"message": "deleted"}


def _generation_event_stream(service: VNService, generator: VNScriptGenerator, job_id: str, user_id: str) -> Iterator[str]:
    """Generation runs in a worker thread; progress events are relayed through a queue as they happen."""
    events: queue.Queue[str | None] = queue.Queue()
    events.put(_sse({"type": "started", "job_id": job_id}))

    def on_progress(progress: PipelineProgress) -> None:
        events.put(_sse({"type": "progress", **progress.model_dump()}))

    def work() -> None:
        try:
            script_id, status, _report = service.run_generation_job(job_id, generator, user_id, on_progress)
            events.put(_sse({"type": "complete", "script_id": script_id, "validation_status": status}))
        except VNGenerationError as e:
            events.put(_sse({"type": "error", "job_id": job_id, "error": str(e), "issues": [issue.model_dump() for issue in e.report.issues]}))
        except Exception as e:
            events.put(_sse({"type": "error", "job_id": job_id, "error": str(e), "issues": []}))
        finally:
            events.put(None)

    threading.Thread(target=work, daemon=True).start()
    while (item := events.get()) is not None:
        yield item


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/sessions")
async def create_session(request: CreateVNSessionRequest, user_id: UserIdDep, service: VNServiceDep) -> VNSessionView:
    try:
        return service.create_session(request.script_id, user_id, seed=request.seed)
    except VNNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except VNConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/sessions")
async def list_sessions(user_id: UserIdDep, service: VNServiceDep, script_id: str | None = None) -> list[VNSessionSummary]:
    return service.list_sessions(user_id, script_id)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user_id: UserIdDep, service: VNServiceDep) -> VNSessionView:
    try:
        return service.get_session(session_id, user_id)
    except VNNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/sessions/{session_id}/advance")
async def advance_session(session_id: str, request: AdvanceVNSessionRequest, user_id: UserIdDep, service: VNServiceDep) -> VNSessionView:
    try:
        return service.advance_session(session_id, request.action, user_id)
    except VNNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except VNRuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/sessions/{session_id}/narrate")
async def narrate_session(session_id: str, request: NarrateVNSessionRequest, user_id: UserIdDep, service: VNServiceDep) -> StreamingResponse:
    """Stream prose narration for events not yet narrated. Never changes runtime state."""
    narrator = VNNarrator(PromptProcessorFactory.create_processor(request.processor_type))
    try:
        stream = service.narrate_session(session_id, user_id, narrator)
    except VNNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except VNConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return StreamingResponse(stream, media_type="text/plain")


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user_id: UserIdDep, service: VNServiceDep) -> dict[str, str]:
    try:
        service.delete_session(session_id, user_id)
    except VNNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"message": "deleted"}
