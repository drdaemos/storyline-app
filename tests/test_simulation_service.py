from pathlib import Path
from typing import Any

from src.character_loader import CharacterLoader
from src.memory.character_registry import CharacterRegistry
from src.simulation.contracts import (
    CharacterActionOutput,
    GmResolutionOutput,
    MoveAdjudication,
    NarratorOutput,
    ObservationInput,
    StateOp,
    SuggestedActionsOutput,
)
from src.simulation.model_router import ModelRouter
from src.simulation.repository import SimulationRepository
from src.simulation.service import SimulationService


class FakeRouter(ModelRouter):
    def __init__(self) -> None:
        pass

    def get_processor(self, model_key: str) -> object:
        return object()


class FakeRunner:
    prompt_version = "test-v2"

    def __init__(self) -> None:
        self.received_persona_name: str | None = None
        self.received_scene_moves_count: int | None = None

    def run_character_action(self, **_: Any) -> CharacterActionOutput:
        return CharacterActionOutput(
            action_type="reaction",
            target="persona-1",
            description='asks persona-1, "What exactly do you mean?"',
            intent_tags=["curious"],
        )

    def run_gm_resolution(self, *, scene_moves: list[dict[str, Any]], **_: Any) -> GmResolutionOutput:
        self.received_scene_moves_count = len(scene_moves)
        adjudications: list[MoveAdjudication] = []
        for move in scene_moves:
            actor_id = str(move.get("actor_id", ""))
            if actor_id == "persona-1":
                adjudications.append(
                    MoveAdjudication(
                        move_id=str(move.get("move_id", "")),
                        actor_id=actor_id,
                        requires_skill_check=True,
                        skill="warmth",
                        difficulty_class=12,
                        reasoning="Direct confrontation under pressure.",
                    )
                )
                continue
            adjudications.append(
                MoveAdjudication(
                    move_id=str(move.get("move_id", "")),
                    actor_id=actor_id,
                    requires_skill_check=False,
                    auto_outcome="success",
                    reasoning="Low-risk conversational response.",
                )
            )
        return GmResolutionOutput(adjudications=adjudications)

    def run_narrator(self, **_: Any) -> NarratorOutput:
        return NarratorOutput(
            narration_text="The room tightens, then eases when the response lands clearly.",
            new_observations=[ObservationInput(character_id="npc-1", content="persona-1 pressed directly", importance=3)],
            state_ops=[StateOp(op="increment", path="pressure_clock", value=1)],
        )

    def run_action_suggestions(self, *, persona: Any, **_: Any) -> SuggestedActionsOutput:
        self.received_persona_name = getattr(persona, "name", None)
        return SuggestedActionsOutput(
            suggested_actions=[
                "I ask npc-1 to name one concrete fear right now.",
                "I tell npc-1 exactly what boundary I need respected.",
                "I redirect both of us to one actionable next step.",
            ]
        )


class FakeRunnerWithStringIncrement(FakeRunner):
    def run_narrator(self, **_: Any) -> NarratorOutput:
        return NarratorOutput(
            narration_text="The room goes quiet after the exchange.",
            new_observations=[ObservationInput(character_id="persona-1", content="npc-1 stayed calm", importance=2)],
            state_ops=[StateOp(op="increment", path="pressure_clock", value="1")],
        )


class FakeRunnerWithSuggestionFailure(FakeRunner):
    def run_action_suggestions(self, **_: Any) -> SuggestedActionsOutput:
        raise ValueError("suggestion-step-failed")


def _make_character(name: str, is_persona: bool = False) -> dict[str, Any]:
    return {
        "name": name,
        "tagline": f"{name} tagline",
        "backstory": f"{name} backstory",
        "personality": "",
        "appearance": "",
        "relationships": {},
        "key_locations": [],
        "setting_description": "",
        "interests": [],
        "dislikes": [],
        "desires": [],
        "kinks": [],
        "is_persona": is_persona,
    }


