"""VNService: orchestration between registries, validator, softlock checker, and engine.

Holds all the logic the API router would otherwise contain. Raises typed errors;
the router maps them to HTTP statuses.
"""

import random
from collections.abc import Iterator
from typing import Literal

from pydantic import TypeAdapter

from src.models.vn.api import (
    VNGenerationJobSummary,
    VNNarrationEntry,
    VNScriptDetail,
    VNScriptSummary,
    VNSessionSummary,
    VNSessionView,
)
from src.models.vn.input import VNInput
from src.models.vn.pipeline import GenerationCheckpoint
from src.models.vn.runtime import EngineEvent, VNAction, VNRuntimeState
from src.models.vn.script import EndingBeat, Script
from src.models.vn.validation import ValidationReport
from src.vn.engine import VNEngine
from src.vn.narrator import VNNarrator
from src.vn.pipeline.generator import ProgressCallback, VNScriptGenerator
from src.vn.registry import VNGenerationJobRegistry, VNScriptRegistry, VNSessionRegistry
from src.vn.softlock import check_softlocks
from src.vn.validator import validate_script

_EVENT_LIST = TypeAdapter(list[EngineEvent])

ValidationStatus = Literal["valid", "invalid"]


class VNNotFoundError(Exception):
    pass


class VNConflictError(Exception):
    pass


