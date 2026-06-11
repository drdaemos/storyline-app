"""VNScriptGenerator: orchestrates the staged pipeline.

outline (gate: scope/ids) -> per-scene mini-graphs (gate: scene structure, local repair)
-> mechanics (gate: full structural validation + scope + softlock walk).
Each stage repairs locally with bounded attempts; there is no global generate-then-repair loop.
"""

from collections.abc import Callable

from src.models.prompt_processor import PromptProcessor
from src.models.vn.input import VNInput
from src.models.vn.pipeline import GenerationCheckpoint, PipelineProgress, PipelineStage
from src.models.vn.script import Scene, Script
from src.models.vn.validation import ValidationReport
from src.vn.pipeline.mechanics import MechanicsStage
from src.vn.pipeline.outline import OutlineStage
from src.vn.pipeline.repair import DEFAULT_MAX_ATTEMPTS, run_with_repair
from src.vn.pipeline.scene_graphs import SceneGraphStage
from src.vn.softlock import check_softlocks

ProgressCallback = Callable[[PipelineProgress], None]
CheckpointCallback = Callable[[GenerationCheckpoint], None]


class VNScriptGenerator:
    def __init__(self, processor: PromptProcessor, max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> None:
        self.outline_stage = OutlineStage(processor)
        self.scene_graph_stage = SceneGraphStage(processor)
        self.mechanics_stage = MechanicsStage(processor)
        self.max_attempts = max_attempts

    def generate(
        self,
        vn_input: VNInput,
        on_progress: ProgressCallback | None = None,
        checkpoint: GenerationCheckpoint | None = None,
        on_checkpoint: CheckpointCallback | None = None,
    ) -> Script:
        """Run the pipeline, optionally resuming from a checkpoint (its outline and scenes are
        not regenerated) and reporting each passed artifact through on_checkpoint."""
        emit = self._emitter(on_progress)
        checkpoint = checkpoint or GenerationCheckpoint()

        if checkpoint.outline is not None:
            outline = checkpoint.outline
            emit("outline", "passed", detail="restored from checkpoint")
        else:
            emit("outline", "started")
            outline = run_with_repair(
                produce=lambda feedback: self.outline_stage.run(vn_input, feedback),
                gate=lambda candidate: self.outline_stage.gate(candidate, vn_input),
                max_attempts=self.max_attempts,
                on_repair=lambda report: emit("outline", "repairing", detail=self._summary(report)),
            )
            emit("outline", "passed", detail="scenes: " + ", ".join(item.id for item in outline.scenes))
            checkpoint = checkpoint.model_copy(update={"outline": outline})
            self._save(on_checkpoint, checkpoint)

        done_scenes = {scene.id: scene for scene in checkpoint.scenes}
        scenes: list[Scene] = []
        for item in outline.scenes:
            if item.id in done_scenes:
                scenes.append(done_scenes[item.id])
                emit("scene_graph", "passed", scene_id=item.id, detail="restored from checkpoint")
                continue
            emit("scene_graph", "started", scene_id=item.id)
            scene = run_with_repair(
                produce=lambda feedback, item=item: self.scene_graph_stage.run(vn_input, outline, item, feedback),
                gate=lambda candidate, item=item: self.scene_graph_stage.gate(candidate, item),
                max_attempts=self.max_attempts,
                on_repair=lambda report, item=item: emit("scene_graph", "repairing", scene_id=item.id, detail=self._summary(report)),
            )
            scenes.append(scene)
            emit("scene_graph", "passed", scene_id=item.id, detail=f"{len(scene.beats)} beats")
            checkpoint = checkpoint.model_copy(update={"scenes": [*checkpoint.scenes, scene]})
            self._save(on_checkpoint, checkpoint)

        emit("mechanics", "started")
        script = run_with_repair(
            produce=lambda feedback: self.mechanics_stage.run(vn_input, outline, scenes, feedback),
            gate=lambda candidate: self._final_gate(candidate, vn_input),
            max_attempts=self.max_attempts,
            on_repair=lambda report: emit("mechanics", "repairing", detail=self._summary(report)),
        )
        emit("mechanics", "passed")
        return script

    def _final_gate(self, script: Script, vn_input: VNInput) -> ValidationReport:
        """Structural validation + scope first; the softlock walk only runs on structurally sound scripts."""
        report = self.mechanics_stage.gate(script, vn_input)
        if report.valid:
            report = report.merged(check_softlocks(script))
        return report

    def _save(self, on_checkpoint: CheckpointCallback | None, checkpoint: GenerationCheckpoint) -> None:
        if on_checkpoint is not None:
            on_checkpoint(checkpoint)

    def _emitter(self, on_progress: ProgressCallback | None) -> Callable[..., None]:
        def emit(stage: PipelineStage, status: str, scene_id: str | None = None, detail: str = "") -> None:
            if on_progress is not None:
                on_progress(PipelineProgress.model_validate({"stage": stage, "status": status, "scene_id": scene_id, "detail": detail}))

        return emit

    def _summary(self, report: ValidationReport) -> str:
        return "; ".join(f"{issue.code}: {issue.message}" for issue in report.errors[:5])
