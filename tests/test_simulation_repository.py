from __future__ import annotations

from src.memory.db_models import RulesetRecord
from src.simulation.repository import SimulationRepository


def test_repository_normalizes_legacy_pressure_clock_cap(tmp_path) -> None:
    repo = SimulationRepository(memory_dir=tmp_path)

    with repo.db_config.create_session() as session:
        row = session.get(RulesetRecord, "everyday-tension")
        assert row is not None
        assert isinstance(row.scene_state_schema, dict)
        properties = row.scene_state_schema.get("properties", {})
        pressure_clock = properties.get("pressure_clock", {})
        assert isinstance(pressure_clock, dict)

        pressure_clock["max"] = 6
        row.scene_state_schema = row.scene_state_schema
        row.rulebook_text = row.rulebook_text.replace("pressure_clock.", "pressure_clock (0..6).")
        session.commit()

    ruleset = repo.get_ruleset("everyday-tension")
    assert "(0..6)" not in ruleset.rulebook_text
    assert isinstance(ruleset.scene_state_schema, dict)
    properties = ruleset.scene_state_schema.get("properties", {})
    pressure_clock = properties.get("pressure_clock", {})
    assert isinstance(pressure_clock, dict)
    assert "max" not in pressure_clock
    assert "maximum" not in pressure_clock
