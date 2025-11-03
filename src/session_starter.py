"""Module for starting new sessions with scenarios."""

from .character_loader import CharacterLoader
from .memory.conversation_memory import ConversationMemory


class SessionStarter:
    """Service for starting new sessions with scenario intros."""

    def __init__(self, character_loader: CharacterLoader, conversation_memory: ConversationMemory) -> None:
        """
        Initialize the SessionStarter.

        Args:
            character_loader: The character loader to use for loading characters
            conversation_memory: The conversation memory for session management
        """
        self.character_loader = character_loader
        self.conversation_memory = conversation_memory

    def start_session_with_scenario(self, character_name: str, intro_message: str, _persona_id: str | None = None, user_id: str = "anonymous") -> str:
        """
        Start a new session with a scenario intro message.

        Args:
            character_name: Name of the character
            intro_message: The scenario intro message
            persona_id: Optional persona character ID to use as user context
            user_id: ID of the user (defaults to 'anonymous')

        Returns:
            The created session ID

        Raises:
            FileNotFoundError: If character or persona is not found
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

        # Build the intro message with hidden context
        intro_with_context = intro_message

        # Add the intro message as an assistant (character) message
        self.conversation_memory.add_message(character_id=character.name, session_id=session_id, role="assistant", content=intro_with_context, message_type="conversation", user_id=user_id)

        return session_id