class VNService:
    def __init__(self, script_registry: VNScriptRegistry, session_registry: VNSessionRegistry, job_registry: VNGenerationJobRegistry) -> None:
        self.scripts = script_registry
        self.sessions = session_registry
        self.jobs = job_registry

    # --- scripts -------------------------------------------------------------

    def validate(self, script: Script) -> ValidationReport:
        """Structural gates first; the softlock walk only runs on structurally sound scripts."""
        report = validate_script(script)
        if report.valid:
            report = report.merged(check_softlocks(script))
        return report

    def import_script(self, script: Script, user_id: str) -> tuple[str, ValidationStatus, ValidationReport]:
        report = self.validate(script)
        status: ValidationStatus = "valid" if report.valid else "invalid"
        script_id = self.scripts.save_script(
            script_data=script.model_dump(mode="json"),
            title=script.meta.title,
            user_id=user_id,
            validation_status=status,
        )
        return script_id, status, report

    # --- generation jobs -------------------------------------------------------

    def start_generation_job(self, vn_input: VNInput, processor_type: str, user_id: str) -> str:
        """Create a persistent record for a generation run before it starts, so progress survives failures."""
        return self.jobs.save_job(
            input_data=vn_input.model_dump(mode="json"),
            processor_type=processor_type,
            checkpoint=GenerationCheckpoint().model_dump(mode="json"),
            status="running",
            user_id=user_id,
        )

    def run_generation_job(self, job_id: str, generator: VNScriptGenerator, user_id: str, on_progress: ProgressCallback | None = None) -> tuple[str, ValidationStatus, ValidationReport]:
        """Run (or resume) a generation job. Each passed stage is checkpointed, so a failed run
        picks up after its last completed artifact. The pipeline's final gate already enforces
        validity; we revalidate independently and store the verdict rather than trusting it.
        On success the script is saved and the job record removed; on failure the job is kept
        with its checkpoint and the error."""
        record = self._job_record(job_id, user_id)
        vn_input = VNInput.model_validate(record["input_data"])
        checkpoint = GenerationCheckpoint.model_validate(record["checkpoint"] or {})

        def persist_checkpoint(state: GenerationCheckpoint) -> None:
            self.jobs.save_job(
                input_data=record["input_data"],
                processor_type=record["processor_type"],
                checkpoint=state.model_dump(mode="json"),
                status="running",
                user_id=user_id,
                job_id=job_id,
            )

        try:
            script = generator.generate(vn_input, on_progress, checkpoint=checkpoint, on_checkpoint=persist_checkpoint)
        except Exception as e:
            latest = self.jobs.get_job(job_id, user_id)
            self.jobs.save_job(
                input_data=record["input_data"],
                processor_type=record["processor_type"],
                checkpoint=latest["checkpoint"] if latest else record["checkpoint"],
                status="failed",
                user_id=user_id,
                job_id=job_id,
                error=str(e),
            )
            raise

        report = self.validate(script)
        status: ValidationStatus = "valid" if report.valid else "invalid"
        script_id = self.scripts.save_script(
            script_data=script.model_dump(mode="json"),
            title=script.meta.title,
            user_id=user_id,
            input_data=record["input_data"],
            validation_status=status,
        )
        self.jobs.delete_job(job_id, user_id)
        return script_id, status, report

    def get_generation_job(self, job_id: str, user_id: str) -> VNGenerationJobSummary:
        return self._job_summary(self._job_record(job_id, user_id))

    def list_generation_jobs(self, user_id: str) -> list[VNGenerationJobSummary]:
        return [self._job_summary(record) for record in self.jobs.list_jobs(user_id)]

    def delete_generation_job(self, job_id: str, user_id: str) -> None:
        if not self.jobs.delete_job(job_id, user_id):
            raise VNNotFoundError(f"generation job '{job_id}' not found")

    def list_scripts(self, user_id: str) -> list[VNScriptSummary]:
        summaries = []
        for record in self.scripts.list_scripts(user_id):
            script = Script.model_validate(record["script_data"])
            summaries.append(
                VNScriptSummary(
                    id=record["id"],
                    title=record["title"],
                    validation_status=record["validation_status"],
                    scene_count=len(script.scenes),
                    ending_count=sum(1 for scene in script.scenes for beat in scene.beats if isinstance(beat, EndingBeat)),
                    created_at=record["created_at"],
                    updated_at=record["updated_at"],
                )
            )
        return summaries

    def get_script(self, script_id: str, user_id: str) -> VNScriptDetail:
        record = self._script_record(script_id, user_id)
        return VNScriptDetail(
            id=record["id"],
            title=record["title"],
            validation_status=record["validation_status"],
            script=Script.model_validate(record["script_data"]),
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )

    def delete_script(self, script_id: str, user_id: str) -> None:
        if not self.scripts.delete_script(script_id, user_id):
            raise VNNotFoundError(f"script '{script_id}' not found")

    # --- sessions --------------------------------------------------------------

    def create_session(self, script_id: str, user_id: str, seed: int | None = None) -> VNSessionView:
        record = self._script_record(script_id, user_id)
        if record["validation_status"] != "valid":
            raise VNConflictError(f"script '{script_id}' is not valid; cannot start a session")
        script = Script.model_validate(record["script_data"])
        engine = VNEngine.new(script, seed=seed if seed is not None else random.randint(0, 2**31 - 1))
        events = engine.start()
        session_id = self._persist(engine, events, script_id, user_id, session_id=None)
        return self._to_view(session_id, record, engine, new_events=events, event_log=events)

    def get_session(self, session_id: str, user_id: str) -> VNSessionView:
        session_record = self._session_record(session_id, user_id)
        script_record = self._script_record(session_record["script_id"], user_id)
        script = Script.model_validate(script_record["script_data"])
        engine = VNEngine(script, VNRuntimeState.model_validate(session_record["runtime_state"]))
        event_log = _EVENT_LIST.validate_python(session_record["event_log"])
        return self._to_view(session_id, script_record, engine, new_events=[], event_log=event_log, narration_log=session_record["narration_log"])

    def list_sessions(self, user_id: str, script_id: str | None = None) -> list[VNSessionSummary]:
        titles = {record["id"]: record["title"] for record in self.scripts.list_scripts(user_id)}
        return [
            VNSessionSummary(
                session_id=record["id"],
                script_id=record["script_id"],
                script_title=titles.get(record["script_id"], "(deleted script)"),
                status=record["status"],
                created_at=record["created_at"],
                updated_at=record["updated_at"],
            )
            for record in self.sessions.list_sessions(user_id, script_id)
        ]

    def advance_session(self, session_id: str, action: VNAction, user_id: str) -> VNSessionView:
        session_record = self._session_record(session_id, user_id)
        script_record = self._script_record(session_record["script_id"], user_id)
        script = Script.model_validate(script_record["script_data"])
        engine = VNEngine(script, VNRuntimeState.model_validate(session_record["runtime_state"]))
        events = engine.advance(action)
        event_log = _EVENT_LIST.validate_python(session_record["event_log"]) + events
        self._persist(engine, event_log, session_record["script_id"], user_id, session_id=session_id)
        return self._to_view(session_id, script_record, engine, new_events=events, event_log=event_log, narration_log=session_record["narration_log"])

    def narrate_session(self, session_id: str, user_id: str, narrator: VNNarrator) -> Iterator[str]:
        """Stream prose for events not yet narrated. Narration is strictly read-only over the
        runtime state: only the narration log is written, after the stream completes."""
        session_record = self._session_record(session_id, user_id)
        script_record = self._script_record(session_record["script_id"], user_id)
        script = Script.model_validate(script_record["script_data"])
        engine = VNEngine(script, VNRuntimeState.model_validate(session_record["runtime_state"]))
        event_log = _EVENT_LIST.validate_python(session_record["event_log"])

        narration_log: list[dict] = list(session_record["narration_log"])
        start_index = int(narration_log[-1]["event_index"]) if narration_log else 0
        new_events = event_log[start_index:]
        if not new_events:
            raise VNConflictError("no new events to narrate")

        history = [str(entry["text"]) for entry in narration_log[-3:]]
        chunks = narrator.narrate(script.meta.title, script.meta.protagonist, new_events, engine.view(), history)

        def stream() -> Iterator[str]:
            collected: list[str] = []
            for chunk in chunks:
                collected.append(chunk)
                yield chunk
            narration_log.append({"event_index": len(event_log), "text": "".join(collected)})
            self.sessions.save_session(
                runtime_state=session_record["runtime_state"],
                event_log=session_record["event_log"],
                script_id=session_record["script_id"],
                status=session_record["status"],
                user_id=user_id,
                session_id=session_id,
                narration_log=narration_log,
            )

        return stream()

    def delete_session(self, session_id: str, user_id: str) -> None:
        if not self.sessions.delete_session(session_id, user_id):
            raise VNNotFoundError(f"session '{session_id}' not found")

    # --- helpers ----------------------------------------------------------------

    def _script_record(self, script_id: str, user_id: str) -> dict:
        record = self.scripts.get_script(script_id, user_id)
        if record is None:
            raise VNNotFoundError(f"script '{script_id}' not found")
        return record

    def _session_record(self, session_id: str, user_id: str) -> dict:
        record = self.sessions.get_session(session_id, user_id)
        if record is None:
            raise VNNotFoundError(f"session '{session_id}' not found")
        return record

    def _job_record(self, job_id: str, user_id: str) -> dict:
        record = self.jobs.get_job(job_id, user_id)
        if record is None:
            raise VNNotFoundError(f"generation job '{job_id}' not found")
        return record

    def _job_summary(self, record: dict) -> VNGenerationJobSummary:
        checkpoint = GenerationCheckpoint.model_validate(record["checkpoint"] or {})
        return VNGenerationJobSummary(
            job_id=record["id"],
            status=record["status"],
            error=record["error"],
            processor_type=record["processor_type"],
            synopsis=str(record["input_data"].get("premise", {}).get("synopsis", "")),
            outline=checkpoint.outline,
            completed_scenes=[scene.id for scene in checkpoint.scenes],
            scenes=checkpoint.scenes,
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )

    def _persist(self, engine: VNEngine, event_log: list[EngineEvent], script_id: str, user_id: str, session_id: str | None) -> str:
        return self.sessions.save_session(
            runtime_state=engine.state.model_dump(mode="json"),
            event_log=[event.model_dump(mode="json") for event in event_log],
            script_id=script_id,
            status=engine.state.status,
            user_id=user_id,
            session_id=session_id,
        )

    def _to_view(
        self,
        session_id: str,
        script_record: dict,
        engine: VNEngine,
        new_events: list[EngineEvent],
        event_log: list[EngineEvent],
        narration_log: list[dict] | None = None,
    ) -> VNSessionView:
        return VNSessionView(
            session_id=session_id,
            script_id=script_record["id"],
            script_title=script_record["title"],
            status=engine.state.status,
            view=engine.view(),
            new_events=new_events,
            event_log=event_log,
            narration_log=[VNNarrationEntry.model_validate(entry) for entry in narration_log or []],
        )