def _build_service(tmp_path: Path) -> SimulationService:
    registry = CharacterRegistry(memory_dir=tmp_path)
    registry.save_character("npc-1", _make_character("npc-1"), user_id="u1")
    registry.save_character("persona-1", _make_character("persona-1", is_persona=True), user_id="u1", is_persona=True)
    repository = SimulationRepository(memory_dir=tmp_path)
    character_loader = CharacterLoader(memory_dir=tmp_path)
    return SimulationService(repository=repository, model_router=FakeRouter(), character_loader=character_loader, llm_runner=FakeRunner())


def test_simulation_service_adjusted_cycle_and_idempotency(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    session_id = "session-cycle-1"
    service.start_session(
        session_id=session_id,
        user_id="u1",
        npc_character_id="npc-1",
        persona_character_id="persona-1",
        intro_seed="You enter the room.",
        small_model_key="deepseek-v32",
        large_model_key="claude-sonnet",
    )

    first = service.run_turn(
        session_id=session_id,
        user_id="u1",
        user_action="I step closer and call out npc-1 directly.",
        user_action_id="ua-cycle-1",
    )
    second = service.run_turn(
        session_id=session_id,
        user_id="u1",
        user_action="I step closer and call out npc-1 directly.",
        user_action_id="ua-cycle-1",
    )

    assert "room" in first.narration_text.lower()
    assert len(first.suggested_actions) == 3
    assert first.meta_text is not None
    assert "Action outcomes:" in first.meta_text
    assert "Dice rolls:" in first.meta_text
    assert "Scene state changes:" in first.meta_text
    assert second.narration_text == first.narration_text
    assert second.suggested_actions == first.suggested_actions
    assert second.meta_text == first.meta_text
    assert service.llm_runner.received_scene_moves_count == 2


def test_simulation_service_rolls_1d20_plus_skill_modifier(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    service.start_session(
        session_id="session-cycle-2",
        user_id="u1",
        npc_character_id="npc-1",
        persona_character_id="persona-1",
        intro_seed="You enter the room.",
        small_model_key="deepseek-v32",
        large_model_key="claude-sonnet",
    )

    result = service.run_turn(
        session_id="session-cycle-2",
        user_id="u1",
        user_action="I push for a hard answer.",
        user_action_id="ua-cycle-2",
    )

    assert result.meta_text is not None
    assert "1d20+5" in result.meta_text


def test_simulation_service_passes_persona_to_action_suggestions(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    service.start_session(
        session_id="session-cycle-3",
        user_id="u1",
        npc_character_id="npc-1",
        persona_character_id="persona-1",
        intro_seed="You enter the room.",
        small_model_key="deepseek-v32",
        large_model_key="claude-sonnet",
    )

    service.run_turn(
        session_id="session-cycle-3",
        user_id="u1",
        user_action="I speak first.",
        user_action_id="ua-cycle-3",
    )

    assert service.llm_runner.received_persona_name == "persona-1"


def test_simulation_service_coerces_string_increment_state_op(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    service.llm_runner = FakeRunnerWithStringIncrement()
    service.start_session(
        session_id="session-cycle-4",
        user_id="u1",
        npc_character_id="npc-1",
        persona_character_id="persona-1",
        intro_seed="You enter the room.",
        small_model_key="deepseek-v32",
        large_model_key="claude-sonnet",
    )

    result = service.run_turn(
        session_id="session-cycle-4",
        user_id="u1",
        user_action="I push the scene.",
        user_action_id="ua-cycle-4",
    )

    assert result.meta_text is not None
    assert "increment pressure_clock 1" in result.meta_text


def test_simulation_service_uses_fallback_suggestions_on_failure(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    service.llm_runner = FakeRunnerWithSuggestionFailure()
    service.start_session(
        session_id="session-cycle-5",
        user_id="u1",
        npc_character_id="npc-1",
        persona_character_id="persona-1",
        intro_seed="You enter the room.",
        small_model_key="deepseek-v32",
        large_model_key="claude-sonnet",
    )

    result = service.run_turn(
        session_id="session-cycle-5",
        user_id="u1",
        user_action="I ask what changed.",
        user_action_id="ua-cycle-5",
    )

    assert len(result.suggested_actions) == 3
    assert all(isinstance(item, str) and item for item in result.suggested_actions)
