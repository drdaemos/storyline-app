from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from src.character_loader import CharacterLoader
from src.memory.scenario_registry import ScenarioRegistry
from src.models.api_models import StartSessionRequest
from src.simulation.service import SimulationService
from src.simulation.session_store import SimulationSessionStore


@dataclass
class SessionInteractionResult:
    narration_text: str
    suggested_actions: list[str]
    meta_text: str | None
    message_count: int


@dataclass
class SessionApplicationService:
    simulation_service: SimulationService
    session_store: SimulationSessionStore
    scenario_registry: ScenarioRegistry
    character_loader: CharacterLoader

    @classmethod
    def create_default(
        cls,
        *,
        simulation_service: SimulationService,
        scenario_registry: ScenarioRegistry,
        character_loader: CharacterLoader,
    ) -> SessionApplicationService:
        return cls(
            simulation_service=simulation_service,
            session_store=SimulationSessionStore(),
            scenario_registry=scenario_registry,
            character_loader=character_loader,
        )

    def health_check(self) -> bool:
        return self.simulation_service.repository.db_config.health_check()

    def list_sessions(self, user_id: str) -> list[dict]:
        return self.session_store.list_user_sessions(user_id=user_id)

    def get_session_details(self, session_id: str, user_id: str, limit: int = 50) -> dict | None:
        return self.session_store.get_session_chat_details(session_id=session_id, user_id=user_id, limit=limit)

    def get_session_summary(self, session_id: str, user_id: str) -> tuple[str, bool]:
        return self.session_store.build_session_summary_text(session_id=session_id, user_id=user_id)

    def get_session_persona(self, session_id: str, user_id: str) -> dict[str, str | None]:
        session_exists = self.session_store.get_session_chat_details(session_id=session_id, user_id=user_id, limit=1)
        if session_exists is None:
            raise ValueError(f"Session '{session_id}' not found")

        persona_id = self.session_store.get_session_persona_id(session_id=session_id, user_id=user_id)
        if persona_id is None:
            return {"persona_id": None, "persona_name": None}

        try:
            persona = self.character_loader.load_character(persona_id, user_id)
            return {"persona_id": persona_id, "persona_name": persona.name}
        except FileNotFoundError:
            return {"persona_id": persona_id, "persona_name": None}

    def clear_session(self, session_id: str, user_id: str) -> bool:
        return self.session_store.delete_session(session_id=session_id, user_id=user_id)

    def start_session(self, request: StartSessionRequest, user_id: str) -> str:
        if not request.scenario_id and not request.intro_message:
            raise ValueError("Either scenario_id or intro_message must be provided")

        scenario_character_ids: list[str] = []
        scenario_world_lore_id = "default-world"
        scenario_ruleset_id = "everyday-tension"
        scenario_scene_seed: dict = {}

        if request.scenario_id:
            scenario_data = self.scenario_registry.get_scenario(request.scenario_id, user_id)
            if not scenario_data:
                raise FileNotFoundError(f"Scenario '{request.scenario_id}' not found")
            scenario_payload = scenario_data["scenario_data"]
            intro_message = scenario_payload.get("intro_message", "")
            if not intro_message:
                raise ValueError(f"Scenario '{request.scenario_id}' has no intro_message")
            persona_id = scenario_payload.get("persona_id")
            if not persona_id:
                raise ValueError(f"Scenario '{request.scenario_id}' has no persona_id")
            scenario_world_lore_id = scenario_payload.get("world_lore_id")
            if not scenario_world_lore_id:
                raise ValueError(f"Scenario '{request.scenario_id}' has no world_lore_id")
            scenario_ruleset_id = scenario_payload.get("ruleset_id")
            if not scenario_ruleset_id:
                raise ValueError(f"Scenario '{request.scenario_id}' has no ruleset_id")
            raw_scene_seed = scenario_payload.get("scene_seed")
            if isinstance(raw_scene_seed, dict):
                scenario_scene_seed = raw_scene_seed
            scenario_character_ids = scenario_payload.get("character_ids") or []
            if not scenario_character_ids:
                raise ValueError(f"Scenario '{request.scenario_id}' has no character_ids")
        else:
            if not request.persona_id:
                raise ValueError("persona_id is required when scenario_id is not provided")
            if not request.character_name:
                raise ValueError("character_name is required when scenario_id is not provided")
            persona_id = request.persona_id
            intro_message = request.intro_message or ""
            scenario_character_ids = [request.character_name]
            scenario_world_lore_id = request.world_lore_id or "default-world"
            scenario_ruleset_id = request.ruleset_id or "everyday-tension"
            scenario_scene_seed = request.scene_seed if isinstance(request.scene_seed, dict) else {}

        npc_character_ids = [character_id for character_id in dict.fromkeys(scenario_character_ids) if character_id and character_id != persona_id]
        if not npc_character_ids:
            raise ValueError("No NPC characters resolved for session")
        for character_id in npc_character_ids:
            self.character_loader.load_character(character_id, user_id)

        self.character_loader.load_character(persona_id, user_id)

        session_id = str(uuid.uuid4())
        self.simulation_service.start_session(
            session_id=session_id,
            user_id=user_id,
            scenario_id=request.scenario_id,
            npc_character_ids=npc_character_ids,
            persona_character_id=persona_id,
            intro_seed=intro_message,
            ruleset_id=scenario_ruleset_id,
            world_lore_id=scenario_world_lore_id,
            scene_seed_overrides=scenario_scene_seed,
            small_model_key=request.small_model_key,
            large_model_key=request.large_model_key,
        )
        return session_id

    def configure_session_models(self, session_id: str, user_id: str, small_model_key: str, large_model_key: str) -> bool:
        return self.simulation_service.configure_session_models(
            session_id=session_id,
            user_id=user_id,
            small_model_key=small_model_key,
            large_model_key=large_model_key,
        )

    def run_interaction(self, *, session_id: str, user_id: str, user_message: str) -> SessionInteractionResult:
        user_action_id = f"ua-{datetime.now(UTC).timestamp()}-{session_id}"
        turn_result = self.simulation_service.run_turn(
            session_id=session_id,
            user_id=user_id,
            user_action=user_message,
            user_action_id=user_action_id,
        )
        session_details = self.session_store.get_session_chat_details(session_id=session_id, user_id=user_id, limit=1)
        message_count = session_details["message_count"] if session_details else 0
        return SessionInteractionResult(
            narration_text=turn_result.narration_text,
            suggested_actions=turn_result.suggested_actions,
            meta_text=turn_result.meta_text,
            message_count=message_count,
        )
