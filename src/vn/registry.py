"""Persistence for VN scripts and play sessions (SQLAlchemy, per-user scoped)."""

import uuid
from datetime import datetime
from pathlib import Path

from src.memory.database_config import DatabaseConfig
from src.memory.db_models import VNGenerationJob, VNScript, VNSession


class VNScriptRegistry:
    """Stores generated/imported VN scripts."""

    def __init__(self, memory_dir: Path | None = None) -> None:
        self.db_config = DatabaseConfig(memory_dir)

    def save_script(
        self,
        script_data: dict,
        title: str,
        user_id: str,
        script_id: str | None = None,
        input_data: dict | None = None,
        validation_status: str = "unvalidated",
        schema_version: int = 1,
    ) -> str:
        if script_id is None:
            script_id = str(uuid.uuid4())
        with self.db_config.create_session() as session:
            existing = session.query(VNScript).filter(VNScript.id == script_id, VNScript.user_id == user_id).first()
            if existing:
                existing.script_data = script_data
                existing.title = title
                existing.input_data = input_data
                existing.validation_status = validation_status
                existing.schema_version = schema_version
                existing.updated_at = datetime.now()
            else:
                session.add(
                    VNScript(
                        id=script_id,
                        title=title,
                        script_data=script_data,
                        input_data=input_data,
                        schema_version=schema_version,
                        validation_status=validation_status,
                        user_id=user_id,
                    )
                )
            session.commit()
            return script_id

    def get_script(self, script_id: str, user_id: str) -> dict | None:
        with self.db_config.create_session() as session:
            record = session.query(VNScript).filter(VNScript.id == script_id, VNScript.user_id == user_id).first()
            if record is None:
                return None
            return self._to_dict(record)

    def list_scripts(self, user_id: str) -> list[dict]:
        with self.db_config.create_session() as session:
            records = session.query(VNScript).filter(VNScript.user_id == user_id).order_by(VNScript.updated_at.desc()).all()
            return [self._to_dict(record) for record in records]

    def delete_script(self, script_id: str, user_id: str) -> bool:
        with self.db_config.create_session() as session:
            count = session.query(VNScript).filter(VNScript.id == script_id, VNScript.user_id == user_id).delete()
            session.commit()
            return count > 0

    def _to_dict(self, record: VNScript) -> dict:
        return {
            "id": record.id,
            "title": record.title,
            "script_data": record.script_data,
            "input_data": record.input_data,
            "schema_version": record.schema_version,
            "validation_status": record.validation_status,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
        }

    def close(self) -> None:
        self.db_config.dispose()


class VNSessionRegistry:
    """Stores play sessions: serialized runtime state plus the accumulated event log."""

    def __init__(self, memory_dir: Path | None = None) -> None:
        self.db_config = DatabaseConfig(memory_dir)

    def save_session(
        self,
        runtime_state: dict,
        event_log: list[dict],
        script_id: str,
        status: str,
        user_id: str,
        session_id: str | None = None,
        narration_log: list[dict] | None = None,
    ) -> str:
        if session_id is None:
            session_id = str(uuid.uuid4())
        with self.db_config.create_session() as session:
            existing = session.query(VNSession).filter(VNSession.id == session_id, VNSession.user_id == user_id).first()
            if existing:
                existing.runtime_state = runtime_state
                existing.event_log = event_log
                existing.status = status
                if narration_log is not None:
                    existing.narration_log = narration_log
                existing.updated_at = datetime.now()
            else:
                session.add(
                    VNSession(
                        id=session_id,
                        script_id=script_id,
                        runtime_state=runtime_state,
                        event_log=event_log,
                        narration_log=narration_log or [],
                        status=status,
                        user_id=user_id,
                    )
                )
            session.commit()
            return session_id

    def get_session(self, session_id: str, user_id: str) -> dict | None:
        with self.db_config.create_session() as session:
            record = session.query(VNSession).filter(VNSession.id == session_id, VNSession.user_id == user_id).first()
            if record is None:
                return None
            return self._to_dict(record)

    def list_sessions(self, user_id: str, script_id: str | None = None) -> list[dict]:
        with self.db_config.create_session() as session:
            query = session.query(VNSession).filter(VNSession.user_id == user_id)
            if script_id is not None:
                query = query.filter(VNSession.script_id == script_id)
            records = query.order_by(VNSession.updated_at.desc()).all()
            return [self._to_dict(record) for record in records]

    def delete_session(self, session_id: str, user_id: str) -> bool:
        with self.db_config.create_session() as session:
            count = session.query(VNSession).filter(VNSession.id == session_id, VNSession.user_id == user_id).delete()
            session.commit()
            return count > 0

    def _to_dict(self, record: VNSession) -> dict:
        return {
            "id": record.id,
            "script_id": record.script_id,
            "runtime_state": record.runtime_state,
            "event_log": record.event_log,
            "narration_log": record.narration_log,
            "status": record.status,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
        }

    def close(self) -> None:
        self.db_config.dispose()


class VNGenerationJobRegistry:
    """Stores in-flight/failed generation runs: input, processor, and the checkpointed artifacts."""

    def __init__(self, memory_dir: Path | None = None) -> None:
        self.db_config = DatabaseConfig(memory_dir)

    def save_job(
        self,
        input_data: dict,
        processor_type: str,
        checkpoint: dict,
        status: str,
        user_id: str,
        job_id: str | None = None,
        error: str | None = None,
    ) -> str:
        if job_id is None:
            job_id = str(uuid.uuid4())
        with self.db_config.create_session() as session:
            existing = session.query(VNGenerationJob).filter(VNGenerationJob.id == job_id, VNGenerationJob.user_id == user_id).first()
            if existing:
                existing.input_data = input_data
                existing.processor_type = processor_type
                existing.checkpoint = checkpoint
                existing.status = status
                existing.error = error
                existing.updated_at = datetime.now()
            else:
                session.add(
                    VNGenerationJob(
                        id=job_id,
                        input_data=input_data,
                        processor_type=processor_type,
                        checkpoint=checkpoint,
                        status=status,
                        error=error,
                        user_id=user_id,
                    )
                )
            session.commit()
            return job_id

    def get_job(self, job_id: str, user_id: str) -> dict | None:
        with self.db_config.create_session() as session:
            record = session.query(VNGenerationJob).filter(VNGenerationJob.id == job_id, VNGenerationJob.user_id == user_id).first()
            if record is None:
                return None
            return self._to_dict(record)

    def list_jobs(self, user_id: str) -> list[dict]:
        with self.db_config.create_session() as session:
            records = session.query(VNGenerationJob).filter(VNGenerationJob.user_id == user_id).order_by(VNGenerationJob.updated_at.desc()).all()
            return [self._to_dict(record) for record in records]

    def delete_job(self, job_id: str, user_id: str) -> bool:
        with self.db_config.create_session() as session:
            count = session.query(VNGenerationJob).filter(VNGenerationJob.id == job_id, VNGenerationJob.user_id == user_id).delete()
            session.commit()
            return count > 0

    def _to_dict(self, record: VNGenerationJob) -> dict:
        return {
            "id": record.id,
            "input_data": record.input_data,
            "processor_type": record.processor_type,
            "checkpoint": record.checkpoint,
            "status": record.status,
            "error": record.error,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
        }

    def close(self) -> None:
        self.db_config.dispose()
