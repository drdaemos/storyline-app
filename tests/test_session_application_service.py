from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from src.models.api_models import StartSessionRequest
from src.session_application_service import SessionApplicationService


def test_scenario_id_is_forwarded_to_simulation_service() -> None:
    simulation_service = Mock()
    scenario_registry = Mock()
    character_loader = Mock()

    scenario_registry.get_scenario.return_value = {
        "scenario_data": {
            "intro_message": "The room goes quiet as the bottle slows.",
            "persona_id": "nora",
            "world_lore_id": "world-1",
            "ruleset_id": "everyday-tension",
            "character_ids": ["elliot", "matteo", "nina"],
        }
    }
    character_loader.load_character.return_value = SimpleNamespace(name="loaded")

    service = SessionApplicationService(
        simulation_service=simulation_service,
        session_store=Mock(),
        scenario_registry=scenario_registry,
        character_loader=character_loader,
    )

    request = StartSessionRequest(
        scenario_id="scenario-123",
        small_model_key="claude-opus",
        large_model_key="claude-opus",
    )

    session_id = service.start_session(request=request, user_id="anonymous")

    simulation_service.start_session.assert_called_once()
    kwargs = simulation_service.start_session.call_args.kwargs
    assert kwargs["session_id"] == session_id
    assert kwargs["scenario_id"] == "scenario-123"
    assert kwargs["npc_character_ids"] == ["elliot", "matteo", "nina"]
    assert kwargs["persona_character_id"] == "nora"

