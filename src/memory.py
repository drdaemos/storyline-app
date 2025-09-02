import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from src.models.message import GenericMessage


class ConversationMemory:
    """SQLite3-based persistent conversation memory system."""

    def __init__(self, memory_dir: Path | None = None) -> None:
        """
        Initialize the conversation memory system.

        Args:
            memory_dir: Directory to store the SQLite database. Defaults to ./memory
        """
        if memory_dir is None:
            memory_dir = Path.cwd() / "memory"

        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.memory_dir / "conversations.db"
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the SQLite database with the required schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for better query performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_character_session
                ON messages (character_id, session_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_created_at
                ON messages (session_id, created_at)
            """)

            conn.commit()

    def create_session(self, character_id: str) -> str:
        """
        Create a new conversation session.

        Args:
            character_id: ID of the character for this session

        Returns:
            Generated session ID
        """
        session_id = str(uuid.uuid4())
        # Session is created implicitly when first message is added
        return session_id

    def add_message(self, character_id: str, session_id: str, role: str, content: str) -> int:
        """
        Add a message to the conversation memory.

        Args:
            character_id: ID of the character
            session_id: Session ID for this conversation
            role: Role of the message sender (user/assistant)
            content: Content of the message

        Returns:
            The ID of the inserted message
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO messages (character_id, session_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (character_id, session_id, role, content, datetime.now().isoformat()))

            conn.commit()
            return cursor.lastrowid
        
    def add_messages(self, character_id: str, session_id: str, messages: list[GenericMessage]) -> int:
        """
        Add multiple messages to the conversation memory.

        Args:
            character_id: ID of the character
            session_id: Session ID for this conversation
            messages: List of messages to add

        Returns:
            The ID of the last inserted message
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT INTO messages (character_id, session_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, [
                (character_id, session_id, msg["role"], msg["content"], datetime.now().isoformat())
                for msg in messages
            ])
            conn.commit()
            return cursor.lastrowid

    def get_session_messages(self, session_id: str, limit: int | None = None) -> list[GenericMessage]:
        """
        Retrieve all messages for a given session.

        Args:
            session_id: Session ID to retrieve messages for
            limit: Maximum number of messages to retrieve (newest first)

        Returns:
            List of messages in chronological order
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            query = """
                SELECT role, content, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY created_at ASC
            """
            params = (session_id,)

            if limit:
                query += " LIMIT ?"
                params = (session_id, limit)

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            return [
                {"role": row["role"], "content": row["content"]}
                for row in rows
            ]

    def get_character_sessions(self, character_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get recent sessions for a character.

        Args:
            character_id: ID of the character
            limit: Maximum number of sessions to return

        Returns:
            List of session info with session_id, last_message_time, message_count
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute("""
                SELECT
                    session_id,
                    MAX(created_at) as last_message_time,
                    COUNT(*) as message_count
                FROM messages
                WHERE character_id = ?
                GROUP BY session_id
                ORDER BY last_message_time DESC
                LIMIT ?
            """, (character_id, limit))

            rows = cursor.fetchall()

            return [
                {
                    "session_id": row["session_id"],
                    "last_message_time": row["last_message_time"],
                    "message_count": row["message_count"]
                }
                for row in rows
            ]

    def get_recent_messages(self, character_id: str, session_id: str, limit: int = 10) -> list[GenericMessage]:
        """
        Get the most recent messages from a session.

        Args:
            character_id: ID of the character
            session_id: Session ID
            limit: Number of recent messages to retrieve

        Returns:
            List of recent messages in chronological order
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute("""
                SELECT role, content
                FROM (
                    SELECT role, content, created_at
                    FROM messages
                    WHERE character_id = ? AND session_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                )
                ORDER BY created_at ASC
            """, (character_id, session_id, limit))

            rows = cursor.fetchall()

            return [
                {"role": row["role"], "content": row["content"]}
                for row in rows
            ]

    def delete_session(self, session_id: str) -> int:
        """
        Delete all messages from a session.

        Args:
            session_id: Session ID to delete

        Returns:
            Number of messages deleted
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM messages WHERE session_id = ?
            """, (session_id,))

            conn.commit()
            return cursor.rowcount

    def clear_character_memory(self, character_id: str) -> int:
        """
        Delete all messages for a character.

        Args:
            character_id: Character ID to clear memory for

        Returns:
            Number of messages deleted
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM messages WHERE character_id = ?
            """, (character_id,))

            conn.commit()
            return cursor.rowcount

    def get_session_summary(self, session_id: str) -> dict[str, Any] | None:
        """
        Get summary information about a session.

        Args:
            session_id: Session ID

        Returns:
            Dictionary with session stats or None if session doesn't exist
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute("""
                SELECT
                    character_id,
                    COUNT(*) as message_count,
                    MIN(created_at) as first_message_time,
                    MAX(created_at) as last_message_time
                FROM messages
                WHERE session_id = ?
                GROUP BY character_id, session_id
            """, (session_id,))

            row = cursor.fetchone()

            if row:
                return {
                    "session_id": session_id,
                    "character_id": row["character_id"],
                    "message_count": row["message_count"],
                    "first_message_time": row["first_message_time"],
                    "last_message_time": row["last_message_time"]
                }

            return None

    def close(self) -> None:
        """Close the database connection (currently no-op as we use context managers)."""
        pass
