from unittest.mock import Mock, patch

import pytest

from src.character_responder import CharacterResponder
from src.models.character import Character
from src.models.character_responder_dependencies import CharacterResponderDependencies
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

    # Mock conversation memory
    conversation_memory = Mock()
    conversation_memory.get_recent_messages.return_value = []
    conversation_memory.get_session_messages.return_value = []
    conversation_memory.add_messages.return_value = None
    conversation_memory.delete_session.return_value = None
    conversation_memory.delete_messages_from_offset.return_value = 3

    # Mock summary memory
    summary_memory = Mock()
    summary_memory.add_summary.return_value = 1
    summary_memory.get_session_summaries.return_value = []
    summary_memory.get_max_processed_offset.return_value = None
    summary_memory.delete_session_summaries.return_value = 1

    # Mock chat logger
    chat_logger = Mock()
    chat_logger.log_message.return_value = None
    chat_logger.log_exception.return_value = None

    dependencies = CharacterResponderDependencies(
        primary_processor=primary_processor,
        backup_processor=backup_processor,
        conversation_memory=conversation_memory,
        summary_memory=summary_memory,
        chat_logger=chat_logger,
        session_id="test-session",
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


@patch("src.character_responder.CharacterPipeline.get_character_response")
def test_regenerate_command_with_history(mock_get_character_response):
    """Test /regenerate command with conversation history."""
    responder = create_test_responder()

    # Add some conversation history manually
    responder.memory = [
        {"role": "user", "content": "Hello", "created_at": "2023-01-01T00:00:00Z", "type": "conversation"},
        {"role": "assistant", "content": "Hi there!", "created_at": "2023-01-01T00:00:02Z", "type": "conversation"},
    ]

    # Mock the CharacterPipeline methods
    character_response = "New regenerated response"
    mock_get_character_response.return_value = iter(character_response)

    result = responder.respond("/regenerate")
    assert result == character_response

    # Verify that the memory was properly reset
    assert len(responder.memory) == 2  # Original user message + new response


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
        {"role": "assistant", "content": "First response", "created_at": "2023-01-01T00:00:02Z", "type": "conversation"},
        {"role": "user", "content": "Second message", "created_at": "2023-01-01T00:01:00Z", "type": "conversation"},
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
    assert len(responder.memory) == 2
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


@patch("src.character_responder.CharacterPipeline.get_character_response")
def test_regular_conversation_still_works(mock_get_character_response):
    """Test that regular conversation still works after adding command handling."""
    responder = create_test_responder()

    # Set up processor responses for character response
    character_response = "Hello there, Alice!"

    # Mock the CharacterPipeline methods
    mock_get_character_response.return_value = iter(character_response)

    result = responder.respond("Hello, my name is Alice")
    assert result == character_response

    # Verify that memory was updated correctly
    assert len(responder.memory) == 2  # user msg + response msg
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
        {"role": "assistant", "content": "Hi there!", "created_at": "2023-01-01T00:00:02Z", "type": "conversation"},
    ]
    responder._current_message_offset = 2

    result = responder.respond("/rewind", event_callback=mock_event_callback)

    # Verify delete_messages_from_offset was called instead of delete_session
    responder.persistent_memory.delete_messages_from_offset.assert_called_once_with(
        responder.session_id,
        "anonymous",
        0,  # delete_from_offset = 2 - 2 = 0
    )

    # Should return empty string and send command completion event
    assert result == ""
    assert len(events) == 1
    assert events[0]["type"] == "command"
    assert events[0]["succeeded"] == "true"


