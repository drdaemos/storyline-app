from unittest.mock import Mock

import pytest

from src.character_creation_assistant import CharacterCreationAssistant


@pytest.fixture
def mock_processor():
    """Create a mock prompt processor."""
    processor = Mock()
    return processor


@pytest.fixture
def assistant(mock_processor):
    """Create a CharacterCreationAssistant with mock processor."""
    return CharacterCreationAssistant(prompt_processor=mock_processor)


class TestCharacterCreationAssistant:
    """Test suite for CharacterCreationAssistant."""

    def test_process_message_with_updates(self, assistant, mock_processor):
        """Test processing a message that includes character updates."""
        # Mock AI response with character update
        ai_response = """Sure! I'll create a character for you.

<character_update>
{
  "name": "Alice",
  "tagline": "A brave adventurer",
  "backstory": "Alice grew up in a small village."
}
</character_update>

I've created Alice, a brave adventurer with an interesting backstory!"""

        mock_processor.respond_with_text.return_value = ai_response

        # Process the message
        response, updates = assistant.process_message(
            user_message="Create a character named Alice",
            current_character={},
            conversation_history=[],
        )

        # Verify the response and updates
        assert response == ai_response
        assert updates == {
            "name": "Alice",
            "tagline": "A brave adventurer",
            "backstory": "Alice grew up in a small village.",
        }

    def test_process_message_without_updates(self, assistant, mock_processor):
        """Test processing a message that doesn't include character updates."""
        # Mock AI response without updates
        ai_response = "Can you tell me more about what kind of character you'd like to create?"

        mock_processor.respond_with_text.return_value = ai_response

        # Process the message
        response, updates = assistant.process_message(
            user_message="I want to create a character",
            current_character={},
            conversation_history=[],
        )

        # Verify no updates were extracted
        assert response == ai_response
        assert updates == {}

    def test_process_message_with_conversation_history(self, assistant, mock_processor):
        """Test processing includes conversation history in the prompt."""
        mock_processor.respond_with_text.return_value = "Great! Let me help with that."

        conversation_history = [
            {"author": "User", "content": "I want a warrior", "is_user": True},
            {"author": "AI", "content": "What's the warrior's name?", "is_user": False},
        ]

        assistant.process_message(
            user_message="Call them Bob",
            current_character={},
            conversation_history=conversation_history,
        )

        # Verify processor was called
        assert mock_processor.respond_with_text.called
        # Verify conversation history was included in the prompt
        call_kwargs = mock_processor.respond_with_text.call_args[1]
        user_prompt = call_kwargs["user_prompt"]
        assert "Previous conversation:" in user_prompt
        assert "User: I want a warrior" in user_prompt
        assert "Assistant: What's the warrior's name?" in user_prompt

    def test_process_message_with_current_character(self, assistant, mock_processor):
        """Test processing includes current character state in the prompt."""
        mock_processor.respond_with_text.return_value = "Updated the backstory!"

        current_character = {
            "name": "Bob",
            "tagline": "The brave",
        }

        assistant.process_message(
            user_message="Add a backstory",
            current_character=current_character,
            conversation_history=[],
        )

        # Verify current character state was included in the prompt
        call_kwargs = mock_processor.respond_with_text.call_args[1]
        user_prompt = call_kwargs["user_prompt"]
        assert "Current character state:" in user_prompt
        assert '"name": "Bob"' in user_prompt

    def test_extract_character_updates_with_relationships(self, assistant):
        """Test extracting updates with complex relationship structure."""
        ai_response = """Here's your character with relationships!

<character_update>
{
  "name": "Jane",
  "relationships": {
    "Bob": "Brother and rival",
    "Alice": "Childhood friend"
  }
}
</character_update>"""

        updates = assistant._extract_character_updates(ai_response, {})

        assert updates["name"] == "Jane"
        assert updates["relationships"] == {
            "Bob": "Brother and rival",
            "Alice": "Childhood friend",
        }

    def test_extract_character_updates_with_key_locations(self, assistant):
        """Test extracting updates with key_locations list."""
        ai_response = """Your character explores many places!

<character_update>
{
  "name": "Explorer",
  "key_locations": ["Ancient Temple", "Hidden Valley", "Crystal Caves"]
}
</character_update>"""

        updates = assistant._extract_character_updates(ai_response, {})

        assert updates["name"] == "Explorer"
        assert updates["key_locations"] == ["Ancient Temple", "Hidden Valley", "Crystal Caves"]

    def test_extract_character_updates_filters_invalid_fields(self, assistant):
        """Test that invalid fields are filtered out from updates."""
        ai_response = """<character_update>
{
  "name": "Valid",
  "invalid_field": "This should be filtered",
  "backstory": "Valid backstory"
}
</character_update>"""

        updates = assistant._extract_character_updates(ai_response, {})

        assert "name" in updates
        assert "backstory" in updates
        assert "invalid_field" not in updates

    def test_extract_character_updates_handles_malformed_json(self, assistant):
        """Test that malformed JSON in updates returns empty dict."""
        ai_response = """<character_update>
{
  "name": "Test"
  "missing_comma": true
}
</character_update>"""

        updates = assistant._extract_character_updates(ai_response, {})

        assert updates == {}

    def test_clean_response_text_removes_update_tags(self, assistant):
        """Test that clean_response_text removes character_update tags."""
        ai_response = """Here's your character!

<character_update>
{
  "name": "Test"
}
</character_update>

I've created the character for you."""

        clean_text = assistant.clean_response_text(ai_response)

        assert "<character_update>" not in clean_text
        assert "</character_update>" not in clean_text
        assert "Here's your character!" in clean_text
        assert "I've created the character for you." in clean_text

    def test_clean_response_text_handles_no_tags(self, assistant):
        """Test that clean_response_text works when there are no tags."""
        ai_response = "Just a normal response without any tags."

        clean_text = assistant.clean_response_text(ai_response)

        assert clean_text == ai_response

    def test_process_message_with_streaming_callback(self, assistant, mock_processor):
        """Test that streaming callback is invoked for each chunk."""
        callback = Mock()
        # Mock streaming response
        mock_processor.respond_with_stream.return_value = iter(["Streaming ", "response"])

        assistant.process_message(
            user_message="Create a character",
            current_character={},
            conversation_history=[],
            streaming_callback=callback,
        )

        # Verify streaming method was called
        assert mock_processor.respond_with_stream.called
        # Verify callback was invoked for each chunk
        assert callback.call_count == 2
        callback.assert_any_call("Streaming ")
        callback.assert_any_call("response")

    def test_extract_character_updates_ignores_empty_values(self, assistant):
        """Test that empty string values are filtered out from updates."""
        ai_response = """<character_update>
{
  "name": "Valid",
  "backstory": "",
  "personality": "Cheerful"
}
</character_update>"""

        updates = assistant._extract_character_updates(ai_response, {})

        assert "name" in updates
        assert "personality" in updates
        assert "backstory" not in updates  # Empty string should be filtered
