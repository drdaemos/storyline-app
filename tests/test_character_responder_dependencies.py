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
        role="Assistant",
        backstory="Test character for dependency injection",
        personality="Helpful and direct",
        appearance="Digital assistant",
        relationships={"user": "helper"},
        key_locations=["digital space"],
        setting_description="Test digital environment"
    )

    # Create mock processors
    primary_processor = MockPromptProcessor("Primary response")
    backup_processor = MockPromptProcessor("Backup response")

    # Create dependencies without memory or logger
    dependencies = CharacterResponderDependencies(
        primary_processor=primary_processor,
        backup_processor=backup_processor,
        conversation_memory=None,
        chat_logger=None
    )

    # Create CharacterResponder with dependencies
    responder = CharacterResponder(character, dependencies)

    # Verify dependencies are correctly set
    assert responder.processor is primary_processor
    assert responder.backup_processor is backup_processor
    assert responder.persistent_memory is None
    assert responder.chat_logger is None
    assert responder.character is character
    assert responder.session_id is None  # No session_id provided in dependencies


@patch('src.processors.cohere_prompt_processor.CoherePromptProcessor')
@patch('src.processors.claude_prompt_processor.ClaudePromptProcessor')
def test_character_responder_default_dependencies(mock_claude, mock_cohere):
    """Test that CharacterResponder creates default dependencies correctly."""
    # Mock the processors
    mock_claude.return_value = MockPromptProcessor("Claude response")
    mock_cohere.return_value = MockPromptProcessor("Cohere response")

    character = Character(
        name="DefaultBot",
        role="Assistant",
        backstory="Test character with defaults",
        personality="Standard assistant",
        appearance="Default appearance",
        relationships={"user": "client"},
        key_locations=["office"],
        setting_description="Default office environment"
    )

    # Create dependencies manually
    dependencies = CharacterResponderDependencies(
        primary_processor=MockPromptProcessor("Claude response"),
        backup_processor=MockPromptProcessor("Cohere response"),
        conversation_memory=None,
        chat_logger=None,
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


@patch('src.models.character_responder_dependencies.OpenRouterPromptProcessor')
@patch('src.models.character_responder_dependencies.CoherePromptProcessor')
@patch('src.models.character_responder_dependencies.ClaudePromptProcessor')
@patch('src.models.character_responder_dependencies.ConversationMemory')
@patch('src.models.character_responder_dependencies.ChatLogger')
def test_dependencies_create_default(mock_logger, mock_memory, mock_claude, mock_cohere, mock_openrouter):
    """Test CharacterResponderDependencies.create_default method."""
    # Mock the dependencies
    mock_claude_instance = MockPromptProcessor("Claude response")
    mock_cohere_instance = MockPromptProcessor("Cohere response")
    mock_openrouter_instance = MockPromptProcessor("OpenRouter response")
    mock_memory_instance = Mock()
    mock_logger_instance = Mock()

    mock_claude.return_value = mock_claude_instance
    mock_cohere.return_value = mock_cohere_instance
    mock_openrouter.return_value = mock_openrouter_instance
    mock_memory.return_value = mock_memory_instance
    mock_logger.return_value = mock_logger_instance

    dependencies = CharacterResponderDependencies.create_default(
        character_name="TestChar",
        session_id="test-123",
        use_persistent_memory=False,
        logs_dir=None,
        processor_type="claude"
    )

    assert dependencies.primary_processor is mock_claude_instance
    assert dependencies.backup_processor is mock_openrouter_instance
    assert dependencies.conversation_memory is None  # Because use_persistent_memory=False
    assert dependencies.chat_logger is mock_logger_instance

    # Test with persistent memory
    dependencies_with_memory = CharacterResponderDependencies.create_default(
        character_name="TestChar2",
        session_id="test-456",
        use_persistent_memory=True,
        logs_dir=None,
        processor_type="cohere"
    )

    assert dependencies_with_memory.primary_processor is mock_cohere_instance
    assert dependencies_with_memory.backup_processor is mock_openrouter_instance
    assert dependencies_with_memory.conversation_memory is mock_memory_instance
