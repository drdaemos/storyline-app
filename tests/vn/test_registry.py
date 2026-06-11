"""M5: VN script/session registries against a temporary SQLite database."""

import shutil
import tempfile
from pathlib import Path

import pytest

from src.vn.registry import VNScriptRegistry, VNSessionRegistry


class TestVNScriptRegistry:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.temp_dir = tempfile.mkdtemp()
        self.registry = VNScriptRegistry(memory_dir=Path(self.temp_dir))
        yield
        self.registry.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_get_round_trip(self, locked_granary_data):
        script_id = self.registry.save_script(locked_granary_data, title="The Locked Granary", user_id="u1", validation_status="valid")
        record = self.registry.get_script(script_id, "u1")
        assert record is not None
        assert record["title"] == "The Locked Granary"
        assert record["validation_status"] == "valid"
        assert record["script_data"] == locked_granary_data

    def test_user_scoping(self, locked_granary_data):
        script_id = self.registry.save_script(locked_granary_data, title="T", user_id="u1")
        assert self.registry.get_script(script_id, "u2") is None
        assert self.registry.list_scripts("u2") == []

    def test_update_existing(self, locked_granary_data):
        script_id = self.registry.save_script(locked_granary_data, title="T", user_id="u1")
        self.registry.save_script(locked_granary_data, title="T2", user_id="u1", script_id=script_id, validation_status="valid")
        record = self.registry.get_script(script_id, "u1")
        assert record["title"] == "T2"
        assert len(self.registry.list_scripts("u1")) == 1

    def test_delete(self, locked_granary_data):
        script_id = self.registry.save_script(locked_granary_data, title="T", user_id="u1")
        assert self.registry.delete_script(script_id, "u1") is True
        assert self.registry.get_script(script_id, "u1") is None
        assert self.registry.delete_script(script_id, "u1") is False


class TestVNSessionRegistry:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.temp_dir = tempfile.mkdtemp()
        self.registry = VNSessionRegistry(memory_dir=Path(self.temp_dir))
        yield
        self.registry.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    STATE = {"vars": {"x": 1}, "visited": ["sc_a"], "current_beat": "b1", "phase": "resolve", "status": "running", "ending_id": None, "seed": 7, "roll_count": 0, "action_log": []}

    def test_save_and_get_round_trip(self):
        session_id = self.registry.save_session(self.STATE, [{"type": "scene_entered", "scene_id": "sc_a", "intent": "x"}], script_id="s1", status="running", user_id="u1")
        record = self.registry.get_session(session_id, "u1")
        assert record["runtime_state"] == self.STATE
        assert record["event_log"][0]["type"] == "scene_entered"
        assert record["status"] == "running"

    def test_list_filtered_by_script(self):
        self.registry.save_session(self.STATE, [], script_id="s1", status="running", user_id="u1")
        self.registry.save_session(self.STATE, [], script_id="s2", status="ended", user_id="u1")
        assert len(self.registry.list_sessions("u1")) == 2
        assert len(self.registry.list_sessions("u1", script_id="s1")) == 1

    def test_user_scoping(self):
        session_id = self.registry.save_session(self.STATE, [], script_id="s1", status="running", user_id="u1")
        assert self.registry.get_session(session_id, "u2") is None
