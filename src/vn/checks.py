"""Check resolution: deterministic f(roll, difficulty, applicable modifiers).

The roll model is an explicitly non-final placeholder (d20, roll + modifiers >= difficulty);
the spec defers the real design to the next version. Everything depends only on the
RollResolver protocol so the redesign is a drop-in.
"""

import random
from collections.abc import Set as AbstractSet
from typing import Protocol

from src.models.vn.script import CheckSpec
from src.vn.conditions import StateMap, evaluate_condition

ROLL_SIDES = 20


class RollResolver(Protocol):
    def roll(self) -> int: ...


class PlaceholderRollResolver:
    """Seedable d20. `skip` discards rolls already consumed, so a resumed session
    continues the exact roll sequence of the original one."""

    def __init__(self, seed: int = 0, skip: int = 0) -> None:
        self._random = random.Random(seed)
        for _ in range(skip):
            self._random.randint(1, ROLL_SIDES)

    def roll(self) -> int:
        return self._random.randint(1, ROLL_SIDES)


def modifier_total(check: CheckSpec, state: StateMap, visited: AbstractSet[str]) -> int:
    """Sum of modifiers whose conditions match the current state. [D5]"""
    return sum(modifier.mod for modifier in check.modifiers if evaluate_condition(modifier, state, visited))


def resolve_check(check: CheckSpec, roll: int, state: StateMap, visited: AbstractSet[str]) -> tuple[bool, int]:
    """Returns (success, applied modifier total). Placeholder rule: roll + modifiers >= difficulty."""
    total = modifier_total(check, state, visited)
    return roll + total >= check.difficulty, total
