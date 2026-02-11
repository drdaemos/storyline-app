from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.simulation.contracts import StateOp


class StateOpError(ValueError):
    """Raised when state operation cannot be applied."""


def apply_state_ops(state: dict[str, Any], ops: list[StateOp]) -> dict[str, Any]:
    next_state = deepcopy(state)
    for op in ops:
        _apply_one(next_state, op)
    return next_state


def _apply_one(root: dict[str, Any], op: StateOp) -> None:
    parent, key = _resolve_parent_and_key(root, op.path)
    if op.op == "set":
        parent[key] = op.value
        return
    current = parent.get(key)
    if op.op == "increment":
        if not isinstance(current, (int, float)):
            raise StateOpError(f"path '{op.path}' is not numeric")
        if not isinstance(op.value, (int, float)):
            raise StateOpError(f"increment value for '{op.path}' must be numeric")
        parent[key] = current + op.value
        return
    if op.op == "decrement":
        if not isinstance(current, (int, float)):
            raise StateOpError(f"path '{op.path}' is not numeric")
        if not isinstance(op.value, (int, float)):
            raise StateOpError(f"decrement value for '{op.path}' must be numeric")
        parent[key] = current - op.value
        return
    if op.op == "append_unique":
        if current is None:
            current = []
        if not isinstance(current, list):
            raise StateOpError(f"path '{op.path}' is not an array")
        if op.value not in current:
            current.append(op.value)
        parent[key] = current
        return
    if op.op == "remove_value":
        if not isinstance(current, list):
            raise StateOpError(f"path '{op.path}' is not an array")
        parent[key] = [item for item in current if item != op.value]
        return
    raise StateOpError(f"Unsupported op '{op.op}'")


def _resolve_parent_and_key(root: dict[str, Any], path: str) -> tuple[dict[str, Any], str]:
    if not path:
        raise StateOpError("path is empty")
    parts = [part for part in path.split(".") if part]
    if not parts:
        raise StateOpError("path is invalid")

    current: dict[str, Any] = root
    for part in parts[:-1]:
        child = current.get(part)
        if child is None:
            child = {}
            current[part] = child
        if not isinstance(child, dict):
            raise StateOpError(f"path segment '{part}' is not an object")
        current = child
    return current, parts[-1]
