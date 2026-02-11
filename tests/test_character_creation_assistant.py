from unittest.mock import Mock

import pytest

from src.character_creation_assistant import CharacterCreationAssistant
from src.models.character import PartialCharacter


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
            current_character=PartialCharacter(),
            conversation_history=[],
        )

        # Verify the response and updates
        assert response == ai_response
        assert isinstance(updates, PartialCharacter)
        assert updates.name == "Alice"
        assert updates.tagline == "A brave adventurer"
        assert updates.backstory == "Alice grew up in a small village."

    def test_process_message_without_updates(self, assistant, mock_processor):
        """Test processing a message that doesn't include character updates."""
        # Mock AI response without updates
        ai_response = "Can you tell me more about what kind of character you'd like to create?"

        mock_processor.respond_with_text.return_value = ai_response

        # Process the message
        response, updates = assistant.process_message(
            user_message="I want to create a character",
            current_character=PartialCharacter(),
            conversation_history=[],
        )

        # Verify no updates were extracted (should return empty PartialCharacter)
        assert response == ai_response
        assert isinstance(updates, PartialCharacter)
        assert updates.name == ""
        assert updates.tagline == ""
        assert updates.backstory == ""

    def test_process_message_with_conversation_history(self, assistant, mock_processor):
        """Test processing includes conversation history in the prompt."""
        from src.models.api_models import ChatMessageModel

        mock_processor.respond_with_text.return_value = "Great! Let me help with that."

        conversation_history = [
            ChatMessageModel(author="User", content="I want a warrior", is_user=True),
            ChatMessageModel(author="AI", content="What's the warrior's name?", is_user=False),
        ]

        assistant.process_message(
            user_message="Call them Bob",
            current_character=PartialCharacter(),
            conversation_history=conversation_history,
        )

        # Verify processor was called
        assert mock_processor.respond_with_text.called
        # Verify conversation history was passed as parameter
        call_kwargs = mock_processor.respond_with_text.call_args[1]
        conversation_history = call_kwargs["conversation_history"]
        assert len(conversation_history) == 2
        assert conversation_history[0]["role"] == "user"
        assert conversation_history[0]["content"] == "I want a warrior"
        assert conversation_history[1]["role"] == "assistant"
        assert conversation_history[1]["content"] == "What's the warrior's name?"

    def test_process_message_with_current_character(self, assistant, mock_processor):
        """Test processing includes current character state in the prompt."""
        mock_processor.respond_with_text.return_value = "Updated the backstory!"

        current_character = PartialCharacter(
            name="Bob",
            tagline="The brave",
        )

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

        updates = assistant._extract_character_updates(ai_response, PartialCharacter())

        assert isinstance(updates, PartialCharacter)
        assert updates.name == "Jane"
        assert updates.relationships == {
            "Bob": "Brother and rival",
            "Alice": "Childhood friend",
        }

    def test_extract_character_updates_with_ruleset_stats(self, assistant):
        """Test extracting updates with ruleset stats."""
        ai_response = """Your character explores many places!

<character_update>
{
  "name": "Explorer",
  "ruleset_id": "everyday-tension",
  "ruleset_stats": {"warmth": 8, "logic": 6}
}
</character_update>"""

        updates = assistant._extract_character_updates(ai_response, PartialCharacter())

        assert isinstance(updates, PartialCharacter)
        assert updates.name == "Explorer"
        assert updates.ruleset_id == "everyday-tension"
        assert updates.ruleset_stats == {"warmth": 8, "logic": 6}

    def test_extract_character_updates_filters_invalid_fields(self, assistant):
        """Test that invalid fields are filtered out from updates."""
        ai_response = """<character_update>
{
  "name": "Valid",
  "invalid_field": "This should be filtered",
  "backstory": "Valid backstory"
}
</character_update>"""

        updates = assistant._extract_character_updates(ai_response, PartialCharacter())

        assert isinstance(updates, PartialCharacter)
        assert updates.name == "Valid"
        assert updates.backstory == "Valid backstory"
        # Pydantic filters invalid fields automatically
        assert not hasattr(updates, "invalid_field")

    def test_extract_character_updates_handles_malformed_json(self, assistant):
        """Test that malformed JSON in updates returns current character unchanged."""
        ai_response = """<character_update>
{
  "name": "Test"
  "missing_comma": true
}
</character_update>"""

        current = PartialCharacter()
        updates = assistant._extract_character_updates(ai_response, current)

        # Should return the original unchanged character when JSON is malformed
        assert isinstance(updates, PartialCharacter)
        assert updates == current

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
            current_character=PartialCharacter(),
            conversation_history=[],
            streaming_callback=callback,
        )

        # Verify streaming method was called
        assert mock_processor.respond_with_stream.called
        # Verify callback was invoked for each chunk
        assert callback.call_count == 2
        callback.assert_any_call("Streaming ")
        callback.assert_any_call("response")

    def test_streaming_preserves_spaces_in_chunks(self, assistant, mock_processor):
        """Test that streaming chunks with leading/trailing spaces are preserved."""
        callback = Mock()
        # Mock streaming response with chunks that have spaces
        # These should be preserved and not stripped
        mock_processor.respond_with_stream.return_value = iter(["Hello", " world", " from", " AI"])

        response, _ = assistant.process_message(
            user_message="Create a character",
            current_character=PartialCharacter(),
            conversation_history=[],
            streaming_callback=callback,
        )

        # Verify callback was invoked with original chunks (including spaces)
        assert callback.call_count == 4
        callback.assert_any_call("Hello")
        callback.assert_any_call(" world")
        callback.assert_any_call(" from")
        callback.assert_any_call(" AI")

        # Verify the assembled response preserves spaces
        assert response == "Hello world from AI"

    def test_extract_character_updates_ignores_empty_values(self, assistant):
        """Test that empty string values are filtered out from updates."""
        ai_response = """<character_update>
{
  "name": "Valid",
  "backstory": "",
  "personality": "Cheerful"
}
</character_update>"""

        updates = assistant._extract_character_updates(ai_response, PartialCharacter())

        assert isinstance(updates, PartialCharacter)
        assert updates.name == "Valid"
        assert updates.personality == "Cheerful"
        assert updates.backstory == ""  # Empty string is allowed in PartialCharacter

    def test_extract_character_updates_filters_whitespace_only_strings(self, assistant):
        """Test that whitespace-only strings are allowed in PartialCharacter."""
        ai_response = """<character_update>
{
  "name": "Valid",
  "backstory": "   ",
  "personality": "Cheerful",
  "appearance": " \\t\\n ",
  "tagline": ""
}
</character_update>"""

        updates = assistant._extract_character_updates(ai_response, PartialCharacter())

        # PartialCharacter accepts whitespace strings - they can be trimmed later if needed
        assert isinstance(updates, PartialCharacter)
        assert updates.name == "Valid"
        assert updates.personality == "Cheerful"
        # These fields are present but contain whitespace
        assert updates.backstory == "   "
        assert updates.tagline == ""

    def test_extract_character_updates_filters_empty_collections(self, assistant):
        """Test that empty dicts and lists are allowed in PartialCharacter."""
        ai_response = """<character_update>
{
  "name": "Valid",
  "relationships": {},
  "ruleset_stats": {},
  "personality": "Brave"
}
</character_update>"""

        updates = assistant._extract_character_updates(ai_response, PartialCharacter())

        # PartialCharacter accepts empty collections
        assert isinstance(updates, PartialCharacter)
        assert updates.name == "Valid"
        assert updates.personality == "Brave"
        assert updates.relationships == {}
        assert updates.ruleset_stats == {}
