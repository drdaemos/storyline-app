from unittest.mock import Mock, patch

from src.character_responder import CharacterResponder
from src.models.character import Character
from src.models.character_responder_dependencies import CharacterResponderDependencies
from tests.test_character_pipeline import MockPromptProcessor


def test_character_responder_dependencies_creation():
    """Test that CharacterResponderDependencies can be created and used."""
    # Create test character
    character = Character(
        name="TestBot",
        tagline="Assistant",
        backstory="Test character for dependency injection",
        personality="Helpful and direct",
        appearance="Digital assistant",
        relationships={"user": "helper"},
        key_locations=["digital space"],
        setting_description="Test digital environment",
    )

    # Create mock processors
    primary_processor = MockPromptProcessor("Primary response")
    backup_processor = MockPromptProcessor("Backup response")

    # Create mock memory and logger
    conversation_memory = Mock()
    conversation_memory.get_recent_messages.return_value = []
    conversation_memory.get_session_messages.return_value = []

    summary_memory = Mock()
    summary_memory.get_session_summaries.return_value = []

    chat_logger = Mock()

    # Create dependencies
    dependencies = CharacterResponderDependencies(
        primary_processor=primary_processor,
        backup_processor=backup_processor,
        conversation_memory=conversation_memory,
        summary_memory=summary_memory,
        chat_logger=chat_logger,
        session_id="test-session"
    )

    # Create CharacterResponder with dependencies
    responder = CharacterResponder(character, dependencies)

    # Verify dependencies are correctly set
    assert responder.processor is primary_processor
    assert responder.backup_processor is backup_processor
    assert responder.persistent_memory is conversation_memory
    assert responder.summary_memory is summary_memory
    assert responder.chat_logger is chat_logger
    assert responder.character is character
    assert responder.session_id == "test-session"  # Session_id provided in dependencies


@patch("src.processors.cohere_prompt_processor.CoherePromptProcessor")
@patch("src.processors.claude_prompt_processor.ClaudePromptProcessor")
def test_character_responder_default_dependencies(mock_claude, mock_cohere):
    """Test that CharacterResponder creates default dependencies correctly."""
    # Mock the processors
    mock_claude.return_value = MockPromptProcessor("Claude response")
    mock_cohere.return_value = MockPromptProcessor("Cohere response")

    character = Character(
        name="DefaultBot",
        tagline="Assistant",
        backstory="Test character with defaults",
        personality="Standard assistant",
        appearance="Default appearance",
        relationships={"user": "client"},
        key_locations=["office"],
        setting_description="Default office environment",
    )

    # Create mock memory and logger
    conversation_memory = Mock()
    conversation_memory.get_recent_messages.return_value = []
    conversation_memory.get_session_messages.return_value = []

    summary_memory = Mock()
    summary_memory.get_session_summaries.return_value = []

    chat_logger = Mock()

    # Create dependencies manually
    dependencies = CharacterResponderDependencies(
        primary_processor=MockPromptProcessor("Claude response"),
        backup_processor=MockPromptProcessor("Cohere response"),
        conversation_memory=conversation_memory,
        summary_memory=summary_memory,
        chat_logger=chat_logger,
        session_id="default-session"
    )

    # Create CharacterResponder with dependencies
    responder = CharacterResponder(character, dependencies)

    # Verify that dependencies were created
    assert responder.processor is not None
    assert responder.backup_processor is not None
    assert responder.dependencies is not None
    assert responder.character is character
    assert responder.session_id == "default-session"


@patch("src.models.prompt_processor_factory.PromptProcessorFactory.create_processor")
@patch("src.models.prompt_processor_factory.PromptProcessorFactory.get_default_backup_processor")
@patch("src.models.character_responder_dependencies.ConversationMemory")
@patch("src.models.character_responder_dependencies.ChatLogger")
def test_dependencies_create_default(mock_logger, mock_memory, mock_get_backup, mock_create_processor):
    """Test CharacterResponderDependencies.create_default method."""
    # Mock the dependencies
    mock_primary_processor = MockPromptProcessor("Primary response")
    mock_backup_processor = MockPromptProcessor("Backup response")
    mock_memory_instance = Mock()
    mock_logger_instance = Mock()

    mock_create_processor.return_value = mock_primary_processor
    mock_get_backup.return_value = mock_backup_processor
    mock_memory.return_value = mock_memory_instance
    mock_logger.return_value = mock_logger_instance

    # Mock the create_session method
    mock_memory_instance.create_session.return_value = "test-session"

    # Test dependencies creation
    dependencies = CharacterResponderDependencies.create_default(character_name="TestChar2", processor_type="cohere")

    assert dependencies.primary_processor is mock_primary_processor
    assert dependencies.backup_processor is mock_backup_processor
    assert dependencies.conversation_memory is mock_memory_instance
