import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

from src.conversation_memory import ConversationMemory


class TestConversationMemory:

    def setup_method(self):
        """Set up a temporary memory directory with test database for each test."""
        self.temp_dir = tempfile.mkdtemp()
        # Create custom memory instance that uses conversations_test.db
        self.memory = ConversationMemory(memory_dir=Path(self.temp_dir))
        # Override the db_path to use test database
        self.memory.db_path = self.memory.memory_dir / "conversations_test.db"
        # Initialize the test database
        self.memory._init_database()
        self.character_id = "test_character"

    def teardown_method(self):
        """Clean up test database file."""
        # Close any open connections first
        self.memory.close()
        # Remove the entire test database file
        if self.memory.db_path.exists():
            try:
                self.memory.db_path.unlink()
            except PermissionError:
                # File might still be locked, ignore for now
                pass

    def test_init_default_directory(self):
        """Test initialization with default directory."""
        with patch('pathlib.Path.cwd') as mock_cwd:
            mock_cwd.return_value = Path(self.temp_dir)
            memory = ConversationMemory()

            expected_path = Path(self.temp_dir) / "memory" / "conversations.db"
            assert memory.db_path == expected_path

    def test_init_custom_directory(self):
        """Test initialization with custom directory."""
        custom_dir = Path(self.temp_dir) / "custom_memory"
        memory = ConversationMemory(memory_dir=custom_dir)

        assert memory.memory_dir == custom_dir
        assert memory.db_path == custom_dir / "conversations.db"
        assert custom_dir.exists()

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

        recent = self.memory.get_recent_messages(self.character_id, session_id, limit=5)

        assert len(recent) == 5
        # Should get the last 5 messages in chronological order
        assert recent[0]["content"] == "Message 5"
        assert recent[4]["content"] == "Message 9"

    def test_get_recent_messages_empty_session(self):
        """Test retrieving recent messages from empty session."""
        session_id = self.memory.create_session(self.character_id)

        recent = self.memory.get_recent_messages(self.character_id, session_id)

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
        new_memory.db_path = new_memory.memory_dir / "conversations_test.db"

        # Verify data persists
        messages = new_memory.get_session_messages(session_id)
        assert len(messages) == 1
        assert messages[0]["content"] == "Persistent message"

    def test_close_method(self):
        """Test the close method (currently no-op)."""
        # Should not raise an exception
        self.memory.close()
