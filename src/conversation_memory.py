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
                    offset INTEGER NOT NULL DEFAULT 0,
                    type TEXT NOT NULL DEFAULT 'conversation' CHECK(type IN ('conversation', 'evaluation')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Add offset column if it doesn't exist (migration)
            cursor = conn.execute("PRAGMA table_info(messages)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'offset' not in columns:
                conn.execute("ALTER TABLE messages ADD COLUMN offset INTEGER NOT NULL DEFAULT 0")
                # Initialize offset values for existing records per session
                conn.execute("""
                    UPDATE messages
                    SET offset = (
                        SELECT COUNT(*) - 1
                        FROM messages m2
                        WHERE m2.session_id = messages.session_id
                        AND m2.id <= messages.id
                    )
                """)

            # Add type column if it doesn't exist (migration)
            cursor = conn.execute("PRAGMA table_info(messages)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'type' not in columns:
                conn.execute("ALTER TABLE messages ADD COLUMN type TEXT NOT NULL DEFAULT 'conversation'")
                # Update existing data based on the pattern:
                # Each cycle of 3 messages -> user, assistant, assistant
                # user message: 'conversation'
                # first assistant message: 'evaluation'
                # second assistant message: 'conversation'
                conn.execute("""
                    UPDATE messages
                    SET type = CASE
                        WHEN role = 'user' THEN 'conversation'
                        WHEN role = 'assistant' AND (offset % 3) = 1 THEN 'evaluation'
                        WHEN role = 'assistant' AND (offset % 3) = 2 THEN 'conversation'
                        ELSE 'conversation'
                    END
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

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_offset
                ON messages (session_id, offset)
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

    def add_message(self, character_id: str, session_id: str, role: str, content: str, message_type: str = 'conversation') -> int:
        """
        Add a message to the conversation memory.

        Args:
            character_id: ID of the character
            session_id: Session ID for this conversation
            role: Role of the message sender (user/assistant)
            content: Content of the message
            message_type: Type of message ('conversation' or 'evaluation')

        Returns:
            The ID of the inserted message
        """
        with sqlite3.connect(self.db_path) as conn:
            # Get the next offset for this session
            cursor = conn.execute("""
                SELECT COALESCE(MAX(offset), -1) + 1 as next_offset
                FROM messages
                WHERE session_id = ?
            """, (session_id,))
            next_offset = cursor.fetchone()[0]

            cursor = conn.execute("""
                INSERT INTO messages (character_id, session_id, role, content, offset, type, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (character_id, session_id, role, content, next_offset, message_type, datetime.now().isoformat()))

            conn.commit()
            return cursor.lastrowid or 0

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
            # Get the current max offset for this session
            cursor = conn.execute("""
                SELECT COALESCE(MAX(offset), -1) as max_offset
                FROM messages
                WHERE session_id = ?
            """, (session_id,))
            max_offset = cursor.fetchone()[0]

            # Prepare data with incremental offsets
            data: list[tuple[str, str, str, str, int, str, str]] = []
            for i, msg in enumerate(messages):
                message_type = msg.get("type", "conversation")
                data.append((
                    character_id,
                    session_id,
                    msg["role"],
                    msg["content"],
                    max_offset + 1 + i,
                    message_type,
                    datetime.now().isoformat()
                ))

            cursor = conn.cursor()
            cursor.executemany("""
                INSERT INTO messages (character_id, session_id, role, content, offset, type, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, data)
            conn.commit()
            return cursor.lastrowid or 0

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
                SELECT role, content, type, offset, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY offset ASC
            """
            params = (session_id,)

            if limit:
                query += " LIMIT ?"
                params = (session_id, limit)

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            return [
                {"role": row["role"], "content": row["content"], "type": row["type"], "created_at": row["created_at"]}
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

    def get_session_details(self, session_id: str) -> dict[str, Any] | None:
        """
        Get detailed information about a session.

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

    def get_recent_messages(self, session_id: str, limit: int = 10, type: str | None = None) -> list[GenericMessage]:
        """
        Get the most recent messages from a session.

        Args:
            session_id: Session ID
            limit: Number of recent messages to retrieve

        Returns:
            List of recent messages in chronological order
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            type_filter = "type IS NOT NULL" if type is None else "type = ?"
            params = (session_id, limit) if type is None else (session_id, type, limit)

            cursor = conn.execute(f"""
                SELECT role, content, type, created_at
                FROM (
                    SELECT role, content, type, created_at, offset
                    FROM messages
                    WHERE session_id = ?
                    AND {type_filter}
                    ORDER BY offset DESC
                    LIMIT ?
                )
                ORDER BY offset ASC
            """, params)

            rows = cursor.fetchall()

            return [
                {"role": row["role"], "content": row["content"], "type": row["type"], "created_at": row["created_at"]}
                for row in rows
            ]

    def delete_messages_from_offset(self, session_id: str, from_offset: int) -> int:
        """
        Delete messages from a specific offset onwards in a session.

        Args:
            session_id: Session ID to delete messages from
            from_offset: Delete messages with offset >= this value

        Returns:
            Number of messages deleted
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM messages
                WHERE session_id = ? AND offset >= ?
            """, (session_id, from_offset))

            conn.commit()
            return cursor.rowcount

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

    def health_check(self) -> bool:
        """Check if the database is accessible and healthy."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT 1")
                cursor.fetchone()
            return True
        except Exception:
            return False

    def close(self) -> None:
        """Close the database connection (currently no-op as we use context managers)."""
        pass
