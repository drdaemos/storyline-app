import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from src.character_responder import CharacterResponder
from src.models.character import Character


class TestCharacterResponder:

    def setup_method(self):
        """Set up test character for each test."""
        self.test_character = Character(
            name="Alice",
            role="Detective",
            backstory="Former police officer turned private investigator",
            appearance="Tall woman with sharp eyes and graying hair",
            autonomy="independent",
            safety="cautious",
            openmindedness="moderate",
            emotional_stability="stable",
            attachment_pattern="secure",
            conscientiousness="organized",
            sociability="introverted",
            social_trust="suspicious",
            risk_approach="calculated",
            conflict_approach="assertive",
            leadership_style="director",
            stress_level="calm",
            energy_level="moderate",
            mood="focused"
        )

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_init(self, mock_processor_class):
        mock_processor = Mock()
        mock_processor_class.return_value = mock_processor

        responder = CharacterResponder(self.test_character)
        assert responder.character == self.test_character
        assert responder.processor is not None
        assert responder.streaming_callback is None
        assert responder.memory == []

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_respond_with_valid_xml_tags(self, mock_processor_class):
        mock_processor = Mock()

        # Mock the evaluation step
        evaluation_response = """
        <selected_option>
        Option A: Adjusts glasses nervously and responds thoughtfully
        </selected_option>
        """

        # Mock the character response step
        character_response = """
        Some preamble text
        <character_response>
        *adjusts glasses* I see what you mean. That's quite interesting.
        </character_response>
        Some trailing text
        """

        # Set up the mock to return different responses for each call
        mock_processor.process.side_effect = [evaluation_response, character_response]
        mock_processor_class.return_value = mock_processor

        responder = CharacterResponder(self.test_character)
        result = responder.respond("Hello there!")

        assert result == "*adjusts glasses* I see what you mean. That's quite interesting."
        assert mock_processor.process.call_count == 2

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_respond_without_xml_tags(self, mock_processor_class):
        mock_processor = Mock()
        # Two responses: evaluation and character response
        mock_processor.process.side_effect = [
            "Option A fallback",
            "Just a plain response without tags."
        ]
        mock_processor_class.return_value = mock_processor

        responder = CharacterResponder(self.test_character)
        result = responder.respond("Hello!")

        assert result == "Just a plain response without tags."

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_respond_with_streaming_callback(self, mock_processor_class):
        mock_processor = Mock()
        mock_processor.process.side_effect = [
            "<selected_option>Option A</selected_option>",
            "<character_response>Test response</character_response>"
        ]
        mock_processor_class.return_value = mock_processor

        callback_mock = Mock()
        responder = CharacterResponder(self.test_character)
        result = responder.respond("Hello!", streaming_callback=callback_mock)

        assert result == "Test response"
        callback_mock.assert_called_once_with("Test response")

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_respond_includes_character_attributes(self, mock_processor_class):
        mock_processor = Mock()
        mock_processor.process.side_effect = [
            "<selected_option>Option A</selected_option>",
            "<character_response>Response</character_response>"
        ]
        mock_processor_class.return_value = mock_processor

        responder = CharacterResponder(self.test_character)
        responder.respond("Test message")

        # Check that process was called with mapped character attributes
        # The first call is the evaluation, second is the character response
        call_args = mock_processor.process.call_args_list[0]  # First call (evaluation)
        variables = call_args[1]['variables']

        assert variables['character_name'] == "Alice"
        assert "Former police officer" in variables['character_background']
        assert variables['user_message'] == "Test message"
        assert "focused" in variables['emotional_state']
        assert "calm" in variables['emotional_state']

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_parse_character_response_with_tags(self, mock_processor_class):
        mock_processor_class.return_value = Mock()
        responder = CharacterResponder(self.test_character)

        response_text = """
        Some intro text
        <character_response>
        *nods thoughtfully* That makes sense to me.
        </character_response>
        Some outro text
        """

        result = responder._parse_character_response(response_text)
        assert result == "*nods thoughtfully* That makes sense to me."

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_parse_character_response_case_insensitive(self, mock_processor_class):
        mock_processor_class.return_value = Mock()
        responder = CharacterResponder(self.test_character)

        response_text = "<CHARACTER_RESPONSE>Test response</CHARACTER_RESPONSE>"
        result = responder._parse_character_response(response_text)
        assert result == "Test response"

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_parse_character_response_multiline(self, mock_processor_class):
        mock_processor_class.return_value = Mock()
        responder = CharacterResponder(self.test_character)

        response_text = """<character_response>
        *stands up slowly*
        Well, I suppose we should get going then.
        *picks up coat from chair*
        </character_response>"""

        result = responder._parse_character_response(response_text)
        expected = "*stands up slowly*\n        Well, I suppose we should get going then.\n        *picks up coat from chair*"
        assert result == expected

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_parse_character_response_multiple_tags_returns_first(self, mock_processor_class):
        mock_processor_class.return_value = Mock()
        responder = CharacterResponder(self.test_character)

        response_text = """
        <character_response>First response</character_response>
        <character_response>Second response</character_response>
        """

        result = responder._parse_character_response(response_text)
        assert result == "First response"

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_parse_character_response_no_tags_returns_original(self, mock_processor_class):
        mock_processor_class.return_value = Mock()
        responder = CharacterResponder(self.test_character)

        response_text = "Just a plain response without any tags."
        result = responder._parse_character_response(response_text)
        assert result == "Just a plain response without any tags."

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_parse_selected_option_with_tags(self, mock_processor_class):
        mock_processor_class.return_value = Mock()
        responder = CharacterResponder(self.test_character)

        response_text = """
        Some intro text
        <selected_option>
        Option A: Character adjusts glasses nervously
        </selected_option>
        Some outro text
        """

        result = responder._parse_selected_option(response_text)
        assert result == "Option A: Character adjusts glasses nervously"

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_parse_selected_option_no_tags_returns_original(self, mock_processor_class):
        mock_processor_class.return_value = Mock()
        responder = CharacterResponder(self.test_character)

        response_text = "Just a plain response without any tags."
        result = responder._parse_selected_option(response_text)
        assert result == "Just a plain response without any tags."

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_update_character_state_private_method(self, mock_processor_class):
        mock_processor_class.return_value = Mock()
        responder = CharacterResponder(self.test_character)

        state_updates = {
            "mood": "excited",
            "stress_level": "pressured",
            "energy_level": "energetic"
        }

        responder._update_character_state(state_updates)

        assert responder.character.mood == "excited"
        assert responder.character.stress_level == "pressured"
        assert responder.character.energy_level == "energetic"

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_update_character_state_ignores_invalid_attributes(self, mock_processor_class):
        mock_processor_class.return_value = Mock()
        responder = CharacterResponder(self.test_character)

        state_updates = {
            "mood": "happy",
            "nonexistent_attr": "should_be_ignored"
        }

        responder._update_character_state(state_updates)

        assert responder.character.mood == "happy"
        assert not hasattr(responder.character, "nonexistent_attr")

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_update_state_public_method(self, mock_processor_class):
        mock_processor_class.return_value = Mock()
        responder = CharacterResponder(self.test_character)

        responder.update_state(mood="jubilant", stress_level="relaxed")

        assert responder.character.mood == "jubilant"
        assert responder.character.stress_level == "relaxed"

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_update_state_with_kwargs(self, mock_processor_class):
        mock_processor_class.return_value = Mock()
        responder = CharacterResponder(self.test_character)

        updates = {"energy_level": "exhausted", "mood": "frustrated"}
        responder.update_state(**updates)

        assert responder.character.energy_level == "exhausted"
        assert responder.character.mood == "frustrated"

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_prompt_includes_all_character_attributes(self, mock_processor_class):
        mock_processor = Mock()
        mock_processor.process.return_value = "<character_response>Response</character_response>"
        mock_processor_class.return_value = mock_processor

        responder = CharacterResponder(self.test_character)
        responder.respond("Test")

        call_args = mock_processor.process.call_args_list[0]  # First call (evaluation)
        prompt_text = call_args[1]['prompt']

        # Check that prompt includes mapped character attribute values
        assert "Character Name: Alice" in prompt_text
        assert "Former police officer" in prompt_text
        assert "Autonomy: independent" in prompt_text
        assert "Mood: focused" in prompt_text
        assert "Character Goals/Desires:" in prompt_text

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_map_character_to_prompt_variables(self, mock_processor_class):
        mock_processor_class.return_value = Mock()
        responder = CharacterResponder(self.test_character)

        variables = responder._map_character_to_prompt_variables("Hello there!")

        # Check all required variables are present
        required_vars = [
            "character_name", "character_background", "character_traits",
            "emotional_state", "character_goals", "current_setting",
            "relationship_status", "user_message"
        ]

        for var in required_vars:
            assert var in variables

        # Check specific mappings
        assert variables["character_name"] == "Alice"
        assert "Former police officer" in variables["character_background"]
        assert "Tall woman" in variables["character_background"]
        assert "Autonomy: independent" in variables["character_traits"]
        assert "Safety: cautious" in variables["character_traits"]
        assert "Mood: focused" in variables["emotional_state"]
        assert "Stress Level: calm" in variables["emotional_state"]
        assert "Energy Level: moderate" in variables["emotional_state"]
        assert variables["character_goals"] == ""
        assert variables["user_message"] == "Hello there!"

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_map_character_to_prompt_variables_personality_traits_format(self, mock_processor_class):
        mock_processor_class.return_value = Mock()
        responder = CharacterResponder(self.test_character)

        variables = responder._map_character_to_prompt_variables("Test")
        traits = variables["character_traits"]

        # Check that all personality traits are included
        expected_traits = [
            "Autonomy: independent",
            "Safety: cautious",
            "Openmindedness: moderate",
            "Emotional Stability: stable",
            "Attachment Pattern: secure",
            "Conscientiousness: organized",
            "Sociability: introverted",
            "Social Trust: suspicious",
            "Risk Approach: calculated",
            "Conflict Approach: assertive",
            "Leadership Style: director"
        ]

        for trait in expected_traits:
            assert trait in traits

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_map_character_to_prompt_variables_default_values(self, mock_processor_class):
        mock_processor_class.return_value = Mock()
        responder = CharacterResponder(self.test_character)

        variables = responder._map_character_to_prompt_variables("Test message")

        # Check default values for variables not in Character model
        assert variables["current_setting"] == ""
        assert variables["relationship_status"] == ""

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_respond_uses_mapping_function(self, mock_processor_class):
        mock_processor = Mock()
        mock_processor.process.side_effect = [
            "<selected_option>Option A</selected_option>",
            "<character_response>Test response</character_response>"
        ]
        mock_processor_class.return_value = mock_processor

        responder = CharacterResponder(self.test_character)
        responder.respond("Hello!")

        # Check that mapped variables are used instead of raw character dict
        call_args = mock_processor.process.call_args_list[0]  # First call (evaluation)
        variables = call_args[1]['variables']

        # Should have mapped variables, not raw character attributes
        assert "character_name" in variables
        assert "character_background" in variables
        assert "character_traits" in variables
        assert "emotional_state" in variables
        assert variables["character_name"] == "Alice"

        # Should NOT have raw character attributes
        assert "name" not in variables
        assert "backstory" not in variables
        assert "appearance" not in variables

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_processor_called_with_correct_parameters(self, mock_processor_class):
        mock_processor = Mock()
        mock_processor.process.side_effect = [
            "<selected_option>Option A</selected_option>",
            "<character_response>Response</character_response>"
        ]
        mock_processor_class.return_value = mock_processor

        responder = CharacterResponder(self.test_character)
        responder.respond("Test message")

        # Check both calls to process
        call_args_list = mock_processor.process.call_args_list
        assert len(call_args_list) == 2

        # Check first call (evaluation)
        first_call = call_args_list[0]
        assert first_call[1]['output_type'] is str
        assert isinstance(first_call[1]['variables'], dict)

        # Check second call (character response)
        second_call = call_args_list[1]
        assert second_call[1]['output_type'] is str
        assert isinstance(second_call[1]['variables'], dict)

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_memory_updates_after_response(self, mock_processor_class):
        mock_processor = Mock()
        mock_processor.process.side_effect = [
            "<selected_option>Option A</selected_option>",
            "<character_response>Test response</character_response>"
        ]
        mock_processor_class.return_value = mock_processor

        responder = CharacterResponder(self.test_character)
        assert len(responder.memory) == 0

        responder.respond("Hello!")

        # Memory should now contain the user message and full response
        assert len(responder.memory) == 2
        assert responder.memory[0]["role"] == "user"
        assert responder.memory[0]["content"] == "Hello!"
        assert responder.memory[1]["role"] == "assistant"
        # The full response is stored, not just the parsed part
        assert "<character_response>Test response</character_response>" in responder.memory[1]["content"]

    @patch('src.character_responder.ClaudePromptProcessor')
    @patch('src.character_responder.ConversationMemory')
    def test_init_with_persistent_memory_enabled(self, mock_memory_class, mock_processor_class):
        """Test initialization with persistent memory enabled."""
        mock_memory = Mock()
        mock_memory.create_session.return_value = "test-session-123"
        mock_memory.get_recent_messages.return_value = []
        mock_memory_class.return_value = mock_memory
        mock_processor_class.return_value = Mock()

        responder = CharacterResponder(self.test_character, use_persistent_memory=True)

        assert responder.use_persistent_memory is True
        assert responder.persistent_memory == mock_memory
        assert responder.session_id == "test-session-123"
        mock_memory.create_session.assert_called_once_with("Alice")
        mock_memory.get_recent_messages.assert_called_once_with("Alice", "test-session-123", limit=10)

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_init_with_persistent_memory_disabled(self, mock_processor_class):
        """Test initialization with persistent memory disabled."""
        mock_processor_class.return_value = Mock()

        responder = CharacterResponder(self.test_character, use_persistent_memory=False)

        assert responder.use_persistent_memory is False
        assert responder.persistent_memory is None
        assert responder.session_id is None
        assert responder.memory == []

    @patch('src.character_responder.ClaudePromptProcessor')
    @patch('src.character_responder.ConversationMemory')
    def test_init_with_existing_session_id(self, mock_memory_class, mock_processor_class):
        """Test initialization with existing session ID."""
        mock_memory = Mock()
        mock_memory.get_recent_messages.return_value = [
            {"role": "user", "content": "Previous message"}
        ]
        mock_memory_class.return_value = mock_memory
        mock_processor_class.return_value = Mock()

        responder = CharacterResponder(self.test_character, session_id="existing-session", use_persistent_memory=True)

        assert responder.session_id == "existing-session"
        assert len(responder.memory) == 1
        mock_memory.get_recent_messages.assert_called_once_with("Alice", "existing-session", limit=10)

    @patch('src.character_responder.ClaudePromptProcessor')
    @patch('src.character_responder.ConversationMemory')
    def test_respond_saves_to_persistent_memory(self, mock_memory_class, mock_processor_class):
        """Test that respond method saves messages to persistent memory."""
        mock_memory = Mock()
        mock_memory.create_session.return_value = "test-session"
        mock_memory.get_recent_messages.return_value = []
        mock_memory_class.return_value = mock_memory

        mock_processor = Mock()
        mock_processor.process.side_effect = [
            "<selected_option>Option A</selected_option>",
            "<character_response>Test response</character_response>"
        ]
        mock_processor_class.return_value = mock_processor

        responder = CharacterResponder(self.test_character, use_persistent_memory=True)
        responder.respond("Hello!")

        # Verify messages were saved to persistent memory
        assert mock_memory.add_message.call_count == 2
        mock_memory.add_message.assert_any_call("Alice", "test-session", "user", "Hello!")
        # Second call should have the combined evaluation + response
        second_call_args = mock_memory.add_message.call_args_list[1]
        assert second_call_args[0][2] == "assistant"  # role
        assert "<selected_option>Option A</selected_option>" in second_call_args[0][3]  # content
        assert "<character_response>Test response</character_response>" in second_call_args[0][3]

    @patch('src.character_responder.ClaudePromptProcessor')
    @patch('src.character_responder.ConversationMemory')
    def test_load_session(self, mock_memory_class, mock_processor_class):
        """Test loading a different session."""
        mock_memory = Mock()
        mock_memory.create_session.return_value = "initial-session"
        mock_memory.get_recent_messages.side_effect = [
            [],  # Initial session (empty)
            [{"role": "user", "content": "Loaded message"}]  # Loaded session
        ]
        mock_memory.get_session_summary.return_value = {
            "character_id": "Alice",
            "session_id": "target-session"
        }
        mock_memory_class.return_value = mock_memory
        mock_processor_class.return_value = Mock()

        responder = CharacterResponder(self.test_character, use_persistent_memory=True)

        result = responder.load_session("target-session")

        assert result is True
        assert responder.session_id == "target-session"
        assert len(responder.memory) == 1
        assert responder.memory[0]["content"] == "Loaded message"

    @patch('src.character_responder.ClaudePromptProcessor')
    @patch('src.character_responder.ConversationMemory')
    def test_load_session_wrong_character(self, mock_memory_class, mock_processor_class):
        """Test loading session that belongs to different character."""
        mock_memory = Mock()
        mock_memory.create_session.return_value = "initial-session"
        mock_memory.get_recent_messages.return_value = []
        mock_memory.get_session_summary.return_value = {
            "character_id": "Bob",  # Different character
            "session_id": "target-session"
        }
        mock_memory_class.return_value = mock_memory
        mock_processor_class.return_value = Mock()

        responder = CharacterResponder(self.test_character, use_persistent_memory=True)

        result = responder.load_session("target-session")

        assert result is False
        assert responder.session_id == "initial-session"  # Unchanged

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_load_session_without_persistent_memory(self, mock_processor_class):
        """Test loading session when persistent memory is disabled."""
        mock_processor_class.return_value = Mock()

        responder = CharacterResponder(self.test_character, use_persistent_memory=False)

        result = responder.load_session("some-session")

        assert result is False

    @patch('src.character_responder.ClaudePromptProcessor')
    @patch('src.character_responder.ConversationMemory')
    def test_get_session_history(self, mock_memory_class, mock_processor_class):
        """Test getting session history."""
        mock_memory = Mock()
        mock_memory.create_session.return_value = "test-session"
        mock_memory.get_recent_messages.return_value = []
        mock_memory.get_character_sessions.return_value = [
            {"session_id": "session1", "message_count": 5},
            {"session_id": "session2", "message_count": 3}
        ]
        mock_memory_class.return_value = mock_memory
        mock_processor_class.return_value = Mock()

        responder = CharacterResponder(self.test_character, use_persistent_memory=True)

        history = responder.get_session_history()

        assert history is not None
        assert len(history) == 2
        assert history[0]["session_id"] == "session1"
        mock_memory.get_character_sessions.assert_called_once_with("Alice")

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_get_session_history_without_persistent_memory(self, mock_processor_class):
        """Test getting session history when persistent memory is disabled."""
        mock_processor_class.return_value = Mock()

        responder = CharacterResponder(self.test_character, use_persistent_memory=False)

        history = responder.get_session_history()

        assert history is None

    @patch('src.character_responder.ClaudePromptProcessor')
    @patch('src.character_responder.ConversationMemory')
    def test_clear_current_session(self, mock_memory_class, mock_processor_class):
        """Test clearing current session."""
        mock_memory = Mock()
        mock_memory.create_session.return_value = "test-session"
        mock_memory.get_recent_messages.return_value = []
        mock_memory_class.return_value = mock_memory
        mock_processor_class.return_value = Mock()

        responder = CharacterResponder(self.test_character, use_persistent_memory=True)
        # Add some memory
        responder.memory = [{"role": "user", "content": "test"}]

        result = responder.clear_current_session()

        assert result is True
        assert responder.memory == []
        mock_memory.delete_session.assert_called_once_with("test-session")

    @patch('src.character_responder.ClaudePromptProcessor')
    @patch('src.character_responder.ConversationMemory')
    def test_create_new_session(self, mock_memory_class, mock_processor_class):
        """Test creating a new session."""
        mock_memory = Mock()
        mock_memory.create_session.side_effect = ["initial-session", "new-session"]
        mock_memory.get_recent_messages.return_value = []
        mock_memory_class.return_value = mock_memory
        mock_processor_class.return_value = Mock()

        responder = CharacterResponder(self.test_character, use_persistent_memory=True)
        # Add some memory
        responder.memory = [{"role": "user", "content": "test"}]

        new_session_id = responder.create_new_session()

        assert new_session_id == "new-session"
        assert responder.session_id == "new-session"
        assert responder.memory == []
        assert mock_memory.create_session.call_count == 2  # Initial + new


    @patch('src.character_responder.ClaudePromptProcessor')
    def test_conversation_logging(self, mock_processor_class):
        """Test that conversations are properly logged."""
        mock_processor = Mock()
        mock_processor.process.side_effect = [
            "<selected_option>Option A</selected_option>Evaluation text",
            "<character_response>Hello there!</character_response>Response text"
        ]
        mock_processor_class.return_value = mock_processor

        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            responder = CharacterResponder(
                self.test_character,
                session_id="test123",
                use_persistent_memory=False,
                logs_dir=logs_dir
            )

            try:
                # Make a response to trigger logging
                responder.respond("Hello character!")

                # Check that log file was created and contains expected content
                assert responder.chat_logger.log_file_path.exists()

                log_content = responder.chat_logger.log_file_path.read_text(encoding='utf-8')
                assert "=== SESSION START: Alice ===" in log_content
                assert "USER: Hello character!" in log_content
                assert "ASSISTANT (RAW):" in log_content
                assert "CHARACTER: Hello there!" in log_content
                assert "---" in log_content  # Separator
            finally:
                # Close logger to release file handles
                responder.chat_logger.close_logger()
                # Clean up log file
                if responder.chat_logger.log_file_path.exists():
                    responder.chat_logger.log_file_path.unlink()

    @patch('src.character_responder.ClaudePromptProcessor')
    def test_multiple_conversation_logging(self, mock_processor_class):
        """Test that multiple conversations are logged in sequence."""
        mock_processor = Mock()
        mock_processor.process.side_effect = [
            # First conversation
            "<selected_option>Option A</selected_option>",
            "<character_response>First response</character_response>",
            # Second conversation
            "<selected_option>Option B</selected_option>",
            "<character_response>Second response</character_response>"
        ]
        mock_processor_class.return_value = mock_processor

        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            responder = CharacterResponder(
                self.test_character,
                use_persistent_memory=False,
                logs_dir=logs_dir
            )

            try:
                # Make multiple responses
                responder.respond("First message")
                responder.respond("Second message")

                # Check log content
                log_content = responder.chat_logger.log_file_path.read_text(encoding='utf-8')
                assert log_content.count("USER:") == 2
                assert log_content.count("ASSISTANT (RAW):") == 2
                assert log_content.count("CHARACTER:") == 2
                assert "First message" in log_content
                assert "Second message" in log_content
                assert "First response" in log_content
                assert "Second response" in log_content
            finally:
                responder.chat_logger.close_logger()
                # Clean up log file
                if responder.chat_logger.log_file_path.exists():
                    responder.chat_logger.log_file_path.unlink()

