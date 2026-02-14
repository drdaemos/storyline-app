"""Programmatic dice resolution for skill checks. No LLM calls."""

import random
from dataclasses import dataclass


@dataclass
class DiceResult:
    """Result of a dice roll resolution."""

    character: str
    skill: str
    roll: int
    modifier: float
    total: float
    dc: int
    success: bool
    contested: bool = False
    opponent: str | None = None
    opponent_total: float | None = None
    detail: str = ""


class DiceResolver:
    """Resolves skill checks using 1d20 + skill modifier vs DC."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def roll_d20(self) -> int:
        """Roll a single d20."""
        return self._rng.randint(1, 20)

    def resolve_check(
        self,
        character: str,
        skill: str,
        skill_value: float,
        dc: int,
    ) -> DiceResult:
        """Resolve a simple skill check: 1d20 + skill_value vs DC.

        Args:
            character: Character name performing the check
            skill: Skill name being tested
            skill_value: Character's skill modifier
            dc: Difficulty class to beat

        Returns:
            DiceResult with roll details and outcome
        """
        roll = self.roll_d20()
        total = roll + skill_value
        success = total >= dc

        detail = f"d20({roll}) + {skill}({skill_value:.0f}) = {total:.0f} vs DC {dc}"

        return DiceResult(
            character=character,
            skill=skill,
            roll=roll,
            modifier=skill_value,
            total=total,
            dc=dc,
            success=success,
            detail=detail,
        )

    def resolve_contested(
        self,
        character: str,
        skill: str,
        skill_value: float,
        opponent: str,
        opponent_skill: str,
        opponent_skill_value: float,
    ) -> DiceResult:
        """Resolve a contested check: both roll 1d20 + skill, higher wins.

        Args:
            character: Acting character name
            skill: Acting character's skill name
            skill_value: Acting character's skill modifier
            opponent: Opposing character name
            opponent_skill: Opposing character's skill name
            opponent_skill_value: Opposing character's skill modifier

        Returns:
            DiceResult from the acting character's perspective
        """
        roll_a = self.roll_d20()
        roll_b = self.roll_d20()
        total_a = roll_a + skill_value
        total_b = roll_b + opponent_skill_value
        success = total_a >= total_b

        detail = (
            f"d20({roll_a}) + {skill}({skill_value:.0f}) = {total_a:.0f} "
            f"vs d20({roll_b}) + {opponent_skill}({opponent_skill_value:.0f}) = {total_b:.0f}"
        )

        return DiceResult(
            character=character,
            skill=skill,
            roll=roll_a,
            modifier=skill_value,
            total=total_a,
            dc=0,
            success=success,
            contested=True,
            opponent=opponent,
            opponent_total=total_b,
            detail=detail,
        )
