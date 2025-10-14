from unittest.mock import Mock, patch

import pytest

from src.character_responder import CharacterResponder
from src.models.character import Character
from src.models.character_responder_dependencies import CharacterResponderDependencies
from src.models.evaluation import Evaluation
from tests.test_character_pipeline import MockPromptProcessor


def create_test_character() -> Character:
    """Create a test character for testing."""
    return Character(
        name="TestBot",
        tagline="Assistant",
        backstory="Test character for command testing",
        personality="Helpful and direct",
        appearance="Digital assistant",
        relationships={"user": "helper"},
        key_locations=["digital space"],
        setting_description="Test digital environment",
    )


def create_test_responder(with_memory: bool = False) -> CharacterResponder:
    """Create a test CharacterResponder."""
    character = create_test_character()
    primary_processor = MockPromptProcessor("Primary response")
    backup_processor = MockPromptProcessor("Backup response")

    # Mock conversation memory if requested
    conversation_memory = None
    if with_memory:
        conversation_memory = Mock()
        conversation_memory.get_recent_messages.return_value = []
        conversation_memory.get_session_messages.return_value = []
        conversation_memory.add_messages.return_value = None
        conversation_memory.delete_session.return_value = None
        conversation_memory.delete_messages_from_offset.return_value = 3

    dependencies = CharacterResponderDependencies(
        primary_processor=primary_processor, backup_processor=backup_processor, conversation_memory=conversation_memory, chat_logger=None, session_id="test-session" if with_memory else None
    )

    return CharacterResponder(character, dependencies)


def test_command_detection():
    """Test that commands are properly detected and routed."""
    responder = create_test_responder()

    # Test that /regenerate raises exception when no history
    with pytest.raises(ValueError, match="No conversation history"):
        responder.respond("/regenerate")

    # Test that /rewind raises exception when no history
    with pytest.raises(ValueError, match="No conversation history"):
        responder.respond("/rewind")

    # Test that unknown commands raise exceptions
    with pytest.raises(ValueError, match="Unknown command"):
        responder.respond("/unknown")


def test_command_detection_with_whitespace():
    """Test that commands work with leading/trailing whitespace."""
    responder = create_test_responder()

    # Test with spaces
    with pytest.raises(ValueError, match="No conversation history"):
        responder.respond("  /regenerate  ")

    # Test with tabs and newlines
    with pytest.raises(ValueError, match="No conversation history"):
        responder.respond("\t/rewind\n")


def test_regenerate_command_no_history():
    """Test /regenerate command with no conversation history."""
    responder = create_test_responder()

    with pytest.raises(ValueError, match="No conversation history to regenerate from"):
        responder.respond("/regenerate")


def test_rewind_command_no_history():
    """Test /rewind command with no conversation history."""
    responder = create_test_responder()

    with pytest.raises(ValueError, match="No conversation history to rewind"):
        responder.respond("/rewind")


@patch("src.character_responder.CharacterPipeline.get_evaluation")
@patch("src.character_responder.CharacterPipeline.get_character_response")
def test_regenerate_command_with_history(mock_get_character_response, mock_get_evaluation):
    """Test /regenerate command with conversation history."""
    responder = create_test_responder()

    # Add some conversation history manually
    responder.memory = [
        {"role": "user", "content": "Hello", "created_at": "2023-01-01T00:00:00Z", "type": "conversation"},
        {"role": "assistant", "content": "Evaluation", "created_at": "2023-01-01T00:00:01Z", "type": "evaluation"},
        {"role": "assistant", "content": "Hi there!", "created_at": "2023-01-01T00:00:02Z", "type": "conversation"},
    ]

    # Mock the CharacterPipeline methods
    evaluation_response = Evaluation(patterns_to_avoid="None", status_update="Regenerating response", user_name="User", time_passed="5 seconds")
    character_response = "New regenerated response"

    mock_get_evaluation.return_value = evaluation_response
    mock_get_character_response.return_value = iter(character_response)

    result = responder.respond("/regenerate")
    assert result == character_response

    # Verify that the memory was properly reset
    assert len(responder.memory) == 3  # Original user message + new eval + new response


