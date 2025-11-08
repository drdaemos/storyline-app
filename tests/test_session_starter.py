import pytest

from src.character_loader import CharacterLoader
from src.character_manager import CharacterManager
from src.memory.conversation_memory import ConversationMemory
from src.models.character import Character
from src.session_starter import SessionStarter


@pytest.fixture
def test_character():
    """Create a test character."""
    return Character(
        name="TestChar",
        tagline="Tester",
        backstory="A test character for testing",
        personality="Helpful and thorough",
        appearance="Pixelated",
        relationships={"user": "test subject"},
        key_locations=["test lab"],
        setting_description="Test environment",
    )


@pytest.fixture
def session_starter(test_character, tmp_path):
    """Create a SessionStarter instance with test dependencies."""
    # Create character manager with temp directory and save test character to database
    character_manager = CharacterManager(memory_dir=tmp_path)
    character_manager.save_character_to_database(character_id="TestChar", character_data=test_character.model_dump())

    # Create loader with temp directory (same database)
    character_loader = CharacterLoader(memory_dir=tmp_path)
    conversation_memory = ConversationMemory(memory_dir=tmp_path)

    return SessionStarter(character_loader, conversation_memory)


class TestSessionStarter:
    def test_start_session_basic(self, session_starter, tmp_path):
        """Test starting a basic session with intro message."""
        intro_message = "Welcome to the test! The character greets you warmly."

        session_id = session_starter.start_session_with_scenario(character_name="TestChar", intro_message=intro_message)

        # Verify session was created
        assert session_id is not None
        assert len(session_id) > 0

        # Verify message was stored
        memory = ConversationMemory(memory_dir=tmp_path)
        messages = memory.get_session_messages(session_id, "anonymous")
        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert messages[0]["content"] == intro_message


    def test_start_session_empty_character_name(self, session_starter):
        """Test that empty character name raises ValueError."""
        with pytest.raises(ValueError, match="character_name cannot be empty"):
            session_starter.start_session_with_scenario(character_name="", intro_message="Test message")

    def test_start_session_empty_intro_message(self, session_starter):
        """Test that empty intro message raises ValueError."""
        with pytest.raises(ValueError, match="intro_message cannot be empty"):
            session_starter.start_session_with_scenario(character_name="TestChar", intro_message="")

    def test_start_session_nonexistent_character(self, session_starter):
        """Test that nonexistent character raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            session_starter.start_session_with_scenario(character_name="NonexistentChar", intro_message="Test message")

    def test_multiple_sessions_same_character(self, session_starter, tmp_path):
        """Test creating multiple sessions for same character."""
        intro1 = "First scenario intro"
        intro2 = "Second scenario intro"

        session_id1 = session_starter.start_session_with_scenario(character_name="TestChar", intro_message=intro1)

        session_id2 = session_starter.start_session_with_scenario(character_name="TestChar", intro_message=intro2)

        # Sessions should be different
        assert session_id1 != session_id2

        # Each should have correct intro
        memory = ConversationMemory(memory_dir=tmp_path)
        messages1 = memory.get_session_messages(session_id1, "anonymous")
        messages2 = memory.get_session_messages(session_id2, "anonymous")

        assert messages1[0]["content"] == intro1
        assert messages2[0]["content"] == intro2
