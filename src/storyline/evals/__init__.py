"""Scenario evaluations of the writer agent: mechanical checks, a behaviour judge and pairwise craft comparison."""

from storyline.evals.scenarios import Scenario, ScenarioError, ScenarioTurn, load_scenarios
from storyline.evals.service import EvalError, EvalService, RunRequest

DEFAULT_JUDGE_MODEL_NAME = "openrouter:anthropic/claude-sonnet-5.5"
"""LitBench found Claude the strongest off-the-shelf creative-writing judge; it is also outside the default writer's family."""

__all__ = (
    "DEFAULT_JUDGE_MODEL_NAME",
    "EvalError",
    "EvalService",
    "RunRequest",
    "Scenario",
    "ScenarioError",
    "ScenarioTurn",
    "load_scenarios",
)
