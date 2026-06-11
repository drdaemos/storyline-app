"""CLI flows for VN generation and review: persistence, resume, guidance, baselines.

The DB is a temporary SQLite (no mocking); only the prompt processor is faked.
"""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from src import cli as cli_module
from src.cli import cli
from src.models.prompt_processor_factory import PromptProcessorFactory
from src.models.vn import Script
from src.models.vn.pipeline import SceneOutlineItem, ScriptOutline
from src.vn.judge.storage import load_evaluation
from src.vn.registry import VNGenerationJobRegistry, VNScriptRegistry, VNSessionRegistry
from src.vn.service import VNService
from tests.vn.helpers import FakeProcessor
from tests.vn.test_judge import make_llm_lens_review
from tests.vn.test_pipeline import make_llm_mechanics_patch, scenes_as_llm_scenes

VN_INPUT = {
    "characters": [{"name": "Mara", "background": "a thief", "protagonist": True}],
    "setting": {"world_description": "a small town"},
    "rules": "low fantasy",
    "premise": {
        "synopsis": "steal the ledger from the granary",
        "protagonist_goal": "clear her name",
        "scope": {"target_scenes": 3, "target_endings": 2},
    },
}


def make_outline() -> ScriptOutline:
    return ScriptOutline(
        title="The Locked Granary",
        start_scene="sc_gate",
        scenes=[
            SceneOutlineItem(id="sc_gate", intent="Talk your way past the granary guard", synopsis="Mara gets past the guard", exit_mode="open"),
            SceneOutlineItem(id="sc_granary", intent="Search the granary for the ledger", synopsis="Mara searches", exit_mode="directed"),
            SceneOutlineItem(id="sc_reckoning", intent="Face the granary master", synopsis="Confrontation", exit_mode="ending", ending_ids=["end_bargain", "end_flight"]),
        ],
    )


def generation_outputs(script: Script) -> list:
    return [make_outline(), *scenes_as_llm_scenes(script), make_llm_mechanics_patch(script)]


@pytest.fixture
def service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> VNService:
    instance = VNService(
        VNScriptRegistry(memory_dir=tmp_path / "db"),
        VNSessionRegistry(memory_dir=tmp_path / "db"),
        VNGenerationJobRegistry(memory_dir=tmp_path / "db"),
    )
    monkeypatch.setattr(cli_module, "build_vn_service", lambda: instance)
    return instance


@pytest.fixture
def use_processor(monkeypatch: pytest.MonkeyPatch):
    def install(processor: FakeProcessor) -> FakeProcessor:
        monkeypatch.setattr(PromptProcessorFactory, "create_processor", staticmethod(lambda processor_type: processor))
        return processor

    return install


@pytest.fixture
def input_file(tmp_path: Path) -> Path:
    path = tmp_path / "input.json"
    path.write_text(json.dumps(VN_INPUT), encoding="utf-8")
    return path


