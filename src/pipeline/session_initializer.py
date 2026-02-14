"""Initialize a session from a scenario: world state, character states, intro narration."""

import logging
import uuid

from src.character_loader import CharacterLoader
from src.memory.conversation_memory import ConversationMemory
from src.memory.scenario_registry import ScenarioRegistry
from src.memory.world_lore_registry import WorldLoreRegistry
from src.models.simulation import Intent, SuccessCondition, WorldState
from src.services.event_stream_service import EventStreamService
from src.services.ruleset_service import RulesetService
from src.services.session_state_service import SessionStateService

logger = logging.getLogger(__name__)


class SessionInitializer:
    """Initializes a new simulation session from a scenario."""

    def __init__(
        self,
        session_state_service: SessionStateService,
        ruleset_service: RulesetService,
        event_stream_service: EventStreamService,
        character_loader: CharacterLoader,
        scenario_registry: ScenarioRegistry,
        conversation_memory: ConversationMemory,
        world_lore_registry: WorldLoreRegistry,
    ) -> None:
        self.session_state = session_state_service
        self.ruleset = ruleset_service
        self.events = event_stream_service
        self.char_loader = character_loader
        self.scenarios = scenario_registry
        self.conversation = conversation_memory
        self.world_lore = world_lore_registry

    def initialize(
        self,
        scenario_id: str,
        user_id: str = "anonymous",
    ) -> dict:
        """Initialize a session from a scenario.

        Returns a dict with session_id, world_state, character_states, and intro text.
        """
        # Load scenario
        scenario_data = self.scenarios.get_scenario(scenario_id, user_id)
        if not scenario_data:
            raise ValueError(f"Scenario '{scenario_id}' not found")

        scenario_content = scenario_data.get("scenario_data", {})

        # Load ruleset (required)
        ruleset_id = scenario_content.get("ruleset_id", "") or scenario_data.get("ruleset_id", "")
        if not ruleset_id:
            raise ValueError(f"Scenario '{scenario_id}' has no ruleset_id")
        ruleset = self.ruleset.load_ruleset(ruleset_id, user_id)
        if not ruleset:
            raise ValueError(f"Ruleset '{ruleset_id}' not found for scenario '{scenario_id}'")

        # Create session
        session_id = str(uuid.uuid4())

        # Build starting world state
        starting_ws = scenario_content.get("starting_world_state")
        if starting_ws:
            world_state = WorldState(**starting_ws)
        else:
            world_state = WorldState(
                location=scenario_content.get("location", "Unknown"),
                time=scenario_content.get("time_context", ""),
                characters_present=scenario_content.get("character_ids", []) or scenario_data.get("character_ids", []),
            )

        # Create session in DB
        self.session_state.sessions.create_session(
            session_id=session_id,
            scenario_id=scenario_id,
            world_state=world_state.model_dump(),
            user_id=user_id,
        )

        # Initialize character states
        character_ids = scenario_content.get("character_ids", []) or scenario_data.get("character_ids", [])
        character_goals = scenario_content.get("character_goals", {})
        character_overrides = scenario_content.get("character_starting_overrides", {})

        for char_id in character_ids:
            overrides = character_overrides.get(char_id, {})
            char_info = self.char_loader.get_character_info(char_id, user_id)

            # Merge character-level starting values with scenario overrides
            starting_drives: dict[str, float] = {}
            starting_skills: dict[str, float] = {}
            starting_emotional: dict | None = None

            if char_info:
                if char_info.starting_drives:
                    starting_drives.update(char_info.starting_drives)
                if char_info.starting_skills:
                    starting_skills.update(char_info.starting_skills)
                if char_info.starting_emotional_state:
                    starting_emotional = char_info.starting_emotional_state

            # Scenario overrides take priority
            if "drives" in overrides:
                starting_drives.update(overrides["drives"])
            if "skills" in overrides:
                starting_skills.update(overrides["skills"])
            if "emotional_state" in overrides:
                starting_emotional = overrides["emotional_state"]

            state = self.ruleset.initialize_character_state(
                ruleset=ruleset,
                starting_drives=starting_drives or None,
                starting_skills=starting_skills or None,
                starting_emotional_state=starting_emotional,
            )

            # Set initial intent from scenario goals if available
            goal = character_goals.get(char_id)
            if goal:
                state.active_intent = Intent(
                    goal=goal,
                    success_condition=SuccessCondition(
                        type="narrative",
                        description=goal,
                    ),
                    source_refs=["scenario_start"],
                )

            self.session_state.save_character_state(session_id, char_id, state)

        # Also initialize persona state if specified
        persona_id = scenario_content.get("persona_id", "")
        if persona_id:
            overrides = character_overrides.get(persona_id, {})
            char_info = self.char_loader.get_character_info(persona_id, user_id)

            starting_drives = {}
            starting_skills = {}
            starting_emotional = None

            if char_info:
                if char_info.starting_drives:
                    starting_drives.update(char_info.starting_drives)
                if char_info.starting_skills:
                    starting_skills.update(char_info.starting_skills)
                if char_info.starting_emotional_state:
                    starting_emotional = char_info.starting_emotional_state

            if "drives" in overrides:
                starting_drives.update(overrides["drives"])
            if "skills" in overrides:
                starting_skills.update(overrides["skills"])
            if "emotional_state" in overrides:
                starting_emotional = overrides["emotional_state"]

            persona_state = self.ruleset.initialize_character_state(
                ruleset=ruleset,
                starting_drives=starting_drives or None,
                starting_skills=starting_skills or None,
                starting_emotional_state=starting_emotional,
            )
            self.session_state.save_character_state(session_id, persona_id, persona_state)

        # Store intro as first narration
        intro = scenario_content.get("intro_message", "")
        if intro:
            self.conversation.add_message(
                session_id=session_id,
                role="narration",
                content=intro,
                user_id=user_id,
                scenario_id=scenario_id,
            )
            self.session_state.append_narration(session_id, intro)

        # Save initial snapshot
        self.session_state.save_snapshot(session_id, user_id)

        return {
            "session_id": session_id,
            "world_state": world_state.model_dump(),
            "character_ids": character_ids,
            "persona_id": persona_id,
            "intro": intro,
        }
