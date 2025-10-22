import tempfile
from pathlib import Path

from src.character_responder import CharacterResponder
from src.memory.conversation_memory import ConversationMemory
from src.memory.summary_memory import SummaryMemory
from src.models.character import Character
from src.models.character_responder_dependencies import CharacterResponderDependencies


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
        import os
        self.temp_dir = tempfile.mkdtemp()
        self.memory_dir = Path(self.temp_dir)

        # Set environment variable to use test database in temp directory
        self.original_database_url = os.environ.get("DATABASE_URL")
        test_db_path = Path(self.temp_dir) / "test_integration.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

        # Create test character
        self.character = Character(
            name="TestBot",
            tagline="Assistant",
            backstory="Test character for summary integration",
            personality="Helpful and direct",
            appearance="Digital assistant",
            relationships={"user": "helper"},
            key_locations=["digital space"],
            setting_description="Test digital environment",
        )

        # Create memory instances with test directory
        self.conversation_memory = ConversationMemory(memory_dir=self.memory_dir)
        self.summary_memory = SummaryMemory(memory_dir=self.memory_dir)

        # Databases are initialized automatically via DatabaseConfig

        self.session_id = "test-session-123"

    def teardown_method(self):
        """Clean up test files."""
        import os
        import shutil

        # Close database connections
        if hasattr(self, 'conversation_memory'):
            self.conversation_memory.close()
        if hasattr(self, 'summary_memory'):
            self.summary_memory.close()

        # Clean up temp directory
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

        # Restore original environment
        if self.original_database_url is not None:
            os.environ["DATABASE_URL"] = self.original_database_url
        elif "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]

    def create_dependencies_with_mock_responses(self, evaluation_response, summary_response: str) -> CharacterResponderDependencies:
        """Create dependencies with mock processors that return specific responses."""
        # Create a mock that can return different responses for different calls
        from src.models.evaluation import Evaluation

        class MockProcessorWithSummary:
            def __init__(self, eval_response, summary_response: str):
                self.eval_response = eval_response
                self.summary_response = summary_response
                self.logger = None
                self.call_count = 0

            def get_processor_specific_prompt(self) -> str:
                return "Mock processor specific prompt for testing"

            def set_logger(self, logger) -> None:
                self.logger = logger

            def respond_with_model(self, prompt: str, user_prompt: str, output_type, conversation_history=None, max_tokens=None, reasoning=False):
                # Return Evaluation object for evaluation calls
                if output_type == Evaluation:
                    return self.eval_response
                # For other model responses, return string
                return self.summary_response

            def respond_with_text(self, prompt: str, user_prompt: str, conversation_history=None, max_tokens=None, reasoning=False) -> str:
                # Return summary response if this looks like a summary call
                if "summarize" in prompt.lower() or "compress" in prompt.lower() or "Summary of previous interactions" in prompt or "Story main genre" in prompt:
                    return self.summary_response
                return str(self.eval_response)

            def respond_with_stream(self, prompt: str, user_prompt: str, conversation_history=None, max_tokens=None, reasoning=False):
                # Return summary response if this looks like a summary call
                if "Summary of previous interactions" in prompt or "previous interactions" in prompt.lower():
                    yield from self.summary_response
                else:
                    yield from str(self.eval_response)

        primary_processor = MockProcessorWithSummary(evaluation_response, summary_response)
        backup_processor = MockProcessorWithSummary(evaluation_response, summary_response)

        # Create mock chat logger
        from unittest.mock import Mock
        chat_logger = Mock()

        return CharacterResponderDependencies(
            primary_processor=primary_processor,
            backup_processor=backup_processor,
            conversation_memory=self.conversation_memory,
            summary_memory=self.summary_memory,
            chat_logger=chat_logger,
            session_id=self.session_id,
        )

    def test_summary_storage_during_compression(self):
        """Test that summaries are properly stored with offsets during memory compression."""
        # Mock responses for evaluation and summarization
        from src.models.evaluation import Evaluation

        evaluation_response = Evaluation(patterns_to_avoid="None", status_update="Normal conversation state", user_name="TestUser", time_passed="5 seconds")

        summary_response = "User and assistant had a brief conversation about testing. The user introduced themselves as TestUser."

        dependencies = self.create_dependencies_with_mock_responses(evaluation_response, summary_response)
        responder = CharacterResponder(self.character, dependencies)

        # Simulate enough interactions to trigger summarization
        from datetime import UTC, datetime

        for i in range(CharacterResponder.RESPONSES_COUNT_FOR_SUMMARIZATION_TRIGGER + 1):
            user_message = f"Test message {i}"
            # Mock the character response by directly adding messages (with type field)
            responder.memory.extend(
                [
                    {"role": "user", "content": user_message, "type": "conversation", "created_at": datetime.now(UTC).isoformat()},
                    {"role": "assistant", "content": f"Evaluation {i}", "type": "evaluation", "created_at": datetime.now(UTC).isoformat()},
                    {"role": "assistant", "content": f"Response {i}", "type": "conversation", "created_at": datetime.now(UTC).isoformat()},
                ]
            )
            responder._current_message_offset += 3

            # Save to persistent memory to maintain offset tracking
            if responder.persistent_memory:
                responder.persistent_memory.add_messages(
                    responder.character.name,
                    responder.session_id,
                    [
                        {"role": "user", "content": user_message, "type": "conversation", "created_at": datetime.now(UTC).isoformat()},
                        {"role": "assistant", "content": f"Evaluation {i}", "type": "evaluation", "created_at": datetime.now(UTC).isoformat()},
                        {"role": "assistant", "content": f"Response {i}", "type": "conversation", "created_at": datetime.now(UTC).isoformat()},
                    ],
                )

        # Manually trigger compression to test summary storage
        responder.compress_memory()

        # Verify summary was stored
        summaries = self.summary_memory.get_session_summaries(self.session_id, "anonymous")
        assert len(summaries) == 1

        stored_summary = summaries[0]
        assert stored_summary["character_id"] == "TestBot"
        assert stored_summary["session_id"] == self.session_id
        assert stored_summary["summary"] == summary_response
        assert stored_summary["start_offset"] >= 0
        assert stored_summary["end_offset"] >= stored_summary["start_offset"]

    def test_existing_summaries_loading(self):
        """Test that existing summaries are properly loaded and concatenated on initialization."""
        # Pre-populate summary memory with test summaries using XML format
        summary1 = """<story_summary>First summary of early conversation (messages 0-5)</story_summary>
<character_learnings>User introduced themselves</character_learnings>"""

        summary2 = """<story_summary>Second summary of middle conversation (messages 6-11)</story_summary>
<character_learnings>Discussed the case details</character_learnings>"""

        self.summary_memory.add_summary(character_id="TestBot", session_id=self.session_id, summary=summary1, start_offset=0, end_offset=5)
        self.summary_memory.add_summary(character_id="TestBot", session_id=self.session_id, summary=summary2, start_offset=6, end_offset=11)

        # Create responder which should load existing summaries
        dependencies = self.create_dependencies_with_mock_responses("test", "test")
        responder = CharacterResponder(self.character, dependencies)

        # Verify summaries were loaded and concatenated
        assert responder.memory_summary != ""
        assert "First summary of early conversation" in responder.memory_summary
        assert "Second summary of middle conversation" in responder.memory_summary

    def test_clear_session_removes_summaries(self):
        """Test that clearing session also removes associated summaries."""
        # Add test summaries
        self.summary_memory.add_summary(character_id="TestBot", session_id=self.session_id, summary="Test summary to be cleared", start_offset=0, end_offset=2)

        # Create responder and clear session
        dependencies = self.create_dependencies_with_mock_responses("test", "test")
        responder = CharacterResponder(self.character, dependencies)

        # Verify summary exists initially
        summaries_before = self.summary_memory.get_session_summaries(self.session_id, "anonymous")
        assert len(summaries_before) == 1

        # Clear session
        cleared = responder.clear_current_session()
        assert cleared is True

        # Verify summaries were cleared
        summaries_after = self.summary_memory.get_session_summaries(self.session_id, "anonymous")
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

        responder.persistent_memory.add_messages(responder.character.name, responder.session_id, initial_messages)

        # Create new responder to load existing messages
        responder2 = CharacterResponder(self.character, dependencies)

        # Verify offset tracking matches actual message count
        all_messages = responder2.persistent_memory.get_session_messages(responder2.session_id, "anonymous")
        assert len(all_messages) == 4
        assert responder2._current_message_offset == 4

    def test_summary_memory_disabled_gracefully_handled(self):
        """Test that the system works gracefully when summary memory is empty."""
        # Create mock chat logger
        from unittest.mock import Mock
        chat_logger = Mock()

        # Create dependencies with summary memory that returns empty results
        dependencies = CharacterResponderDependencies(
            primary_processor=MockPromptProcessor("test response"),
            backup_processor=MockPromptProcessor("backup response"),
            conversation_memory=self.conversation_memory,
            summary_memory=self.summary_memory,  # Use normal summary memory
            chat_logger=chat_logger,
            session_id=self.session_id,
        )

        responder = CharacterResponder(self.character, dependencies)

        # Should initialize with empty memory_summary
        assert responder.memory_summary == ""

        # Add messages to trigger compression (with proper message structure including "type")
        from datetime import UTC, datetime

        for i in range(CharacterResponder.RESPONSES_COUNT_FOR_SUMMARIZATION_TRIGGER + 5):
            responder.memory.extend(
                [
                    {"role": "user", "content": f"Message {i}", "type": "conversation", "created_at": datetime.now(UTC).isoformat()},
                    {"role": "assistant", "content": f"Response {i}", "type": "conversation", "created_at": datetime.now(UTC).isoformat()},
                ]
            )

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
            responder.memory.extend([{"role": "user", "content": f"Message {i}"}, {"role": "assistant", "content": f"Response {i}"}])
            responder._current_message_offset += 2

        # Manually create first summary to establish baseline
        responder.summary_memory.add_summary(
            character_id=responder.character.name,
            session_id=responder.session_id,
            summary="First summary",
            start_offset=0,
            end_offset=9,  # Covered first 10 messages (0-9)
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
        """Test that summarization works with summary memory that has no existing summaries."""
        # Create mock chat logger
        from unittest.mock import Mock
        chat_logger = Mock()

        # Create dependencies with summary memory that returns no summaries
        dependencies = CharacterResponderDependencies(
            primary_processor=MockPromptProcessor("test response"),
            backup_processor=MockPromptProcessor("backup response"),
            conversation_memory=self.conversation_memory,
            summary_memory=self.summary_memory,  # Use normal summary memory
            chat_logger=chat_logger,
            session_id=self.session_id,
        )

        responder = CharacterResponder(self.character, dependencies)

        # When no summaries exist, max_processed_offset is None, which becomes -1
        # Then messages_since_last_summary = _current_message_offset - (-1) - 1 = _current_message_offset
        trigger_threshold = responder.RESPONSES_COUNT_FOR_SUMMARIZATION_TRIGGER * responder.EPOCH_MESSAGES

        # Set offset just below threshold
        responder._current_message_offset = trigger_threshold - 1
        should_trigger = responder._should_trigger_summarization("new message")
        assert should_trigger is False

        # Add one more message to reach threshold
        responder._current_message_offset = trigger_threshold
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
