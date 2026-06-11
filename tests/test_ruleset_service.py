import tempfile
from pathlib import Path

import pytest

from src.memory.ruleset_registry import RulesetRegistry
from src.models.simulation import CharacterStateData, EmotionalStateData, Ruleset
from src.services.ruleset_service import RulesetService


class _DummyRegistry:
    def get_ruleset(self, _ruleset_id: str, _user_id: str = "anonymous") -> None:
        return None


def _build_ruleset() -> Ruleset:
    return Ruleset.model_validate(
        {
            "id": "core",
            "name": "Core",
            "rules_text": "Test rules",
            "state_schemas": {
                "drives": [
                    {"name": "energy", "range_min": 0, "range_max": 10, "default": 5, "decay_rate": 1.0, "offscreen_baseline": 6},
                    {"name": "satiation", "range_min": 0, "range_max": 10, "default": 4, "decay_rate": 0.5, "offscreen_baseline": None},
                ],
                "skills": [
                    {"name": "persuasion", "range_min": 0, "range_max": 20},
                    {"name": "stealth", "range_min": 0, "range_max": 20},
                ],
                "emotional_state": {
                    "global_dims": [
                        {"name": "composure", "range_min": 0, "range_max": 10, "default": 5, "offscreen_baseline": 7}
                    ],
                    "per_relationship": [
                        {"name": "trust", "range_min": 0, "range_max": 10, "default": 5, "offscreen_baseline": None}
                    ],
                },
            },
            "config": {},
        }
    )


class TestRulesetService:
    @pytest.fixture(autouse=True)
    def clear_database_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATABASE_URL", raising=False)

    def test_load_ruleset_from_registry(self) -> None:
        temp_dir = tempfile.mkdtemp()
        registry = RulesetRegistry(memory_dir=Path(temp_dir))
        try:
            ruleset_id = registry.save_ruleset(
                name="Core",
                rules_text="Rules",
                state_schemas={
                    "drives": [{"name": "energy"}],
                    "skills": [{"name": "persuasion"}],
                    "emotional_state": {},
                },
                config={},
            )

            service = RulesetService(registry)
            ruleset = service.load_ruleset(ruleset_id)

            assert ruleset is not None
            assert ruleset.id == ruleset_id
            assert ruleset.name == "Core"
        finally:
            registry.close()

    def test_initialize_character_state_with_overrides(self) -> None:
        service = RulesetService(_DummyRegistry())  # type: ignore[arg-type]
        ruleset = _build_ruleset()

        state = service.initialize_character_state(
            ruleset=ruleset,
            starting_drives={"energy": 8},
            starting_skills={"persuasion": 12},
            starting_emotional_state={"global_state": {"composure": 9}},
        )

        assert state.drives["energy"] == 8
        assert state.drives["satiation"] == 4
        assert state.skills["persuasion"] == 12
        assert state.skills["stealth"] == 0
        assert state.emotional_state.global_state["composure"] == 9

    def test_apply_drive_decay_and_clamp(self) -> None:
        service = RulesetService(_DummyRegistry())  # type: ignore[arg-type]
        ruleset = _build_ruleset()
        state = CharacterStateData(
            drives={"energy": 1, "satiation": 0.2},
            skills={"persuasion": 40},
            emotional_state=EmotionalStateData(global_state={"composure": 12}),
        )

        service.apply_drive_decay(state, ruleset)
        service.clamp_all(state, ruleset)

        assert state.drives["energy"] == 0
        assert state.drives["satiation"] == 0
        assert state.skills["persuasion"] == 20
        assert state.emotional_state.global_state["composure"] == 10

    def test_apply_drive_effects_and_state_diffs(self) -> None:
        service = RulesetService(_DummyRegistry())  # type: ignore[arg-type]
        ruleset = _build_ruleset()
        state = CharacterStateData(
            drives={"energy": 5, "satiation": 4},
            skills={"persuasion": 10, "stealth": 3},
            emotional_state=EmotionalStateData(
                global_state={"composure": 5},
                per_relationship={"Mara": {"trust": 4}},
            ),
        )

        service.apply_drive_effects(
            state,
            effects=[{"drive": "energy", "change": -3}, {"drive": "satiation", "change": 4}],
            ruleset=ruleset,
        )
        service.apply_state_diffs(
            state,
            diffs=[
                {"stat": "persuasion", "change": 2},
                {"stat": "composure", "change": -2},
                {"stat": "trust", "target": "Mara", "change": 3},
            ],
            ruleset=ruleset,
        )

        assert state.drives["energy"] == 2
        assert state.drives["satiation"] == 8
        assert state.skills["persuasion"] == 12
        assert state.emotional_state.global_state["composure"] == 3
        assert state.emotional_state.per_relationship["Mara"]["trust"] == 7

    def test_apply_state_diffs_auto_initializes_new_relationship(self) -> None:
        service = RulesetService(_DummyRegistry())  # type: ignore[arg-type]
        ruleset = _build_ruleset()
        state = CharacterStateData(
            drives={"energy": 5, "satiation": 4},
            skills={"persuasion": 10},
            emotional_state=EmotionalStateData(
                global_state={"composure": 5},
                per_relationship={},
            ),
        )

        # "Kai" doesn't exist in per_relationship yet — should be auto-initialized
        service.apply_state_diffs(
            state,
            diffs=[{"stat": "trust", "target": "Kai", "change": 2}],
            ruleset=ruleset,
        )

        assert "Kai" in state.emotional_state.per_relationship
        assert state.emotional_state.per_relationship["Kai"]["trust"] == 7  # default 5 + 2

    def test_apply_reactive_effects(self) -> None:
        service = RulesetService(_DummyRegistry())  # type: ignore[arg-type]
        ruleset = _build_ruleset()
        state = CharacterStateData(
            drives={"energy": 5, "satiation": 4},
            skills={"persuasion": 10},
            emotional_state=EmotionalStateData(
                global_state={"composure": 5},
                per_relationship={},
            ),
        )

        service.apply_reactive_effects(
            state,
            effects=[
                {"drive": "energy", "change": -1},
                {"drive": "composure", "change": -2},
            ],
            ruleset=ruleset,
        )

        assert state.drives["energy"] == 4
        assert state.emotional_state.global_state["composure"] == 3

    def test_apply_offscreen_restore(self) -> None:
        service = RulesetService(_DummyRegistry())  # type: ignore[arg-type]
        ruleset = _build_ruleset()
        state = CharacterStateData(
            drives={"energy": 1, "satiation": 1},
            skills={"persuasion": 3},
            emotional_state=EmotionalStateData(global_state={"composure": 2}),
        )

        service.apply_offscreen_restore(state, ruleset)

        assert state.drives["energy"] == 6
        assert state.drives["satiation"] == 1
        assert state.emotional_state.global_state["composure"] == 7
