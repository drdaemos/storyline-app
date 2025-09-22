from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func

from .database_config import DatabaseConfig
from .db_models import Summary


class SummaryMemory:
    """SQLAlchemy-based persistent conversation summary memory system."""

    def __init__(self, memory_dir: Path | None = None) -> None:
        """
        Initialize the summary memory system.

        Args:
            memory_dir: Directory to store the database. Defaults to ./memory
        """
        self.db_config = DatabaseConfig(memory_dir)
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the database with the required schema."""
        # Database initialization is handled by DatabaseConfig
        pass

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

        with self.db_config.create_session() as session:
            summary_obj = Summary(
                character_id=character_id,
                session_id=session_id,
                summary=summary,
                start_offset=start_offset,
                end_offset=end_offset,
                created_at=datetime.now()
            )

            session.add(summary_obj)
            session.commit()
            return summary_obj.id

    def get_session_summaries(self, session_id: str) -> list[dict[str, Any]]:
        """
        Retrieve all summaries for a given session, ordered by start_offset.

        Args:
            session_id: Session ID to retrieve summaries for

        Returns:
            List of summary dictionaries with all fields
        """
        with self.db_config.create_session() as session:
            summaries = session.query(Summary).filter(
                Summary.session_id == session_id
            ).order_by(Summary.start_offset).all()

            return [
                {
                    "id": summary.id,
                    "character_id": summary.character_id,
                    "session_id": summary.session_id,
                    "summary": summary.summary,
                    "start_offset": summary.start_offset,
                    "end_offset": summary.end_offset,
                    "created_at": summary.created_at.isoformat()
                }
                for summary in summaries
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
        with self.db_config.create_session() as session:
            summaries = session.query(Summary).filter(
                Summary.character_id == character_id
            ).order_by(Summary.created_at.desc()).limit(limit).all()

            return [
                {
                    "id": summary.id,
                    "character_id": summary.character_id,
                    "session_id": summary.session_id,
                    "summary": summary.summary,
                    "start_offset": summary.start_offset,
                    "end_offset": summary.end_offset,
                    "created_at": summary.created_at.isoformat()
                }
                for summary in summaries
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
        with self.db_config.create_session() as session:
            summaries = session.query(Summary).filter(
                Summary.session_id == session_id,
                Summary.start_offset <= offset,
                Summary.end_offset >= offset
            ).order_by(Summary.start_offset).all()

            return [
                {
                    "id": summary.id,
                    "character_id": summary.character_id,
                    "session_id": summary.session_id,
                    "summary": summary.summary,
                    "start_offset": summary.start_offset,
                    "end_offset": summary.end_offset,
                    "created_at": summary.created_at.isoformat()
                }
                for summary in summaries
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
        with self.db_config.create_session() as session:
            # Overlap condition: NOT (end_offset < start_offset OR start_offset > end_offset)
            summaries = session.query(Summary).filter(
                Summary.session_id == session_id,
                ~((Summary.end_offset < start_offset) | (Summary.start_offset > end_offset))
            ).order_by(Summary.start_offset).all()

            return [
                {
                    "id": summary.id,
                    "character_id": summary.character_id,
                    "session_id": summary.session_id,
                    "summary": summary.summary,
                    "start_offset": summary.start_offset,
                    "end_offset": summary.end_offset,
                    "created_at": summary.created_at.isoformat()
                }
                for summary in summaries
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
        with self.db_config.create_session() as session:
            count = session.query(Summary).filter(
                Summary.id == summary_id
            ).update({Summary.summary: new_summary_text})
            session.commit()
            return count > 0

    def delete_summary(self, summary_id: int) -> bool:
        """
        Delete a summary by ID.

        Args:
            summary_id: ID of the summary to delete

        Returns:
            True if summary was deleted, False if not found
        """
        with self.db_config.create_session() as session:
            count = session.query(Summary).filter(Summary.id == summary_id).delete()
            session.commit()
            return count > 0

    def delete_session_summaries(self, session_id: str) -> int:
        """
        Delete all summaries for a session.

        Args:
            session_id: Session ID to delete summaries for

        Returns:
            Number of summaries deleted
        """
        with self.db_config.create_session() as session:
            count = session.query(Summary).filter(Summary.session_id == session_id).delete()
            session.commit()
            return count

    def clear_character_summaries(self, character_id: str) -> int:
        """
        Delete all summaries for a character.

        Args:
            character_id: Character ID to clear summaries for

        Returns:
            Number of summaries deleted
        """
        with self.db_config.create_session() as session:
            count = session.query(Summary).filter(Summary.character_id == character_id).delete()
            session.commit()
            return count

    def get_max_processed_offset(self, session_id: str) -> int | None:
        """
        Get the highest end_offset that has been summarized for a session.
        This can be used to determine which messages still need summarization.

        Args:
            session_id: Session ID

        Returns:
            Highest end_offset that has been summarized, or None if no summaries exist
        """
        with self.db_config.create_session() as session:
            result = session.query(func.max(Summary.end_offset)).filter(
                Summary.session_id == session_id
            ).scalar()
            return result

    def health_check(self) -> bool:
        """Check if the database is accessible and healthy."""
        return self.db_config.health_check()

    def close(self) -> None:
        """Close the database connection (currently no-op as we use context managers)."""
        pass