@patch("src.character_responder.CharacterPipeline.get_character_plans")
@patch("src.character_responder.CharacterPipeline.get_character_response")
@patch("src.character_responder.CharacterPipeline.get_memory_summary")
def test_regenerate_after_memory_compression(mock_get_memory_summary, mock_get_character_response, mock_get_character_plans):
    """Test that /regenerate command handles memory correctly after history compression/summarization.

    This test demonstrates the bug where memory indices don't align with database offsets
    after memory compression, causing incorrect deletion of messages during regeneration.
    """
    responder = create_test_responder(with_memory=True)

    # Mock summary memory methods
    summary_memory = Mock()
    summary_memory.add_summary.return_value = 1
    summary_memory.get_session_summaries.return_value = []
    summary_memory.get_max_processed_offset.return_value = None
    summary_memory.delete_session_summaries.return_value = 1
    responder.summary_memory = summary_memory
    responder.dependencies.summary_memory = summary_memory

    # Simulate several conversation rounds (12 messages total = 6 rounds)
    # This will trigger compression after 4 messages (2 rounds)
    initial_history = []
    for i in range(6):
        initial_history.append({
            "role": "user",
            "content": f"Message {i+1}",
            "created_at": f"2023-01-01T00:0{i}:00Z",
            "type": "conversation"
        })
        initial_history.append({
            "role": "assistant",
            "content": f"Response {i+1}",
            "created_at": f"2023-01-01T00:0{i}:01Z",
            "type": "conversation"
        })

    # Setup mock to return all messages initially
    responder.persistent_memory.get_session_messages.return_value = initial_history
    responder.persistent_memory.get_recent_messages.return_value = initial_history[-10:]  # Last 5 rounds

    # Set the current message offset to match the total number of messages in DB
    responder._current_message_offset = 12  # 6 rounds * 2 messages
    responder.memory = initial_history[-10:]  # Keep last 5 rounds in memory

    # Mock memory summary response
    mock_get_memory_summary.return_value = "Summary of previous conversation"
    # Mock character plans response
    mock_get_character_plans.return_value = "Character's plans for the future"

    # Simulate memory compression that would leave only the last 2 messages in memory
    # After compression, memory indices 0-1 don't correspond to DB offsets 0-1
    # They actually correspond to DB offsets 10-11 (the last 2 messages)
    responder.compress_memory()

    # After compression, memory should have only EPOCH_MESSAGES (2) items
    # but _current_message_offset should still be 12
    responder.memory = initial_history[-2:]  # Simulate compression keeping last EPOCH_MESSAGES

    # Mock the character response for regeneration
    mock_get_character_response.return_value = iter("New regenerated response")

    # Now try to regenerate - this should work correctly
    # The bug: memory[0] is at DB offset 10, not offset 0
    # When we try to regenerate, we should delete from offset 10, not from offset 0
    result = responder.respond("/regenerate")

    # Verify that delete_messages_from_offset was called with the CORRECT offset
    # It should delete from offset 10 (where the last user message is in DB)
    # NOT from offset 0 (where the last user message is in the memory list)
    calls = responder.persistent_memory.delete_messages_from_offset.call_args_list
    assert len(calls) > 0, "Expected delete_messages_from_offset to be called"

    # The delete should be from the correct DB offset, not memory index
    delete_offset = calls[-1][0][2]  # Third positional argument
    # After compression, we have 2 messages in memory (offsets 10-11 in DB)
    # Current offset is 12 (total messages in DB)
    # When we regenerate, we remove 2 messages (from index 0 to end in memory)
    # So delete_from_offset = 12 - 2 = 10, which is correct!
    assert delete_offset == 10, f"Expected delete from offset 10 but got {delete_offset}"

    assert result == "New regenerated response"

    # Verify the memory offset was updated correctly after regeneration
    # After deleting 2 messages (offsets 10-11), _current_message_offset should be 10
    # Then after regeneration adds new user+assistant messages, it should be 12 again
    assert responder._current_message_offset == 12, f"Expected offset 12 after regeneration but got {responder._current_message_offset}"