def test_rewind_command_with_history():
    """Test /rewind command with conversation history."""
    responder = create_test_responder()

    # Track event callback calls
    events = []

    def mock_event_callback(event_type: str, **kwargs: str) -> None:
        events.append({"type": event_type, **kwargs})

    # Add some conversation history manually
    responder.memory = [
        {"role": "user", "content": "First message", "created_at": "2023-01-01T00:00:00Z", "type": "conversation"},
        {"role": "assistant", "content": "First eval", "created_at": "2023-01-01T00:00:01Z", "type": "evaluation"},
        {"role": "assistant", "content": "First response", "created_at": "2023-01-01T00:00:02Z", "type": "conversation"},
        {"role": "user", "content": "Second message", "created_at": "2023-01-01T00:01:00Z", "type": "conversation"},
        {"role": "assistant", "content": "Second eval", "created_at": "2023-01-01T00:01:01Z", "type": "evaluation"},
        {"role": "assistant", "content": "Second response", "created_at": "2023-01-01T00:01:02Z", "type": "conversation"},
    ]

    result = responder.respond("/rewind", event_callback=mock_event_callback)

    # Should return empty string
    assert result == ""

    # Should send command completion event
    assert len(events) == 1
    assert events[0]["type"] == "command"
    assert events[0]["succeeded"] == "true"

    # Memory should only contain the first exchange
    assert len(responder.memory) == 3
    assert responder.memory[-1]["content"] == "First response"


def test_rewind_command_no_user_message():
    """Test /rewind command when there are no user messages."""
    responder = create_test_responder()

    # Add only assistant messages (no user messages)
    responder.memory = [{"role": "assistant", "content": "System message", "created_at": "2023-01-01T00:00:00Z", "type": "evaluation"}]

    with pytest.raises(ValueError, match="No user message found to rewind"):
        responder.respond("/rewind")


def test_regenerate_command_no_user_message():
    """Test /regenerate command when there are no user messages."""
    responder = create_test_responder()

    # Add only assistant messages (no user messages)
    responder.memory = [{"role": "assistant", "content": "System message", "created_at": "2023-01-01T00:00:00Z", "type": "evaluation"}]

    with pytest.raises(ValueError, match="No user message found to regenerate response for"):
        responder.respond("/regenerate")


@patch("src.character_responder.CharacterPipeline.get_evaluation")
@patch("src.character_responder.CharacterPipeline.get_character_response")
def test_regular_conversation_still_works(mock_get_character_response, mock_get_evaluation):
    """Test that regular conversation still works after adding command handling."""
    responder = create_test_responder()

    # Set up processor responses for evaluation and character response
    evaluation_response = Evaluation(patterns_to_avoid="None", status_update="Normal conversation state", user_name="Alice", time_passed="5 seconds")
    character_response = "Hello there, Alice!"

    # Mock the CharacterPipeline methods
    mock_get_evaluation.return_value = evaluation_response
    mock_get_character_response.return_value = iter(character_response)

    result = responder.respond("Hello, my name is Alice")
    assert result == character_response

    # Verify that memory was updated correctly
    assert len(responder.memory) == 3  # user msg, eval msg, response msg
    assert responder.memory[0]["content"] == "Hello, my name is Alice"
    assert responder.memory[0]["role"] == "user"


def test_commands_with_persistent_memory():
    """Test that commands work correctly with persistent memory."""
    responder = create_test_responder(with_memory=True)

    # Track event callback calls
    events = []

    def mock_event_callback(event_type: str, **kwargs: str) -> None:
        events.append({"type": event_type, **kwargs})

    # Add some conversation history
    responder.memory = [
        {"role": "user", "content": "Hello", "created_at": "2023-01-01T00:00:00Z", "type": "conversation"},
        {"role": "assistant", "content": "Evaluation", "created_at": "2023-01-01T00:00:01Z", "type": "evaluation"},
        {"role": "assistant", "content": "Hi there!", "created_at": "2023-01-01T00:00:02Z", "type": "conversation"},
    ]
    responder._current_message_offset = 3

    result = responder.respond("/rewind", event_callback=mock_event_callback)

    # Verify delete_messages_from_offset was called instead of delete_session
    responder.persistent_memory.delete_messages_from_offset.assert_called_once_with(
        responder.session_id,
        "anonymous",
        0,  # delete_from_offset = 3 - 3 = 0
    )

    # Should return empty string and send command completion event
    assert result == ""
    assert len(events) == 1
    assert events[0]["type"] == "command"
    assert events[0]["succeeded"] == "true"
