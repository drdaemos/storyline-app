"""Module for starting new sessions with scenarios."""

from .character_loader import CharacterLoader
from .memory.conversation_memory import ConversationMemory
from .memory.scenario_registry import ScenarioRegistry
from .memory.summary_memory import SummaryMemory
from .scenario_to_summary import create_initial_summary_from_scenario


class SessionStarter:
    """Service for starting new sessions with scenario intros."""

    def __init__(
        self,
        character_loader: CharacterLoader,
        conversation_memory: ConversationMemory,
        scenario_registry: ScenarioRegistry | None = None,
        summary_memory: SummaryMemory | None = None,
    ) -> None:
        """
        Initialize the SessionStarter.

        Args:
            character_loader: The character loader to use for loading characters
            conversation_memory: The conversation memory for session management
            scenario_registry: Optional scenario registry for loading stored scenarios
            summary_memory: Optional summary memory for storing initial scenario summaries
        """
        self.character_loader = character_loader
        self.conversation_memory = conversation_memory
        self.scenario_registry = scenario_registry
        self.summary_memory = summary_memory or SummaryMemory()

    def start_session_with_scenario_id(
        self,
        character_name: str,
        scenario_id: str,
        user_id: str = "anonymous",
    ) -> str:
        """
        Start a new session with a stored scenario.
        The persona is automatically loaded from the scenario if specified.

        Args:
            character_name: Name of the character
            scenario_id: ID of the stored scenario to use
            user_id: ID of the user (defaults to 'anonymous')

        Returns:
            The created session ID

        Raises:
            FileNotFoundError: If character or scenario is not found, or if persona_id is specified but persona not found
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

        # Get intro message and persona_id from scenario
        intro_message = scenario_data["scenario_data"].get("intro_message", "")
        if not intro_message:
            raise ValueError(f"Scenario '{scenario_id}' has no intro_message")

        persona_id = scenario_data["scenario_data"].get("persona_id")

        # Create new session
        session_id = self.conversation_memory.create_session(character.name)

        # Load the persona from the scenario if specified
        persona_name = "User"
        if persona_id:
            persona = self.character_loader.load_character(persona_id, user_id)
            if not persona:
                raise FileNotFoundError(f"Persona '{persona_id}' not found for scenario '{scenario_id}'")
            persona_name = persona.name

        # Create initial summary from scenario data (before adding intro message)
        # This makes the summary immediately available when CharacterResponder initializes
        initial_summary = create_initial_summary_from_scenario(
            scenario_data=scenario_data["scenario_data"],
            character_name=character.name,
            persona_name=persona_name,
        )

        # Save the initial summary with offset 0 (before any messages)
        self.summary_memory.add_summary(
            character_id=character.name,
            session_id=session_id,
            summary=initial_summary.model_dump_json(),
            start_offset=0,
            end_offset=0,
            user_id=user_id,
        )

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
        user_id: str = "anonymous",
    ) -> str:
        """
        Start a new session with a raw intro message (no scenario link).
        Note: Sessions started this way will not have an associated persona.

        Args:
            character_name: Name of the character
            intro_message: The scenario intro message
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
        user_id: str = "anonymous",
    ) -> str:
        """
        Backwards-compatible alias for start_session_with_intro.

        Deprecated: Use start_session_with_intro or start_session_with_scenario_id instead.
        """
        return self.start_session_with_intro(character_name, intro_message, user_id)