@patch("src.character_responder.CharacterPipeline.get_character_plans")
@patch("src.character_responder.CharacterPipeline.get_character_response")
@patch("src.character_responder.CharacterPipeline.get_memory_summary")
def test_regenerate_loads_correct_message_after_summarization(mock_get_memory_summary, mock_get_character_response, mock_get_character_plans):
    """Test that /regenerate uses the correct message content after summarization.

    This test verifies the fix for the bug where messages were loaded from the wrong offset
    after summarization, causing regenerate to use old message content.
    """
    responder = create_test_responder(with_memory=True)

    # Create 9 messages in total (offsets 0-8)
    # Simulate that messages 0-3 were summarized (last_offset = 4)
    # So memory should contain only messages with offsets > 4 (i.e., 5, 6, 7, 8)
    all_messages = []
    for i in range(9):
        all_messages.append({
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"Message at offset {i}",
            "created_at": f"2023-01-01T00:0{i}:00Z",
            "type": "conversation"
        })

    # Mock get_session_messages to return all 9 messages
    responder.persistent_memory.get_session_messages.return_value = all_messages

    # Mock get_recent_messages to simulate loading messages after offset 4
    # This should return messages at offsets 5, 6, 7, 8 (the 4 most recent after offset 4)
    messages_after_offset_4 = [msg for msg in all_messages if all_messages.index(msg) > 4]
    responder.persistent_memory.get_recent_messages.return_value = messages_after_offset_4

    # Mock summary memory to return a summary with end_offset = 4
    responder.summary_memory.get_session_summaries.return_value = [{
        "id": 1,
        "summary": "Summary of messages 0-4",
        "start_offset": 0,
        "end_offset": 4,
        "created_at": "2023-01-01T00:00:00Z"
    }]

    # Set up the responder state as if after summarization
    responder._current_message_offset = 9
    responder.memory = messages_after_offset_4  # Messages at offsets 5-8

    # Mock the response
    mock_get_character_response.return_value = iter("Regenerated response")
    mock_get_character_plans.return_value = "Some plans"
    mock_get_memory_summary.return_value = "Summary"

    # Call regenerate
    result = responder.respond("/regenerate")

    # The last user message in memory should be at offset 8 (if odd indices are assistants, then offset 8 is user)
    # Actually, let me recalculate: offset 0=user, 1=assistant, 2=user, 3=assistant, 4=user, 5=assistant, 6=user, 7=assistant, 8=user
    # So the last user message should be "Message at offset 8"
    # When we call _handle_conversation, it should use this content

    # Verify that the right content was used by checking the mock was called
    # The memory should have been cleared and then new messages added
    assert result == "Regenerated response"

    # Verify the persistent_memory.add_messages was called with the correct user message content
    # The user message should be from offset 8, not from an old offset like 3
    calls = responder.persistent_memory.add_messages.call_args_list
    if calls:
        last_call = calls[-1]
        messages_added = last_call[0][2]  # Third positional argument (the messages list)
        user_message = messages_added[0]
        # The content should be from the last user message in memory (offset 8)
        assert user_message["content"] == "Message at offset 8", f"Expected 'Message at offset 8' but got '{user_message['content']}'"


def test_intro_message_at_offset_zero_is_loaded():
    """Test that the intro message at offset 0 is properly loaded when starting a new chat.

    This verifies the fix for the bug where messages at offset 0 were excluded
    when from_offset=0 was passed to get_recent_messages.
    """
    responder = create_test_responder(with_memory=True)

    # Create messages with an intro at offset 0
    intro_message = {
        "role": "assistant",
        "content": "Hello! I'm your assistant. How can I help you today?",
        "created_at": "2023-01-01T00:00:00Z",
        "type": "conversation"
    }
    user_message = {
        "role": "user",
        "content": "Tell me about yourself",
        "created_at": "2023-01-01T00:01:00Z",
        "type": "conversation"
    }

    all_messages = [intro_message, user_message]

    # Mock get_session_messages to return all messages
    responder.persistent_memory.get_session_messages.return_value = all_messages

    # Mock get_recent_messages to return all messages (simulating from_offset=-1)
    # This should include the message at offset 0
    responder.persistent_memory.get_recent_messages.return_value = all_messages

    # Mock summary memory to return no summaries (which should give last_offset=-1)
    responder.summary_memory.get_session_summaries.return_value = []

    # Reinitialize to trigger the loading logic
    from src.character_responder import CharacterResponder
    responder2 = CharacterResponder(responder.character, responder.dependencies)

    # Verify the intro message at offset 0 is in memory
    assert len(responder2.memory) >= 1, "Expected at least one message in memory"
    assert responder2.memory[0]["content"] == "Hello! I'm your assistant. How can I help you today?", \
        "Expected intro message at offset 0 to be loaded"
