import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class SummaryMemory:
    """SQLite3-based persistent conversation summary memory system."""

    def __init__(self, memory_dir: Path | None = None) -> None:
        """
        Initialize the summary memory system.

        Args:
            memory_dir: Directory to store the SQLite database. Defaults to ./memory
        """
        if memory_dir is None:
            memory_dir = Path.cwd() / "memory"

        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.memory_dir / "summaries.db"
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the SQLite database with the required schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    start_offset INTEGER NOT NULL,
                    end_offset INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for better query performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_character_session_summaries
                ON summaries (character_id, session_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_offsets
                ON summaries (session_id, start_offset, end_offset)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_created_at
                ON summaries (session_id, created_at)
            """)

            conn.commit()

    def add_summary(
        self,
        character_id: str,
        session_id: str,
        summary: str,
        start_offset: int,
        end_offset: int
    ) -> int:
        """
        Add a summary to the memory.

        Args:
            character_id: ID of the character
            session_id: Session ID for this conversation
            summary: Text summary of the messages
            start_offset: Starting message offset (inclusive)
            end_offset: Ending message offset (inclusive)

        Returns:
            The ID of the inserted summary

        Raises:
            ValueError: If start_offset > end_offset or offsets are negative
        """
        if start_offset < 0 or end_offset < 0:
            raise ValueError("Offsets must be non-negative")
        if start_offset > end_offset:
            raise ValueError("start_offset must be <= end_offset")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO summaries (character_id, session_id, summary, start_offset, end_offset, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (character_id, session_id, summary, start_offset, end_offset, datetime.now().isoformat()))

            conn.commit()
            return cursor.lastrowid or 0

    def get_session_summaries(self, session_id: str) -> list[dict[str, Any]]:
        """
        Retrieve all summaries for a given session, ordered by start_offset.

        Args:
            session_id: Session ID to retrieve summaries for

        Returns:
            List of summary dictionaries with all fields
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute("""
                SELECT id, character_id, session_id, summary, start_offset, end_offset, created_at
                FROM summaries
                WHERE session_id = ?
                ORDER BY start_offset ASC
            """, (session_id,))

            rows = cursor.fetchall()

            return [
                {
                    "id": row["id"],
                    "character_id": row["character_id"],
                    "session_id": row["session_id"],
                    "summary": row["summary"],
                    "start_offset": row["start_offset"],
                    "end_offset": row["end_offset"],
                    "created_at": row["created_at"]
                }
                for row in rows
            ]

    def get_character_summaries(self, character_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        Get recent summaries for a character across all sessions.

        Args:
            character_id: ID of the character
            limit: Maximum number of summaries to return

        Returns:
            List of summary info ordered by creation time (most recent first)
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute("""
                SELECT id, character_id, session_id, summary, start_offset, end_offset, created_at
                FROM summaries
                WHERE character_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (character_id, limit))

            rows = cursor.fetchall()

            return [
                {
                    "id": row["id"],
                    "character_id": row["character_id"],
                    "session_id": row["session_id"],
                    "summary": row["summary"],
                    "start_offset": row["start_offset"],
                    "end_offset": row["end_offset"],
                    "created_at": row["created_at"]
                }
                for row in rows
            ]

    def get_summaries_covering_offset(self, session_id: str, offset: int) -> list[dict[str, Any]]:
        """
        Get summaries that cover a specific message offset.

        Args:
            session_id: Session ID
            offset: Message offset to check coverage for

        Returns:
            List of summaries that include the given offset
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute("""
                SELECT id, character_id, session_id, summary, start_offset, end_offset, created_at
                FROM summaries
                WHERE session_id = ? AND start_offset <= ? AND end_offset >= ?
                ORDER BY start_offset ASC
            """, (session_id, offset, offset))

            rows = cursor.fetchall()

            return [
                {
                    "id": row["id"],
                    "character_id": row["character_id"],
                    "session_id": row["session_id"],
                    "summary": row["summary"],
                    "start_offset": row["start_offset"],
                    "end_offset": row["end_offset"],
                    "created_at": row["created_at"]
                }
                for row in rows
            ]

    def get_summaries_in_range(self, session_id: str, start_offset: int, end_offset: int) -> list[dict[str, Any]]:
        """
        Get summaries that overlap with a given offset range.

        Args:
            session_id: Session ID
            start_offset: Start of range (inclusive)
            end_offset: End of range (inclusive)

        Returns:
            List of summaries that overlap with the given range
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute("""
                SELECT id, character_id, session_id, summary, start_offset, end_offset, created_at
                FROM summaries
                WHERE session_id = ?
                AND NOT (end_offset < ? OR start_offset > ?)
                ORDER BY start_offset ASC
            """, (session_id, start_offset, end_offset))

            rows = cursor.fetchall()

            return [
                {
                    "id": row["id"],
                    "character_id": row["character_id"],
                    "session_id": row["session_id"],
                    "summary": row["summary"],
                    "start_offset": row["start_offset"],
                    "end_offset": row["end_offset"],
                    "created_at": row["created_at"]
                }
                for row in rows
            ]

    def update_summary(self, summary_id: int, new_summary_text: str) -> bool:
        """
        Update the summary text of an existing summary.

        Args:
            summary_id: ID of the summary to update
            new_summary_text: New summary text

        Returns:
            True if summary was updated, False if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                UPDATE summaries
                SET summary = ?
                WHERE id = ?
            """, (new_summary_text, summary_id))

            conn.commit()
            return cursor.rowcount > 0

    def delete_summary(self, summary_id: int) -> bool:
        """
        Delete a summary by ID.

        Args:
            summary_id: ID of the summary to delete

        Returns:
            True if summary was deleted, False if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM summaries WHERE id = ?
            """, (summary_id,))

            conn.commit()
            return cursor.rowcount > 0

    def delete_session_summaries(self, session_id: str) -> int:
        """
        Delete all summaries for a session.

        Args:
            session_id: Session ID to delete summaries for

        Returns:
            Number of summaries deleted
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM summaries WHERE session_id = ?
            """, (session_id,))

            conn.commit()
            return cursor.rowcount

    def clear_character_summaries(self, character_id: str) -> int:
        """
        Delete all summaries for a character.

        Args:
            character_id: Character ID to clear summaries for

        Returns:
            Number of summaries deleted
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM summaries WHERE character_id = ?
            """, (character_id,))

            conn.commit()
            return cursor.rowcount

    def get_max_processed_offset(self, session_id: str) -> int | None:
        """
        Get the highest end_offset that has been summarized for a session.
        This can be used to determine which messages still need summarization.

        Args:
            session_id: Session ID

        Returns:
            Highest end_offset that has been summarized, or None if no summaries exist
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT MAX(end_offset) as max_offset
                FROM summaries
                WHERE session_id = ?
            """, (session_id,))

            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else None

    def close(self) -> None:
        """Close the database connection (currently no-op as we use context managers)."""
        pass
