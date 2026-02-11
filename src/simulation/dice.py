from __future__ import annotations

import random
import re
from dataclasses import dataclass

_DICE_RE = re.compile(r"^\s*(\d+)d(\d+)\s*([+-]\s*\d+)?\s*$")


@dataclass(frozen=True)
class DiceResult:
    expression: str
    rolls: list[int]
    modifier: int
    total: int
    seed: int | None


def roll_dice(expression: str, seed: int | None = None) -> DiceResult:
    match = _DICE_RE.match(expression)
    if not match:
        raise ValueError(f"Invalid dice expression: '{expression}'")

    count = int(match.group(1))
    sides = int(match.group(2))
    modifier_raw = match.group(3) or ""
    modifier = int(modifier_raw.replace(" ", "")) if modifier_raw else 0

    if count < 1 or count > 100:
        raise ValueError("Dice count must be between 1 and 100")
    if sides < 2 or sides > 1000:
        raise ValueError("Dice sides must be between 2 and 1000")

    rng = random.Random(seed)
    rolls = [rng.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + modifier
    normalized_expression = f"{count}d{sides}{modifier:+d}" if modifier else f"{count}d{sides}"
    return DiceResult(expression=normalized_expression, rolls=rolls, modifier=modifier, total=total, seed=seed)
