"""Evaluation scenarios: a starting story and the user messages played against it, one turn at a time.

Scenarios live as YAML files in a scenarios directory; a scenario may name a seed story, a directory in the seeds
directory that is copied as the starting story. Scenarios carry expectations that are checked mechanically
(which turns should write prose or update lore) and notes that tell the judge what the scenario probes.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from storyline.presets import BUNDLED_PRESETS

SCENARIO_SUFFIX = ".yaml"


class ScenarioError(ValueError):
    """Raised when scenarios cannot be found or parsed."""


class ScenarioTurn(BaseModel):
    """One user message and what the turn is expected to change."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt: str = Field(min_length=1)
    writes: bool | None = None
    """True when the turn should change script.md, False when it should leave it alone, None when either is fine."""
    updates_lore: tuple[str, ...] = ()
    """Lore files the turn should create or change."""


class Scenario(BaseModel):
    """A story to start from and the turns to play against it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: str
    turns: tuple[ScenarioTurn, ...] = Field(min_length=1)
    seed: str | None = None
    """Name of a directory in the seeds directory copied as the starting story; None starts from an empty story."""
    preset: str | None = None
    """Id of the bundled preset a seedless scenario's story is created as; None starts a co-writing story. A seed carries its own."""
    judge_notes: str = ""
    """What the scenario probes, shown to the judge."""

    @model_validator(mode="after")
    def _preset_belongs_to_a_seedless_scenario(self) -> Self:
        if self.preset is not None and self.seed is not None:
            raise ValueError(f"Scenario {self.name} names both a seed and a preset; a seed carries its own story.json.")
        if self.preset is not None and self.preset not in BUNDLED_PRESETS:
            raise ValueError(f"Scenario {self.name} names an unknown preset {self.preset!r}. Known presets: {', '.join(p.id for p in BUNDLED_PRESETS)}.")
        return self


def load_scenarios(scenarios_dir: Path, seeds_dir: Path, names: Sequence[str] = ()) -> list[Scenario]:
    """Load the named scenarios, or all of them, checking that every named seed exists."""
    available = {path.stem: path for path in sorted(scenarios_dir.glob(f"*{SCENARIO_SUFFIX}"))}
    if not available:
        raise ScenarioError(f"No scenarios found in {scenarios_dir}.")
    unknown = [name for name in names if name not in available]
    if unknown:
        raise ScenarioError(f"Unknown scenario: {', '.join(unknown)}. Available: {', '.join(available)}.")

    scenarios = [_load_scenario(available[name]) for name in (names or tuple(available))]
    for scenario in scenarios:
        if scenario.seed is not None and not (seeds_dir / scenario.seed).is_dir():
            raise ScenarioError(f"Scenario {scenario.name} names a missing seed: {seeds_dir / scenario.seed}")
    return scenarios


def _load_scenario(path: Path) -> Scenario:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ScenarioError(f"{path} must contain a mapping.")
        return Scenario.model_validate({"name": path.stem, **data})
    except (yaml.YAMLError, ValidationError) as error:
        raise ScenarioError(f"Invalid scenario {path}: {error}") from error
