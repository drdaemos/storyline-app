import tempfile
from pathlib import Path

from src.character_responder import CharacterResponder
from src.conversation_memory import ConversationMemory
from src.models.character import Character
from src.models.character_responder_dependencies import CharacterResponderDependencies
from src.summary_memory import SummaryMemory


class MockPromptProcessor:
    def __init__(self, response: str):
        self.response = response
        self.logger = None

    def get_processor_specific_prompt(self) -> str:
        return "Mock processor specific prompt for testing"

    def set_logger(self, logger) -> None:
        self.logger = logger

    def respond_with_model(self, prompt: str, user_prompt: str, output_type, conversation_history=None, max_tokens=None):
        return self.response

    def respond_with_text(self, prompt: str, user_prompt: str, conversation_history=None, max_tokens=None, reasoning=False) -> str:
        return self.response

    def respond_with_stream(self, prompt: str, user_prompt: str, conversation_history=None, max_tokens=None):
        yield from self.response


class TestCharacterResponderSummaryIntegration:

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.memory_dir = Path(self.temp_dir)

        # Create test character
        self.character = Character(
            name="TestBot",
            role="Assistant",
            backstory="Test character for summary integration",
            personality="Helpful and direct",
            appearance="Digital assistant",
            relationships={"user": "helper"},
            key_locations=["digital space"],
            setting_description="Test digital environment"
        )

        # Create memory instances with test directory
        self.conversation_memory = ConversationMemory(memory_dir=self.memory_dir)
        self.summary_memory = SummaryMemory(memory_dir=self.memory_dir)

        # Override DB paths for isolation
        self.conversation_memory.db_path = self.memory_dir / "test_conversations.db"
        self.summary_memory.db_path = self.memory_dir / "test_summaries.db"

        # Initialize databases
        self.conversation_memory._init_database()
        self.summary_memory._init_database()

        self.session_id = "test-session-123"

    def teardown_method(self):
        """Clean up test files."""
        try:
            if self.conversation_memory.db_path.exists():
                self.conversation_memory.db_path.unlink()
            if self.summary_memory.db_path.exists():
                self.summary_memory.db_path.unlink()
        except PermissionError:
            pass

    def create_dependencies_with_mock_responses(self, evaluation_response: str, summary_response: str) -> CharacterResponderDependencies:
        """Create dependencies with mock processors that return specific responses."""
        # Create a mock that can return different responses for different calls
        class MockProcessorWithSummary:
            def __init__(self, eval_response: str, summary_response: str):
                self.eval_response = eval_response
                self.summary_response = summary_response
                self.logger = None
                self.call_count = 0

            def get_processor_specific_prompt(self) -> str:
                return "Mock processor specific prompt for testing"

            def set_logger(self, logger) -> None:
                self.logger = logger

            def respond_with_model(self, prompt: str, user_prompt: str, output_type, conversation_history=None, max_tokens=None):
                # Return summary response if this looks like a summary call
                if "Summary of previous interactions" in prompt or "previous interactions" in prompt.lower():
                    return self.summary_response
                return self.eval_response

            def respond_with_text(self, prompt: str, user_prompt: str, conversation_history=None, max_tokens=None, reasoning=False) -> str:
                # Return summary response if this looks like a summary call
                if ("summarize" in prompt.lower() or
                    "compress" in prompt.lower() or
                    "Summary of previous interactions" in prompt or
                    "Story main genre" in prompt):
                    return self.summary_response
                return self.eval_response

            def respond_with_stream(self, prompt: str, user_prompt: str, conversation_history=None, max_tokens=None):
                # Return summary response if this looks like a summary call
                if "Summary of previous interactions" in prompt or "previous interactions" in prompt.lower():
                    yield from self.summary_response
                else:
                    yield from self.eval_response

        primary_processor = MockProcessorWithSummary(evaluation_response, summary_response)
        backup_processor = MockProcessorWithSummary(evaluation_response, summary_response)

        return CharacterResponderDependencies(
            primary_processor=primary_processor,
            backup_processor=backup_processor,
            conversation_memory=self.conversation_memory,
            summary_memory=self.summary_memory,
            chat_logger=None,
            session_id=self.session_id
        )

    def test_summary_storage_during_compression(self):
        """Test that summaries are properly stored with offsets during memory compression."""
        # Mock responses for evaluation and summarization
        evaluation_response = """
        <user_name>TestUser</user_name>
        <continuation>option_1</continuation>
        <option_1>Continue conversation naturally</option_1>
        <status_update>Normal conversation state</status_update>
        """

        summary_response = "User and assistant had a brief conversation about testing. The user introduced themselves as TestUser."

        dependencies = self.create_dependencies_with_mock_responses(evaluation_response, summary_response)
        responder = CharacterResponder(self.character, dependencies)

        # Simulate enough interactions to trigger summarization
        for i in range(CharacterResponder.RESPONSES_COUNT_FOR_SUMMARIZATION_TRIGGER + 1):
            user_message = f"Test message {i}"
            # Mock the character response by directly adding messages
            responder.memory.extend([
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": f"Evaluation {i}"},
                {"role": "assistant", "content": f"Response {i}"}
            ])
            responder._current_message_offset += 3

            # Save to persistent memory to maintain offset tracking
            if responder.persistent_memory:
                responder.persistent_memory.add_messages(
                    responder.character.name,
                    responder.session_id,
                    [
                        {"role": "user", "content": user_message},
                        {"role": "assistant", "content": f"Evaluation {i}"},
                        {"role": "assistant", "content": f"Response {i}"}
                    ]
                )

        # Manually trigger compression to test summary storage
        responder.compress_memory()

        # Verify summary was stored
        summaries = self.summary_memory.get_session_summaries(self.session_id)
        assert len(summaries) == 1

        stored_summary = summaries[0]
        assert stored_summary["character_id"] == "TestBot"
        assert stored_summary["session_id"] == self.session_id
        assert stored_summary["summary"] == summary_response
        assert stored_summary["start_offset"] >= 0
        assert stored_summary["end_offset"] >= stored_summary["start_offset"]

    def test_existing_summaries_loading(self):
        """Test that existing summaries are properly loaded and concatenated on initialization."""
        # Pre-populate summary memory with test summaries
        self.summary_memory.add_summary(
            character_id="TestBot",
            session_id=self.session_id,
            summary="First summary of early conversation",
            start_offset=0,
            end_offset=5
        )

        self.summary_memory.add_summary(
            character_id="TestBot",
            session_id=self.session_id,
            summary="Second summary of middle conversation",
            start_offset=6,
            end_offset=11
        )

        # Create responder which should load existing summaries
        dependencies = self.create_dependencies_with_mock_responses("test", "test")
        responder = CharacterResponder(self.character, dependencies)

        # Verify summaries were loaded and concatenated
        assert responder.memory_summary != ""
        assert "First summary of early conversation" in responder.memory_summary
        assert "Second summary of middle conversation" in responder.memory_summary
        assert "messages 0-5" in responder.memory_summary
        assert "messages 6-11" in responder.memory_summary

    def test_clear_session_removes_summaries(self):
        """Test that clearing session also removes associated summaries."""
        # Add test summaries
        self.summary_memory.add_summary(
            character_id="TestBot",
            session_id=self.session_id,
            summary="Test summary to be cleared",
            start_offset=0,
            end_offset=2
        )

        # Create responder and clear session
        dependencies = self.create_dependencies_with_mock_responses("test", "test")
        responder = CharacterResponder(self.character, dependencies)

        # Verify summary exists initially
        summaries_before = self.summary_memory.get_session_summaries(self.session_id)
        assert len(summaries_before) == 1

        # Clear session
        cleared = responder.clear_current_session()
        assert cleared is True

        # Verify summaries were cleared
        summaries_after = self.summary_memory.get_session_summaries(self.session_id)
        assert len(summaries_after) == 0

        # Verify memory_summary was reset
        assert responder.memory_summary == ""

    def test_offset_tracking_accuracy(self):
        """Test that offset tracking accurately reflects message positions."""
        dependencies = self.create_dependencies_with_mock_responses("test", "test")
        responder = CharacterResponder(self.character, dependencies)

        # Add some messages directly to persistent memory to establish a baseline
        initial_messages = [
            {"role": "user", "content": "Message 0"},
            {"role": "assistant", "content": "Response 0"},
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"},
        ]

        responder.persistent_memory.add_messages(
            responder.character.name,
            responder.session_id,
            initial_messages
        )

        # Create new responder to load existing messages
        responder2 = CharacterResponder(self.character, dependencies)

        # Verify offset tracking matches actual message count
        all_messages = responder2.persistent_memory.get_session_messages(responder2.session_id)
        assert len(all_messages) == 4
        assert responder2._current_message_offset == 4

    def test_summary_memory_disabled_gracefully_handled(self):
        """Test that the system works gracefully when summary memory is disabled."""
        # Create dependencies without summary memory
        dependencies = CharacterResponderDependencies(
            primary_processor=MockPromptProcessor("test response"),
            backup_processor=MockPromptProcessor("backup response"),
            conversation_memory=self.conversation_memory,
            summary_memory=None,  # No summary memory
            chat_logger=None,
            session_id=self.session_id
        )

        responder = CharacterResponder(self.character, dependencies)

        # Should initialize with empty memory_summary
        assert responder.memory_summary == ""

        # Add messages to trigger compression
        for i in range(CharacterResponder.RESPONSES_COUNT_FOR_SUMMARIZATION_TRIGGER + 5):
            responder.memory.extend([
                {"role": "user", "content": f"Message {i}"},
                {"role": "assistant", "content": f"Response {i}"}
            ])

        # Compress memory should work without errors even without summary memory
        try:
            responder.compress_memory()
            # Should succeed without throwing exceptions
        except Exception as e:
            raise AssertionError(f"compress_memory failed when summary_memory is None: {e}") from e

    def test_summarization_trigger_based_on_offset_difference(self):
        """Test that summarization is triggered based on offset difference from last summary."""
        dependencies = self.create_dependencies_with_mock_responses("test", "test summary")
        responder = CharacterResponder(self.character, dependencies)

        # Add some initial messages and create first summary
        for i in range(5):
            responder.memory.extend([
                {"role": "user", "content": f"Message {i}"},
                {"role": "assistant", "content": f"Response {i}"}
            ])
            responder._current_message_offset += 2

        # Manually create first summary to establish baseline
        responder.summary_memory.add_summary(
            character_id=responder.character.name,
            session_id=responder.session_id,
            summary="First summary",
            start_offset=0,
            end_offset=9  # Covered first 10 messages (0-9)
        )

        # Should not trigger with few messages after last summary
        responder._current_message_offset = 12  # Only 2 messages since last summary
        should_trigger = responder._should_trigger_summarization("new message")
        assert should_trigger is False

        # Should trigger with many messages after last summary
        trigger_threshold = responder.RESPONSES_COUNT_FOR_SUMMARIZATION_TRIGGER * responder.EPOCH_MESSAGES
        responder._current_message_offset = 10 + trigger_threshold + 1  # Enough messages to trigger
        should_trigger = responder._should_trigger_summarization("new message")
        assert should_trigger is True

    def test_summarization_trigger_fallback_without_summary_memory(self):
        """Test that summarization falls back to memory size when summary memory is disabled."""
        # Create dependencies without summary memory
        dependencies = CharacterResponderDependencies(
            primary_processor=MockPromptProcessor("test response"),
            backup_processor=MockPromptProcessor("backup response"),
            conversation_memory=self.conversation_memory,
            summary_memory=None,  # No summary memory
            chat_logger=None,
            session_id=self.session_id
        )

        responder = CharacterResponder(self.character, dependencies)

        # Should use memory size as trigger when summary memory is not available
        trigger_threshold = responder.RESPONSES_COUNT_FOR_SUMMARIZATION_TRIGGER * responder.EPOCH_MESSAGES

        # Add messages below threshold
        for i in range(trigger_threshold - 1):
            responder.memory.append({"role": "user", "content": f"Message {i}"})

        should_trigger = responder._should_trigger_summarization("new message")
        assert should_trigger is False

        # Add one more message to reach threshold
        responder.memory.append({"role": "user", "content": "final message"})
        should_trigger = responder._should_trigger_summarization("new message")
        assert should_trigger is True

    def test_summarization_trigger_no_existing_summaries(self):
        """Test that summarization uses offset-based logic when no summaries exist yet."""
        dependencies = self.create_dependencies_with_mock_responses("test", "test summary")
        responder = CharacterResponder(self.character, dependencies)

        trigger_threshold = responder.RESPONSES_COUNT_FOR_SUMMARIZATION_TRIGGER * responder.EPOCH_MESSAGES

        # Set current offset to just below threshold (messages since -1 should be threshold - 1)
        responder._current_message_offset = trigger_threshold - 1
        should_trigger = responder._should_trigger_summarization("new message")
        assert should_trigger is False

        # Set current offset to reach threshold
        responder._current_message_offset = trigger_threshold
        should_trigger = responder._should_trigger_summarization("new message")
        assert should_trigger is True
