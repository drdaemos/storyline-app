"""Module for starting new sessions with scenarios."""

from .character_loader import CharacterLoader
from .memory.conversation_memory import ConversationMemory
from .memory.scenario_registry import ScenarioRegistry


class SessionStarter:
    """Service for starting new sessions with scenario intros."""

    def __init__(
        self,
        character_loader: CharacterLoader,
        conversation_memory: ConversationMemory,
        scenario_registry: ScenarioRegistry | None = None,
    ) -> None:
        """
        Initialize the SessionStarter.

        Args:
            character_loader: The character loader to use for loading characters
            conversation_memory: The conversation memory for session management
            scenario_registry: Optional scenario registry for loading stored scenarios
        """
        self.character_loader = character_loader
        self.conversation_memory = conversation_memory
        self.scenario_registry = scenario_registry

    def start_session_with_scenario_id(
        self,
        character_name: str,
        scenario_id: str,
        persona_id: str | None = None,
        user_id: str = "anonymous",
    ) -> str:
        """
        Start a new session with a stored scenario.

        Args:
            character_name: Name of the character
            scenario_id: ID of the stored scenario to use
            persona_id: Optional persona character ID to use as user context
            user_id: ID of the user (defaults to 'anonymous')

        Returns:
            The created session ID

        Raises:
            FileNotFoundError: If character or scenario is not found
            ValueError: If character_name or scenario_id is empty, or if scenario doesn't match character
        """
        if not character_name:
            raise ValueError("character_name cannot be empty")
        if not scenario_id:
            raise ValueError("scenario_id cannot be empty")
        if not self.scenario_registry:
            raise ValueError("ScenarioRegistry not configured - cannot load scenarios by ID")

        # Load the character
        character = self.character_loader.load_character(character_name, user_id)
        if not character:
            raise FileNotFoundError(f"Character '{character_name}' not found")

        # Load the scenario
        scenario_data = self.scenario_registry.get_scenario(scenario_id, user_id)
        if not scenario_data:
            raise FileNotFoundError(f"Scenario '{scenario_id}' not found")

        # Validate scenario matches the character
        if scenario_data["character_id"] != character_name:
            raise ValueError(f"Scenario '{scenario_id}' is for character '{scenario_data['character_id']}', not '{character_name}'")

        # Get intro message from scenario
        intro_message = scenario_data["scenario_data"].get("intro_message", "")
        if not intro_message:
            raise ValueError(f"Scenario '{scenario_id}' has no intro_message")

        # Create new session
        session_id = self.conversation_memory.create_session(character.name)

        # Add the intro message as an assistant (character) message, linking to the scenario
        self.conversation_memory.add_message(
            character_id=character.name,
            session_id=session_id,
            role="assistant",
            content=intro_message,
            message_type="conversation",
            user_id=user_id,
            scenario_id=scenario_id,
        )

        return session_id

    def start_session_with_intro(
        self,
        character_name: str,
        intro_message: str,
        persona_id: str | None = None,
        user_id: str = "anonymous",
    ) -> str:
        """
        Start a new session with a raw intro message (no scenario link).

        Args:
            character_name: Name of the character
            intro_message: The scenario intro message
            persona_id: Optional persona character ID to use as user context
            user_id: ID of the user (defaults to 'anonymous')

        Returns:
            The created session ID

        Raises:
            FileNotFoundError: If character is not found
            ValueError: If character_name or intro_message is empty
        """
        if not character_name:
            raise ValueError("character_name cannot be empty")
        if not intro_message:
            raise ValueError("intro_message cannot be empty")

        # Load the character
        character = self.character_loader.load_character(character_name, user_id)
        if not character:
            raise FileNotFoundError(f"Character '{character_name}' not found")

        # Create new session
        session_id = self.conversation_memory.create_session(character.name)

        # Add the intro message as an assistant (character) message
        self.conversation_memory.add_message(
            character_id=character.name,
            session_id=session_id,
            role="assistant",
            content=intro_message,
            message_type="conversation",
            user_id=user_id,
        )

        return session_id

    # Backwards compatibility alias
    def start_session_with_scenario(
        self,
        character_name: str,
        intro_message: str,
        persona_id: str | None = None,
        user_id: str = "anonymous",
    ) -> str:
        """
        Backwards-compatible alias for start_session_with_intro.

        Deprecated: Use start_session_with_intro or start_session_with_scenario_id instead.
        """
        return self.start_session_with_intro(character_name, intro_message, persona_id, user_id)
