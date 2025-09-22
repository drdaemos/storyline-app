import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch
import os

from src.memory.conversation_memory import ConversationMemory


class TestConversationMemory:

    def setup_method(self):
        """Set up a temporary memory directory with test database for each test."""
        self.temp_dir = tempfile.mkdtemp()
        # Set environment variable to use test database
        self.original_db_name = os.environ.get('DB_NAME')
        os.environ['DB_NAME'] = 'conversations_test.db'
        # Create custom memory instance that uses test database
        self.memory = ConversationMemory(memory_dir=Path(self.temp_dir))
        self.character_id = "test_character"

    def teardown_method(self):
        """Clean up test environment."""
        # Restore original environment
        if self.original_db_name is not None:
            os.environ['DB_NAME'] = self.original_db_name
        elif 'DB_NAME' in os.environ:
            del os.environ['DB_NAME']

    def test_create_session(self):
        """Test session creation."""
        session_id = self.memory.create_session(self.character_id)

        assert isinstance(session_id, str)
        assert len(session_id) > 0
        # Should be a valid UUID
        uuid.UUID(session_id)  # Raises ValueError if invalid

    def test_add_message(self):
        """Test adding a message to memory."""
        session_id = self.memory.create_session(self.character_id)

        message_id = self.memory.add_message(
            self.character_id,
            session_id,
            "user",
            "Hello there!"
        )

        assert isinstance(message_id, int)
        assert message_id > 0

    def test_get_session_messages(self):
        """Test retrieving session messages."""
        session_id = self.memory.create_session(self.character_id)

        # Add some messages
        self.memory.add_message(self.character_id, session_id, "user", "Hello!")
        self.memory.add_message(self.character_id, session_id, "assistant", "Hi there!")
        self.memory.add_message(self.character_id, session_id, "user", "How are you?")

        messages = self.memory.get_session_messages(session_id)

        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello!"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Hi there!"
        assert messages[2]["role"] == "user"
        assert messages[2]["content"] == "How are you?"

    def test_get_session_messages_with_limit(self):
        """Test retrieving session messages with limit."""
        session_id = self.memory.create_session(self.character_id)

        # Add multiple messages
        for i in range(5):
            self.memory.add_message(self.character_id, session_id, "user", f"Message {i}")

        messages = self.memory.get_session_messages(session_id, limit=3)

        assert len(messages) == 3
        # Should get the first 3 messages (chronological order)
        assert messages[0]["content"] == "Message 0"
        assert messages[1]["content"] == "Message 1"
        assert messages[2]["content"] == "Message 2"

    def test_get_session_messages_empty_session(self):
        """Test retrieving messages from empty session."""
        session_id = self.memory.create_session(self.character_id)

        messages = self.memory.get_session_messages(session_id)

        assert messages == []

    def test_get_character_sessions(self):
        """Test retrieving character sessions."""
        # Create multiple sessions with messages
        session1 = self.memory.create_session(self.character_id)
        session2 = self.memory.create_session(self.character_id)

        self.memory.add_message(self.character_id, session1, "user", "Session 1 message")
        self.memory.add_message(self.character_id, session2, "user", "Session 2 message")
        self.memory.add_message(self.character_id, session2, "assistant", "Session 2 response")

        sessions = self.memory.get_character_sessions(self.character_id)

        assert len(sessions) == 2
        # Should be ordered by last_message_time DESC
        assert sessions[0]["session_id"] == session2  # More recent
        assert sessions[0]["message_count"] == 2
        assert sessions[1]["session_id"] == session1
        assert sessions[1]["message_count"] == 1

    def test_get_character_sessions_with_limit(self):
        """Test retrieving character sessions with limit."""
        # Create more sessions than the limit
        for i in range(5):
            session_id = self.memory.create_session(self.character_id)
            self.memory.add_message(self.character_id, session_id, "user", f"Message {i}")

        sessions = self.memory.get_character_sessions(self.character_id, limit=3)

        assert len(sessions) == 3

    def test_get_character_sessions_no_sessions(self):
        """Test retrieving sessions for character with no sessions."""
        sessions = self.memory.get_character_sessions("nonexistent_character")

        assert sessions == []

    def test_get_recent_messages(self):
        """Test retrieving recent messages."""
        session_id = self.memory.create_session(self.character_id)

        # Add multiple messages
        for i in range(10):
            self.memory.add_message(self.character_id, session_id, "user", f"Message {i}")

        recent = self.memory.get_recent_messages(session_id, limit=5)

        assert len(recent) == 5
        # Should get the last 5 messages in chronological order
        assert recent[0]["content"] == "Message 5"
        assert recent[4]["content"] == "Message 9"

    def test_get_recent_messages_empty_session(self):
        """Test retrieving recent messages from empty session."""
        session_id = self.memory.create_session(self.character_id)

        recent = self.memory.get_recent_messages(session_id)

        assert recent == []

    def test_delete_session(self):
        """Test deleting a session."""
        session_id = self.memory.create_session(self.character_id)

        # Add messages
        self.memory.add_message(self.character_id, session_id, "user", "Message 1")
        self.memory.add_message(self.character_id, session_id, "assistant", "Response 1")

        # Verify messages exist
        messages = self.memory.get_session_messages(session_id)
        assert len(messages) == 2

        # Delete session
        deleted_count = self.memory.delete_session(session_id)
        assert deleted_count == 2

        # Verify messages are gone
        messages = self.memory.get_session_messages(session_id)
        assert len(messages) == 0

    def test_delete_nonexistent_session(self):
        """Test deleting a nonexistent session."""
        fake_session_id = str(uuid.uuid4())

        deleted_count = self.memory.delete_session(fake_session_id)
        assert deleted_count == 0

    def test_clear_character_memory(self):
        """Test clearing all memory for a character."""
        # Create multiple sessions
        session1 = self.memory.create_session(self.character_id)
        session2 = self.memory.create_session(self.character_id)

        # Add messages to both sessions
        self.memory.add_message(self.character_id, session1, "user", "Session 1")
        self.memory.add_message(self.character_id, session2, "user", "Session 2")

        # Create session for different character
        other_character = "other_character"
        other_session = self.memory.create_session(other_character)
        self.memory.add_message(other_character, other_session, "user", "Other character")

        # Clear memory for test character
        deleted_count = self.memory.clear_character_memory(self.character_id)
        assert deleted_count == 2

        # Verify test character messages are gone
        sessions = self.memory.get_character_sessions(self.character_id)
        assert len(sessions) == 0

        # Verify other character messages remain
        other_sessions = self.memory.get_character_sessions(other_character)
        assert len(other_sessions) == 1

    def test_get_session_summary(self):
        """Test getting session summary."""
        session_id = self.memory.create_session(self.character_id)

        # Add messages
        self.memory.add_message(self.character_id, session_id, "user", "First message")
        self.memory.add_message(self.character_id, session_id, "assistant", "First response")
        self.memory.add_message(self.character_id, session_id, "user", "Second message")

        summary = self.memory.get_session_summary(session_id)

        assert summary is not None
        assert summary["session_id"] == session_id
        assert summary["character_id"] == self.character_id
        assert summary["message_count"] == 3
        assert "first_message_time" in summary
        assert "last_message_time" in summary

    def test_get_session_summary_nonexistent(self):
        """Test getting summary for nonexistent session."""
        fake_session_id = str(uuid.uuid4())

        summary = self.memory.get_session_summary(fake_session_id)

        assert summary is None

    def test_multiple_characters_isolation(self):
        """Test that different characters' data is properly isolated."""
        character1 = "character_1"
        character2 = "character_2"

        session1 = self.memory.create_session(character1)
        session2 = self.memory.create_session(character2)

        self.memory.add_message(character1, session1, "user", "Character 1 message")
        self.memory.add_message(character2, session2, "user", "Character 2 message")

        # Check character 1 sessions
        char1_sessions = self.memory.get_character_sessions(character1)
        assert len(char1_sessions) == 1
        assert char1_sessions[0]["session_id"] == session1

        # Check character 2 sessions
        char2_sessions = self.memory.get_character_sessions(character2)
        assert len(char2_sessions) == 1
        assert char2_sessions[0]["session_id"] == session2

        # Check messages are isolated
        char1_messages = self.memory.get_session_messages(session1)
        assert len(char1_messages) == 1
        assert char1_messages[0]["content"] == "Character 1 message"

        char2_messages = self.memory.get_session_messages(session2)
        assert len(char2_messages) == 1
        assert char2_messages[0]["content"] == "Character 2 message"

    def test_database_persistence(self):
        """Test that data persists across memory instance recreation."""
        session_id = self.memory.create_session(self.character_id)
        self.memory.add_message(self.character_id, session_id, "user", "Persistent message")

        # Create new memory instance with same directory and test database
        new_memory = ConversationMemory(memory_dir=Path(self.temp_dir))

        # Verify data persists
        messages = new_memory.get_session_messages(session_id)
        assert len(messages) == 1
        assert messages[0]["content"] == "Persistent message"

    def test_close_method(self):
        """Test the close method (currently no-op)."""
        # Should not raise an exception
        self.memory.close()

    def test_message_offset_incremental(self):
        """Test that message offsets increment correctly within a session."""
        session_id = self.memory.create_session(self.character_id)

        # Add messages one by one
        self.memory.add_message(self.character_id, session_id, "user", "Message 0")
        self.memory.add_message(self.character_id, session_id, "assistant", "Message 1")
        self.memory.add_message(self.character_id, session_id, "user", "Message 2")

        # Verify messages can be retrieved in correct order
        messages = self.memory.get_session_messages(session_id)
        assert len(messages) == 3
        assert messages[0]["content"] == "Message 0"
        assert messages[1]["content"] == "Message 1"
        assert messages[2]["content"] == "Message 2"

    def test_message_offset_across_sessions(self):
        """Test that offsets are isolated per session."""
        session1 = self.memory.create_session(self.character_id)
        session2 = self.memory.create_session(self.character_id)

        # Add messages to both sessions
        self.memory.add_message(self.character_id, session1, "user", "Session1 Msg0")
        self.memory.add_message(self.character_id, session2, "user", "Session2 Msg0")
        self.memory.add_message(self.character_id, session1, "assistant", "Session1 Msg1")
        self.memory.add_message(self.character_id, session2, "assistant", "Session2 Msg1")

        # Verify messages are isolated per session and in correct order
        session1_messages = self.memory.get_session_messages(session1)
        session2_messages = self.memory.get_session_messages(session2)

        assert len(session1_messages) == 2
        assert session1_messages[0]["content"] == "Session1 Msg0"
        assert session1_messages[1]["content"] == "Session1 Msg1"

        assert len(session2_messages) == 2
        assert session2_messages[0]["content"] == "Session2 Msg0"
        assert session2_messages[1]["content"] == "Session2 Msg1"

    def test_add_messages_offset_batch(self):
        """Test that add_messages correctly handles offset incrementation."""
        session_id = self.memory.create_session(self.character_id)

        # Add an initial message
        self.memory.add_message(self.character_id, session_id, "user", "Initial message")

        # Add multiple messages at once
        batch_messages = [
            {"role": "assistant", "content": "Batch message 1"},
            {"role": "user", "content": "Batch message 2"},
            {"role": "assistant", "content": "Batch message 3"}
        ]
        self.memory.add_messages(self.character_id, session_id, batch_messages)

        # Verify all messages are in correct order
        messages = self.memory.get_session_messages(session_id)
        assert len(messages) == 4
        assert messages[0]["content"] == "Initial message"
        assert messages[1]["content"] == "Batch message 1"
        assert messages[2]["content"] == "Batch message 2"
        assert messages[3]["content"] == "Batch message 3"

    def test_message_ordering_by_offset(self):
        """Test that messages are retrieved in correct order by offset."""
        session_id = self.memory.create_session(self.character_id)

        # Add messages
        self.memory.add_message(self.character_id, session_id, "user", "First")
        self.memory.add_message(self.character_id, session_id, "assistant", "Second")
        self.memory.add_message(self.character_id, session_id, "user", "Third")

        # Get messages and verify order
        messages = self.memory.get_session_messages(session_id)

        assert len(messages) == 3
        assert messages[0]["content"] == "First"
        assert messages[1]["content"] == "Second"
        assert messages[2]["content"] == "Third"

    def test_get_recent_messages_offset_ordering(self):
        """Test that get_recent_messages uses offset for correct ordering."""
        session_id = self.memory.create_session(self.character_id)

        # Add many messages
        for i in range(10):
            self.memory.add_message(self.character_id, session_id, "user", f"Message {i}")

        # Get recent messages
        recent = self.memory.get_recent_messages(session_id, limit=3)

        assert len(recent) == 3
        # Should get the last 3 messages (7, 8, 9) in chronological order
        assert recent[0]["content"] == "Message 7"
        assert recent[1]["content"] == "Message 8"
        assert recent[2]["content"] == "Message 9"

    def test_delete_messages_from_offset(self):
        """Test deleting messages from a specific offset onwards."""
        session_id = self.memory.create_session(self.character_id)

        # Add multiple messages
        messages = [
            {"role": "user", "content": "Message 0", "created_at": "2023-01-01T00:00:00Z", "type": "conversation"},
            {"role": "assistant", "content": "Message 1", "created_at": "2023-01-01T00:00:01Z", "type": "evaluation"},
            {"role": "assistant", "content": "Message 2", "created_at": "2023-01-01T00:00:02Z", "type": "conversation"},
            {"role": "user", "content": "Message 3", "created_at": "2023-01-01T00:01:00Z", "type": "conversation"},
            {"role": "assistant", "content": "Message 4", "created_at": "2023-01-01T00:01:01Z", "type": "evaluation"},
            {"role": "assistant", "content": "Message 5", "created_at": "2023-01-01T00:01:02Z", "type": "conversation"}
        ]
        self.memory.add_messages(self.character_id, session_id, messages)

        # Verify all messages are there
        all_messages = self.memory.get_session_messages(session_id)
        assert len(all_messages) == 6

        # Delete messages from offset 3 onwards (last user message and its responses)
        deleted_count = self.memory.delete_messages_from_offset(session_id, 3)
        assert deleted_count == 3

        # Verify remaining messages
        remaining_messages = self.memory.get_session_messages(session_id)
        assert len(remaining_messages) == 3
        assert remaining_messages[0]["content"] == "Message 0"
        assert remaining_messages[1]["content"] == "Message 1"
        assert remaining_messages[2]["content"] == "Message 2"

    def test_delete_messages_from_offset_edge_cases(self):
        """Test edge cases for delete_messages_from_offset."""
        session_id = self.memory.create_session(self.character_id)

        # Add some messages
        self.memory.add_message(self.character_id, session_id, "user", "Message 0")
        self.memory.add_message(self.character_id, session_id, "assistant", "Message 1")

        # Delete from offset beyond existing messages (should delete nothing)
        deleted_count = self.memory.delete_messages_from_offset(session_id, 10)
        assert deleted_count == 0

        # Verify messages are still there
        messages = self.memory.get_session_messages(session_id)
        assert len(messages) == 2

        # Delete from offset 0 (should delete all messages)
        deleted_count = self.memory.delete_messages_from_offset(session_id, 0)
        assert deleted_count == 2

        # Verify no messages remain
        messages = self.memory.get_session_messages(session_id)
        assert len(messages) == 0

    def test_delete_messages_from_offset_nonexistent_session(self):
        """Test deleting from a nonexistent session."""
        nonexistent_session = "nonexistent-session-id"
        deleted_count = self.memory.delete_messages_from_offset(nonexistent_session, 0)
        assert deleted_count == 0
