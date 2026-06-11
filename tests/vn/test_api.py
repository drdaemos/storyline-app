"""M5: VN API endpoints — import, validate, play to an ending entirely over HTTP."""

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.fastapi_server import app
from src.models.vn.pipeline import SceneOutlineItem, ScriptOutline
from src.vn.api import get_vn_service
from src.vn.registry import VNGenerationJobRegistry, VNScriptRegistry, VNSessionRegistry
from src.vn.service import VNService
from tests.vn.test_pipeline import FakeProcessor, make_mechanics_patch


@pytest.fixture(scope="module", autouse=True)
def disable_auth():
    os.environ["AUTH_ENABLED"] = "false"
    yield


class TestVNApi:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        service = VNService(
            VNScriptRegistry(memory_dir=Path(self.temp_dir)),
            VNSessionRegistry(memory_dir=Path(self.temp_dir)),
            VNGenerationJobRegistry(memory_dir=Path(self.temp_dir)),
        )
        app.dependency_overrides[get_vn_service] = lambda: service
        self.client = TestClient(app)

    def teardown_method(self):
        app.dependency_overrides.pop(get_vn_service, None)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _import(self, script_data: dict) -> str:
        response = self.client.post("/api/vn/scripts", json={"script": script_data})
        assert response.status_code == 200, response.text
        return response.json()["script_id"]

    def test_validate_endpoint_reports_issues(self, locked_granary_data):
        broken = dict(locked_granary_data)
        broken["start_scene"] = "sc_ghost"
        response = self.client.post("/api/vn/scripts/validate", json={"script": broken})
        assert response.status_code == 200
        codes = {issue["code"] for issue in response.json()["issues"]}
        assert "unknown_start_scene" in codes

    def test_malformed_script_rejected_as_422(self, locked_granary_data):
        broken = dict(locked_granary_data)
        broken["scenes"] = []
        response = self.client.post("/api/vn/scripts/validate", json={"script": broken})
        assert response.status_code == 422

    def test_import_list_get_delete(self, locked_granary_data):
        script_id = self._import(locked_granary_data)

        scripts = self.client.get("/api/vn/scripts").json()
        assert [s["id"] for s in scripts] == [script_id]
        assert scripts[0]["validation_status"] == "valid"
        assert scripts[0]["scene_count"] == 3
        assert scripts[0]["ending_count"] == 2

        detail = self.client.get(f"/api/vn/scripts/{script_id}").json()
        assert detail["script"]["meta"]["title"] == "The Locked Granary"

        assert self.client.delete(f"/api/vn/scripts/{script_id}").status_code == 200
        assert self.client.get(f"/api/vn/scripts/{script_id}").status_code == 404

    def test_invalid_script_cannot_start_session(self, locked_granary_data):
        broken = dict(locked_granary_data)
        broken["start_scene"] = "sc_ghost"
        script_id = self._import(broken)
        response = self.client.post("/api/vn/sessions", json={"script_id": script_id})
        assert response.status_code == 409

    def test_full_playthrough_over_http(self, locked_granary_data):
        script_id = self._import(locked_granary_data)

        # start: runs to the extension offer on b_approach
        response = self.client.post("/api/vn/sessions", json={"script_id": script_id, "seed": 1})
        assert response.status_code == 200, response.text
        session = response.json()
        session_id = session["session_id"]
        assert session["view"]["pending"]["kind"] == "extension"
        assert session["new_events"][0]["type"] == "scene_entered"

        def advance(action: dict) -> dict:
            response = self.client.post(f"/api/vn/sessions/{session_id}/advance", json={"action": action})
            assert response.status_code == 200, response.text
            return response.json()

        session = advance({"type": "proceed"})
        options = session["view"]["pending"]["options"]
        assert [o["intent"] for o in options] == ["Persuade him", "Slip past while he is distracted"]

        session = advance({"type": "choose", "option_index": 0})  # persuade -> trust 1
        session = advance({"type": "choose", "option_index": 2})  # vouched -> has_key -> forced sc_reckoning
        assert session["view"]["beat_id"] == "b_confront"
        assert session["view"]["vars"]["has_key"] is True

        session = advance({"type": "choose", "option_index": 0})  # tell the truth
        assert session["status"] == "ended"
        assert session["view"]["ending_id"] == "end_bargain"

        # event log accumulated and session retrievable after completion
        fetched = self.client.get(f"/api/vn/sessions/{session_id}").json()
        assert fetched["status"] == "ended"
        event_types = [event["type"] for event in fetched["event_log"]]
        assert event_types[0] == "scene_entered"
        assert event_types[-1] == "ending_reached"

    def test_session_survives_reload_mid_playthrough(self, locked_granary_data):
        script_id = self._import(locked_granary_data)
        session_id = self.client.post("/api/vn/sessions", json={"script_id": script_id, "seed": 5}).json()["session_id"]
        self.client.post(f"/api/vn/sessions/{session_id}/advance", json={"action": {"type": "proceed"}})

        # fetch (fresh engine built from persisted state) and keep playing
        fetched = self.client.get(f"/api/vn/sessions/{session_id}").json()
        assert fetched["view"]["pending"]["kind"] == "choice"
        response = self.client.post(f"/api/vn/sessions/{session_id}/advance", json={"action": {"type": "choose", "option_index": 0}})
        assert response.status_code == 200
        assert response.json()["view"]["vars"]["guard_trust"] == 1

    def test_invalid_action_returns_400(self, locked_granary_data):
        script_id = self._import(locked_granary_data)
        session_id = self.client.post("/api/vn/sessions", json={"script_id": script_id}).json()["session_id"]
        response = self.client.post(f"/api/vn/sessions/{session_id}/advance", json={"action": {"type": "choose", "option_index": 0}})
        assert response.status_code == 400  # extension offer pending; choose is invalid

    def test_unknown_session_404(self):
        assert self.client.get("/api/vn/sessions/nope").status_code == 404

    def test_list_sessions(self, locked_granary_data):
        script_id = self._import(locked_granary_data)
        self.client.post("/api/vn/sessions", json={"script_id": script_id})
        sessions = self.client.get("/api/vn/sessions").json()
        assert len(sessions) == 1
        assert sessions[0]["script_title"] == "The Locked Granary"
        assert sessions[0]["status"] == "running"

    def test_generate_streams_progress_and_saves(self, locked_granary, monkeypatch):
        """SSE generation endpoint with a fully mocked pipeline (no LLM calls)."""
        outline = ScriptOutline(
            title="The Locked Granary",
            start_scene="sc_gate",
            scenes=[
                SceneOutlineItem(id="sc_gate", intent="x", synopsis="s", exit_mode="open"),
                SceneOutlineItem(id="sc_granary", intent="x", synopsis="s", exit_mode="directed"),
                SceneOutlineItem(id="sc_reckoning", intent="x", synopsis="s", exit_mode="ending", ending_ids=["end_bargain", "end_flight"]),
            ],
        )
        processor = FakeProcessor([outline, *locked_granary.scenes, make_mechanics_patch(locked_granary)])
        monkeypatch.setattr("src.vn.api.PromptProcessorFactory.create_processor", lambda processor_type: processor)

        request = {
            "input": {
                "characters": [{"name": "Mara", "protagonist": True}],
                "premise": {"synopsis": "s", "protagonist_goal": "g", "scope": {"target_scenes": 3, "target_endings": 2}},
            },
        }
        response = self.client.post("/api/vn/scripts/generate", json=request)
        assert response.status_code == 200

        events = [json.loads(line.removeprefix("data: ")) for line in response.text.splitlines() if line.startswith("data: ")]
        types = [event["type"] for event in events]
        assert types[0] == "started"
        assert events[0]["job_id"]
        assert types[1:-1] == ["progress"] * (len(types) - 2)
        assert types[-1] == "complete"
        assert events[-1]["validation_status"] == "valid"

        # generated script was persisted and is playable
        script_id = events[-1]["script_id"]
        detail = self.client.get(f"/api/vn/scripts/{script_id}").json()
        assert detail["validation_status"] == "valid"
        session = self.client.post("/api/vn/sessions", json={"script_id": script_id})
        assert session.status_code == 200

        # job removed after success
        assert self.client.get("/api/vn/generation-jobs").json() == []

    def test_failed_generation_keeps_resumable_job(self, locked_granary, monkeypatch):
        """A failure mid-pipeline persists the checkpoint; resume finishes without redoing passed stages."""
        outline = ScriptOutline(
            title="The Locked Granary",
            start_scene="sc_gate",
            scenes=[
                SceneOutlineItem(id="sc_gate", intent="x", synopsis="s", exit_mode="open"),
                SceneOutlineItem(id="sc_granary", intent="x", synopsis="s", exit_mode="directed"),
                SceneOutlineItem(id="sc_reckoning", intent="x", synopsis="s", exit_mode="ending", ending_ids=["end_bargain", "end_flight"]),
            ],
        )
        # outline + first scene pass, then the second scene fails all repair attempts
        failing = FakeProcessor([outline, locked_granary.scenes[0], "garbage", "garbage", "garbage"])
        monkeypatch.setattr("src.vn.api.PromptProcessorFactory.create_processor", lambda processor_type: failing)
        request = {
            "input": {
                "characters": [{"name": "Mara", "protagonist": True}],
                "premise": {"synopsis": "s", "protagonist_goal": "g", "scope": {"target_scenes": 3, "target_endings": 2}},
            },
        }
        response = self.client.post("/api/vn/scripts/generate", json=request)
        events = [json.loads(line.removeprefix("data: ")) for line in response.text.splitlines() if line.startswith("data: ")]
        assert events[-1]["type"] == "error"
        job_id = events[-1]["job_id"]

        # the job lists what was generated so far
        jobs = self.client.get("/api/vn/generation-jobs").json()
        assert len(jobs) == 1
        assert jobs[0]["job_id"] == job_id
        assert jobs[0]["status"] == "failed"
        assert jobs[0]["outline"]["start_scene"] == "sc_gate"
        assert jobs[0]["completed_scenes"] == ["sc_gate"]
        assert jobs[0]["scenes"][0]["id"] == "sc_gate"
        assert jobs[0]["scenes"][0]["beats"][0]["intent"] == locked_granary.scenes[0].beats[0].intent

        # resume with a working processor: only the missing scenes and mechanics run
        resuming = FakeProcessor([*locked_granary.scenes[1:], make_mechanics_patch(locked_granary)])
        monkeypatch.setattr("src.vn.api.PromptProcessorFactory.create_processor", lambda processor_type: resuming)
        response = self.client.post(f"/api/vn/generation-jobs/{job_id}/resume")
        events = [json.loads(line.removeprefix("data: ")) for line in response.text.splitlines() if line.startswith("data: ")]
        assert events[-1]["type"] == "complete"
        assert events[-1]["validation_status"] == "valid"
        assert self.client.get("/api/vn/generation-jobs").json() == []

    def test_deleting_a_job_discards_it(self, locked_granary, monkeypatch):
        failing = FakeProcessor(["garbage", "garbage", "garbage"])
        monkeypatch.setattr("src.vn.api.PromptProcessorFactory.create_processor", lambda processor_type: failing)
        request = {
            "input": {
                "characters": [{"name": "Mara", "protagonist": True}],
                "premise": {"synopsis": "s", "protagonist_goal": "g", "scope": {"target_scenes": 1, "target_endings": 1}},
            },
        }
        response = self.client.post("/api/vn/scripts/generate", json=request)
        events = [json.loads(line.removeprefix("data: ")) for line in response.text.splitlines() if line.startswith("data: ")]
        job_id = events[-1]["job_id"]
        assert self.client.delete(f"/api/vn/generation-jobs/{job_id}").status_code == 200
        assert self.client.get("/api/vn/generation-jobs").json() == []
        assert self.client.post(f"/api/vn/generation-jobs/{job_id}/resume").status_code == 404
