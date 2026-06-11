"""File persistence for judge evaluations: JSON (machine-readable, baseline-loadable),
markdown report, and a guidance file feedable back into `vn-generate --guidance`."""

import json
import re
from pathlib import Path

from src.models.vn.judge import EvaluationDelta, ScriptEvaluation
from src.vn.judge.report import render_markdown


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "script"


def write_evaluation_files(
    directory: Path,
    stem: str,
    evaluation: ScriptEvaluation,
    delta: EvaluationDelta | None = None,
) -> tuple[Path, Path, Path]:
    """Write <stem>.json, <stem>.md and <stem>.guidance.txt into directory; returns the three paths.

    A taken stem gets a numeric suffix so rapid iterations never overwrite earlier reports."""
    directory.mkdir(parents=True, exist_ok=True)
    unique = stem
    counter = 2
    while (directory / f"{unique}.json").exists():
        unique = f"{stem}-{counter}"
        counter += 1
    json_path = directory / f"{unique}.json"
    md_path = directory / f"{unique}.md"
    guidance_path = directory / f"{unique}.guidance.txt"

    payload = {
        "evaluation": evaluation.model_dump(mode="json"),
        "delta": delta.model_dump(mode="json") if delta is not None else None,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(evaluation, delta), encoding="utf-8")
    guidance_path.write_text("\n".join(evaluation.regeneration_guidance) + "\n", encoding="utf-8")
    return json_path, md_path, guidance_path


def load_evaluation(path: Path) -> ScriptEvaluation:
    """Load an evaluation written by write_evaluation_files (or a bare ScriptEvaluation dump)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "evaluation" in data:
        data = data["evaluation"]
    return ScriptEvaluation.model_validate(data)
