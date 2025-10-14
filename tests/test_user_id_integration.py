"""Tests for user_id integration across database tables."""

import tempfile
from pathlib import Path

import pytest

from src.character_manager import CharacterManager
from src.memory.character_registry import CharacterRegistry
from src.memory.conversation_memory import ConversationMemory
from src.memory.summary_memory import SummaryMemory


@pytest.fixture
def temp_memory_dir():
    """Create a temporary directory for database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def conversation_memory(temp_memory_dir):
    """Create ConversationMemory instance with temp directory."""
    return ConversationMemory(temp_memory_dir)


@pytest.fixture
def summary_memory(temp_memory_dir):
    """Create SummaryMemory instance with temp directory."""
    return SummaryMemory(temp_memory_dir)


@pytest.fixture
def character_registry(temp_memory_dir):
    """Create CharacterRegistry instance with temp directory."""
    return CharacterRegistry(temp_memory_dir)


def test_conversation_memory_stores_user_id(conversation_memory):
    """Test that ConversationMemory stores user_id correctly."""
    session_id = conversation_memory.create_session("test_character")

    # Add message with custom user_id
    message_id = conversation_memory.add_message(character_id="test_character", session_id=session_id, role="user", content="Hello", user_id="user_123")

    assert message_id > 0

    # Verify message is stored (this tests indirectly through get methods)
    messages = conversation_memory.get_session_messages(session_id, "user_123")
    assert len(messages) == 1


def test_conversation_memory_default_user_id(conversation_memory):
    """Test that ConversationMemory uses default user_id when not specified."""
    session_id = conversation_memory.create_session("test_character")

    # Add message without user_id (should default to 'anonymous')
    message_id = conversation_memory.add_message(character_id="test_character", session_id=session_id, role="user", content="Hello")

    assert message_id > 0
    messages = conversation_memory.get_session_messages(session_id, "anonymous")
    assert len(messages) == 1


def test_conversation_memory_add_messages_with_user_id(conversation_memory):
    """Test that add_messages stores user_id correctly."""
    session_id = conversation_memory.create_session("test_character")

    messages = [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi there!"}]

    last_id = conversation_memory.add_messages(character_id="test_character", session_id=session_id, messages=messages, user_id="user_456")

    assert last_id > 0
    stored_messages = conversation_memory.get_session_messages(session_id, "user_456")
    assert len(stored_messages) == 2


def test_summary_memory_stores_user_id(summary_memory):
    """Test that SummaryMemory stores user_id correctly."""
    session_id = "test_session_123"

    summary_id = summary_memory.add_summary(character_id="test_character", session_id=session_id, summary="Test summary", start_offset=0, end_offset=5, user_id="user_789")

    assert summary_id > 0
    summaries = summary_memory.get_session_summaries(session_id, "user_789")
    assert len(summaries) == 1


def test_summary_memory_default_user_id(summary_memory):
    """Test that SummaryMemory uses default user_id when not specified."""
    session_id = "test_session_456"

    summary_id = summary_memory.add_summary(character_id="test_character", session_id=session_id, summary="Test summary", start_offset=0, end_offset=5)

    assert summary_id > 0
    summaries = summary_memory.get_session_summaries(session_id, "anonymous")
    assert len(summaries) == 1


def test_character_registry_stores_user_id(character_registry):
    """Test that CharacterRegistry stores user_id correctly."""
    character_data = {"name": "Test Character", "tagline": "Test Role", "backstory": "Test backstory"}

    success = character_registry.save_character(character_id="test_char_1", character_data=character_data, user_id="user_999")

    assert success is True
    character = character_registry.get_character("test_char_1", "user_999")
    assert character is not None
    assert character["id"] == "test_char_1"


def test_character_registry_default_user_id(character_registry):
    """Test that CharacterRegistry uses default user_id when not specified."""
    character_data = {"name": "Test Character 2", "tagline": "Test Role", "backstory": "Test backstory"}

    success = character_registry.save_character(character_id="test_char_2", character_data=character_data)

    assert success is True
    character = character_registry.get_character("test_char_2", "anonymous")
    assert character is not None


def test_character_manager_stores_user_id(temp_memory_dir):
    """Test that CharacterManager passes user_id to registry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        characters_dir = Path(tmpdir) / "characters"
        characters_dir.mkdir()

        manager = CharacterManager(characters_dir=str(characters_dir), memory_dir=temp_memory_dir)

        character_data = {"name": "Manager Test Character", "tagline": "Test Role", "backstory": "Test backstory"}

        filename = manager.create_character_file(character_data=character_data, user_id="user_manager_123")

        assert filename is not None
        # Verify it was saved to registry
        character = manager.registry.get_character(filename, "user_manager_123")
        assert character is not None


def test_multiple_users_separate_data(conversation_memory):
    """Test that different users can have separate data in the same table."""
    session_id_1 = conversation_memory.create_session("character_1")
    session_id_2 = conversation_memory.create_session("character_1")

    # User 1 adds a message
    conversation_memory.add_message(character_id="character_1", session_id=session_id_1, role="user", content="User 1 message", user_id="user_1")

    # User 2 adds a message
    conversation_memory.add_message(character_id="character_1", session_id=session_id_2, role="user", content="User 2 message", user_id="user_2")

    # Both should be stored successfully
    messages_1 = conversation_memory.get_session_messages(session_id_1, "user_1")
    messages_2 = conversation_memory.get_session_messages(session_id_2, "user_2")

    assert len(messages_1) == 1
    assert len(messages_2) == 1
    assert messages_1[0]["content"] == "User 1 message"
    assert messages_2[0]["content"] == "User 2 message"
