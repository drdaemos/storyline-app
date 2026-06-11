"""Guard/condition evaluation against runtime state and visitedness.

Shared by the structural validator, the softlock walker, and the runtime engine
so all three agree on semantics by construction.
"""

from collections.abc import Set as AbstractSet

from src.models.vn.script import Condition, Guard, StateValue, VisitedCondition

StateMap = dict[str, StateValue]


def evaluate_condition(condition: Condition, state: StateMap, visited: AbstractSet[str]) -> bool:
    """Evaluate one condition. Var conditions require the var to exist in state (KeyError otherwise —
    the structural validator guarantees declared vars before anything reaches runtime)."""
    if isinstance(condition, VisitedCondition):
        return (condition.visited in visited) == condition.value
    current = state[condition.var]
    if condition.op == "==":
        return current == condition.value
    if condition.op == ">=":
        return bool(current >= condition.value)  # type: ignore[operator]
    return bool(current <= condition.value)  # type: ignore[operator]


def evaluate_guard(guard: Guard, state: StateMap, visited: AbstractSet[str]) -> bool:
    """AND semantics; empty guard is always true. [D4]"""
    return all(evaluate_condition(condition, state, visited) for condition in guard)
