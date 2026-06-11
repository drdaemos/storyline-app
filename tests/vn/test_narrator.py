"""M7: narration adapter — streaming, narration-log bookkeeping, and the read-only boundary."""

import os
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.fastapi_server import app
from src.models.prompt_processor import PromptProcessor
from src.models.vn import Script, VNAction
from src.vn.api import get_vn_service
from src.vn.narrator import VNNarrator
from src.vn.registry import VNGenerationJobRegistry, VNScriptRegistry, VNSessionRegistry
from src.vn.service import VNConflictError, VNService


class FakeNarrationProcessor(PromptProcessor):
    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks
        self.stream_calls = 0

    def get_processor_specific_prompt(self) -> str:
        return ""

    def respond_with_stream(self, prompt, user_prompt, conversation_history=None, max_tokens=None, reasoning=False):
        self.stream_calls += 1
        return iter(self.chunks)

    def respond_with_text(self, prompt, user_prompt, conversation_history=None, max_tokens=None, reasoning=False):
        raise NotImplementedError

    def respond_with_model(self, prompt, user_prompt, output_type, conversation_history=None, max_tokens=None, reasoning=False):
        raise NotImplementedError


class TestNarration:
    @pytest.fixture(autouse=True)
    def setup(self, locked_granary: Script):
        self.temp_dir = tempfile.mkdtemp()
        self.service = VNService(VNScriptRegistry(memory_dir=Path(self.temp_dir)), VNSessionRegistry(memory_dir=Path(self.temp_dir)), VNGenerationJobRegistry(memory_dir=Path(self.temp_dir)))
        script_id, _, _ = self.service.import_script(locked_granary, "u1")
        self.session = self.service.create_session(script_id, "u1", seed=1)
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _narrate(self, chunks: list[str] | None = None) -> str:
        processor = FakeNarrationProcessor(chunks or ["The gate ", "looms."])
        narrator = VNNarrator(processor)
        return "".join(self.service.narrate_session(self.session.session_id, "u1", narrator))

    def test_streams_prose_chunks(self):
        assert self._narrate(["A", "B", "C"]) == "ABC"

    def test_narration_does_not_change_runtime_state(self):
        before = self.service.get_session(self.session.session_id, "u1")
        self._narrate()
        after = self.service.get_session(self.session.session_id, "u1")
        assert after.view == before.view
        assert after.event_log == before.event_log
        assert after.status == before.status

    def test_renarrating_without_new_events_conflicts(self):
        self._narrate()
        with pytest.raises(VNConflictError, match="no new events"):
            self._narrate()

    def test_narration_resumes_after_advance(self):
        self._narrate()
        self.service.advance_session(self.session.session_id, VNAction(type="proceed"), "u1")
        assert self._narrate(["Beyond the gate."]) == "Beyond the gate."

    def test_structural_outcome_identical_with_and_without_narration(self, locked_granary: Script):
        """Same actions + same seed produce the same state whether or not narration runs in between."""
        script_id, _, _ = self.service.import_script(locked_granary, "u2")
        plain = self.service.create_session(script_id, "u2", seed=9)
        self.service.advance_session(plain.session_id, VNAction(type="proceed"), "u2")
        result_plain = self.service.advance_session(plain.session_id, VNAction(type="choose", option_index=1), "u2")

        narrated = self.service.create_session(script_id, "u2", seed=9)
        narrator = VNNarrator(FakeNarrationProcessor(["..."]))
        "".join(self.service.narrate_session(narrated.session_id, "u2", narrator))
        self.service.advance_session(narrated.session_id, VNAction(type="proceed"), "u2")
        result_narrated = self.service.advance_session(narrated.session_id, VNAction(type="choose", option_index=1), "u2")

        assert result_narrated.view.vars == result_plain.view.vars
        assert result_narrated.view.beat_id == result_plain.view.beat_id


class TestNarrateEndpoint:
    def test_narrate_over_http(self, locked_granary_data, monkeypatch):
        os.environ["AUTH_ENABLED"] = "false"
        temp_dir = tempfile.mkdtemp()
        service = VNService(VNScriptRegistry(memory_dir=Path(temp_dir)), VNSessionRegistry(memory_dir=Path(temp_dir)), VNGenerationJobRegistry(memory_dir=Path(temp_dir)))
        app.dependency_overrides[get_vn_service] = lambda: service
        monkeypatch.setattr("src.vn.api.PromptProcessorFactory.create_processor", lambda processor_type: FakeNarrationProcessor(["Night falls."]))
        try:
            client = TestClient(app)
            script_id = client.post("/api/vn/scripts", json={"script": locked_granary_data}).json()["script_id"]
            session_id = client.post("/api/vn/sessions", json={"script_id": script_id}).json()["session_id"]

            response = client.post(f"/api/vn/sessions/{session_id}/narrate", json={})
            assert response.status_code == 200
            assert response.text == "Night falls."

            # nothing new -> 409
            assert client.post(f"/api/vn/sessions/{session_id}/narrate", json={}).status_code == 409
        finally:
            app.dependency_overrides.pop(get_vn_service, None)
            shutil.rmtree(temp_dir, ignore_errors=True)