class TestVnGenerateCommand:
    def test_generates_and_persists_script(self, service: VNService, use_processor, input_file: Path, tmp_path: Path, locked_granary: Script):
        use_processor(FakeProcessor(generation_outputs(locked_granary)))
        output = tmp_path / "script.json"
        result = CliRunner().invoke(cli, ["vn-generate", str(input_file), "--output", str(output)])

        assert result.exit_code == 0, result.output
        scripts = service.list_scripts("cli")
        assert len(scripts) == 1
        assert scripts[0].validation_status == "valid"
        assert service.list_generation_jobs("cli") == []  # job removed on success
        assert Script.model_validate(json.loads(output.read_text(encoding="utf-8"))) == locked_granary

    def test_failed_generation_keeps_resumable_job(self, service: VNService, use_processor, input_file: Path, locked_granary: Script):
        use_processor(FakeProcessor(["bad", "bad", "bad"]))  # outline never parses
        result = CliRunner().invoke(cli, ["vn-generate", str(input_file)])

        assert result.exit_code == 1
        jobs = service.list_generation_jobs("cli")
        assert len(jobs) == 1
        assert jobs[0].status == "failed"
        assert "--resume" in result.output

    def test_resume_completes_failed_job(self, service: VNService, use_processor, input_file: Path, locked_granary: Script):
        use_processor(FakeProcessor(["bad", "bad", "bad"]))
        CliRunner().invoke(cli, ["vn-generate", str(input_file)])
        job_id = service.list_generation_jobs("cli")[0].job_id

        use_processor(FakeProcessor(generation_outputs(locked_granary)))
        result = CliRunner().invoke(cli, ["vn-generate", "--resume", job_id])

        assert result.exit_code == 0, result.output
        assert service.list_generation_jobs("cli") == []
        assert len(service.list_scripts("cli")) == 1

    def test_guidance_is_appended_to_rules(self, service: VNService, use_processor, input_file: Path, tmp_path: Path, locked_granary: Script):
        guidance = tmp_path / "guidance.txt"
        guidance.write_text("[sc_gate] escalate the guard's suspicion", encoding="utf-8")
        use_processor(FakeProcessor(generation_outputs(locked_granary)))
        result = CliRunner().invoke(cli, ["vn-generate", str(input_file), "--guidance", str(guidance)])

        assert result.exit_code == 0, result.output
        script_id = service.list_scripts("cli")[0].id
        stored_input = service.get_script_input(script_id, "cli")
        assert stored_input is not None
        assert "low fantasy" in stored_input.rules
        assert "escalate the guard's suspicion" in stored_input.rules

    def test_requires_input_or_resume(self, service: VNService):
        result = CliRunner().invoke(cli, ["vn-generate"])
        assert result.exit_code != 0
        assert "INPUT_FILE or --resume" in result.output


class TestVnReviewCommand:
    def review_outputs(self, script: Script) -> list:
        return [make_llm_lens_review("playwright", script), make_llm_lens_review("director", script)]

    def test_reviews_script_file_and_writes_reports(self, service: VNService, use_processor, tmp_path: Path, locked_granary: Script, locked_granary_data: dict):
        script_file = tmp_path / "granary.json"
        script_file.write_text(json.dumps(locked_granary_data), encoding="utf-8")
        use_processor(FakeProcessor(self.review_outputs(locked_granary)))
        out_dir = tmp_path / "evals"
        result = CliRunner().invoke(cli, ["vn-review", str(script_file), "--output-dir", str(out_dir)])

        assert result.exit_code == 0, result.output
        json_files = list(out_dir.glob("*.json"))
        assert len(json_files) == 1
        evaluation = load_evaluation(json_files[0])
        assert evaluation.script_title == locked_granary.meta.title
        assert len(list(out_dir.glob("*.md"))) == 1
        assert len(list(out_dir.glob("*.guidance.txt"))) == 1

    def test_reviews_persisted_script_by_id(self, service: VNService, use_processor, tmp_path: Path, locked_granary: Script):
        script_id, _, _ = service.import_script(locked_granary, user_id="cli")
        use_processor(FakeProcessor(self.review_outputs(locked_granary)))
        out_dir = tmp_path / "evals"
        result = CliRunner().invoke(cli, ["vn-review", script_id, "--output-dir", str(out_dir)])

        assert result.exit_code == 0, result.output
        assert locked_granary.meta.title in result.output

    def test_baseline_produces_progress_recommendation(self, service: VNService, use_processor, tmp_path: Path, locked_granary: Script, locked_granary_data: dict):
        script_file = tmp_path / "granary.json"
        script_file.write_text(json.dumps(locked_granary_data), encoding="utf-8")
        out_dir = tmp_path / "evals"

        use_processor(FakeProcessor(self.review_outputs(locked_granary)))
        CliRunner().invoke(cli, ["vn-review", str(script_file), "--output-dir", str(out_dir)])
        baseline = next(iter(out_dir.glob("*.json")))

        use_processor(FakeProcessor([make_llm_lens_review("playwright", locked_granary, score=4), make_llm_lens_review("director", locked_granary, score=4)]))
        result = CliRunner().invoke(cli, ["vn-review", str(script_file), "--output-dir", str(out_dir), "--baseline", str(baseline), "--target-score", "4.0"])

        assert result.exit_code == 0, result.output
        assert "stop_target_reached" in result.output

    def test_unknown_script_id_fails_cleanly(self, service: VNService, use_processor, locked_granary: Script):
        use_processor(FakeProcessor([]))
        result = CliRunner().invoke(cli, ["vn-review", "no-such-id"])
        assert result.exit_code != 0
        assert "not found" in result.output
