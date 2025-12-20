import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func

from src.models.message import GenericMessage

from .database_config import DatabaseConfig
from .db_models import Message


class ConversationMemory:
    """SQLAlchemy-based persistent conversation memory system."""

    def __init__(self, memory_dir: Path | None = None) -> None:
        """
        Initialize the conversation memory system.

        Args:
            memory_dir: Directory to store the SQLite database. Defaults to ./memory
        """
        self.db_config = DatabaseConfig(memory_dir)
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the database with the required schema."""
        # Database initialization is handled by DatabaseConfig
        pass

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

    def add_message(
        self,
        character_id: str,
        session_id: str,
        role: str,
        content: str,
        message_type: str = "conversation",
        user_id: str = "anonymous",
        scenario_id: str | None = None,
    ) -> int:
        """
        Add a message to the conversation memory.

        Args:
            character_id: ID of the character
            session_id: Session ID for this conversation
            role: Role of the message sender (user/assistant)
            content: Content of the message
            message_type: Type of message ('conversation' or 'evaluation')
            user_id: ID of the user (defaults to 'anonymous')
            scenario_id: Optional scenario ID to link this message to

        Returns:
            The ID of the inserted message
        """
        with self.db_config.create_session() as session:
            # Get the next offset for this session
            max_offset = session.query(func.coalesce(func.max(Message.offset), -1)).filter(Message.session_id == session_id).scalar()
            next_offset = max_offset + 1

            message = Message(
                character_id=character_id,
                session_id=session_id,
                role=role,
                content=content,
                offset=next_offset,
                type=message_type,
                user_id=user_id,
                scenario_id=scenario_id,
                created_at=datetime.now(),
            )

            session.add(message)
            session.commit()
            return message.id

    def add_messages(self, character_id: str, session_id: str, messages: list[GenericMessage], user_id: str = "anonymous") -> int:
        """
        Add multiple messages to the conversation memory.

        Args:
            character_id: ID of the character
            session_id: Session ID for this conversation
            messages: List of messages to add
            user_id: ID of the user (defaults to 'anonymous')

        Returns:
            The ID of the last inserted message
        """
        with self.db_config.create_session() as session:
            # Get the current max offset for this session
            max_offset = session.query(func.coalesce(func.max(Message.offset), -1)).filter(Message.session_id == session_id).scalar()

            # Create message objects with incremental offsets
            message_objects = []
            for i, msg in enumerate(messages):
                message_type = msg.get("type", "conversation")
                message_obj = Message(
                    character_id=character_id, session_id=session_id, role=msg["role"], content=msg["content"], offset=max_offset + 1 + i, type=message_type, user_id=user_id, created_at=datetime.now()
                )
                message_objects.append(message_obj)

            session.add_all(message_objects)
            session.commit()
            return message_objects[-1].id if message_objects else 0

    def get_session_messages(self, session_id: str, user_id: str, limit: int | None = None) -> list[GenericMessage]:
        """
        Retrieve all messages for a given session.

        Args:
            session_id: Session ID to retrieve messages for
            user_id: ID of the user to filter messages for
            limit: Maximum number of messages to retrieve (newest first)

        Returns:
            List of messages in chronological order
        """
        with self.db_config.create_session() as session:
            query = session.query(Message).filter(Message.session_id == session_id, Message.user_id == user_id).order_by(Message.offset)

            if limit:
                query = query.limit(limit)

            messages = query.all()

            return [{"role": msg.role, "content": msg.content, "type": msg.type, "created_at": msg.created_at.isoformat()} for msg in messages]

    def get_character_sessions(self, character_id: str, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get recent sessions for a character.

        Args:
            character_id: ID of the character
            user_id: ID of the user to filter sessions for
            limit: Maximum number of sessions to return

        Returns:
            List of session info with session_id, last_message_time, message_count
        """
        with self.db_config.create_session() as session:
            results = (
                session.query(Message.session_id, func.max(Message.created_at).label("last_message_time"), func.count().label("message_count"))
                .filter(Message.character_id == character_id, Message.user_id == user_id)
                .group_by(Message.session_id)
                .order_by(func.max(Message.created_at).desc())
                .limit(limit)
                .all()
            )

            return [{"session_id": result.session_id, "last_message_time": result.last_message_time.isoformat(), "message_count": result.message_count} for result in results]

    def get_session_details(self, session_id: str, user_id: str) -> dict[str, Any] | None:
        """
        Get detailed information about a session.

        Args:
            session_id: Session ID
            user_id: ID of the user to filter session for

        Returns:
            Dictionary with session stats or None if session doesn't exist
        """
        with self.db_config.create_session() as session:
            result = (
                session.query(
                    Message.character_id, func.count().label("message_count"), func.min(Message.created_at).label("first_message_time"), func.max(Message.created_at).label("last_message_time")
                )
                .filter(Message.session_id == session_id, Message.user_id == user_id)
                .group_by(Message.character_id, Message.session_id)
                .first()
            )

            if result:
                return {
                    "session_id": session_id,
                    "character_id": result.character_id,
                    "message_count": result.message_count,
                    "first_message_time": result.first_message_time.isoformat(),
                    "last_message_time": result.last_message_time.isoformat(),
                }

            return None

    def get_recent_messages(self, session_id: str, user_id: str, limit: int = 10, from_offset: int = 0) -> list[GenericMessage]:
        """
        Get the most recent messages from a session, optionally starting from a specific offset.

        Args:
            session_id: Session ID
            user_id: ID of the user to filter messages for
            limit: Number of recent messages to retrieve
            from_offset: Only retrieve messages with offset >= from_offset (default 0 gets all messages)

        Returns:
            List of recent messages in chronological order
        """
        with self.db_config.create_session() as session:
            # Build the query for recent messages from the specified offset onwards
            query = session.query(Message).filter(
                Message.session_id == session_id,
                Message.user_id == user_id,
                Message.offset >= from_offset
            )

            # Order by offset DESC to get most recent, limit, then reverse to chronological order
            subquery = query.order_by(Message.offset.desc()).limit(limit).subquery()

            # Query the subquery ordered by offset ascending (chronological order)
            messages = session.query(subquery).order_by(subquery.c.offset).all()

            return [{"role": msg.role, "content": msg.content, "type": msg.type, "created_at": msg.created_at.isoformat()} for msg in messages]

    def delete_messages_from_offset(self, session_id: str, user_id: str, from_offset: int) -> int:
        """
        Delete messages from a specific offset onwards in a session.

        Args:
            session_id: Session ID to delete messages from
            user_id: ID of the user (for authorization check)
            from_offset: Delete messages with offset >= this value

        Returns:
            Number of messages deleted
        """
        with self.db_config.create_session() as session:
            count = session.query(Message).filter(Message.session_id == session_id, Message.user_id == user_id, Message.offset >= from_offset).delete()
            session.commit()
            return count

    def delete_session(self, session_id: str, user_id: str) -> int:
        """
        Delete all messages from a session.

        Args:
            session_id: Session ID to delete
            user_id: ID of the user (for authorization check)

        Returns:
            Number of messages deleted
        """
        with self.db_config.create_session() as session:
            count = session.query(Message).filter(Message.session_id == session_id, Message.user_id == user_id).delete()
            session.commit()
            return count

    def clear_character_memory(self, character_id: str, user_id: str) -> int:
        """
        Delete all messages for a character.

        Args:
            character_id: Character ID to clear memory for
            user_id: ID of the user (for authorization check)

        Returns:
            Number of messages deleted
        """
        with self.db_config.create_session() as session:
            count = session.query(Message).filter(Message.character_id == character_id, Message.user_id == user_id).delete()
            session.commit()
            return count

    def get_session_summary(self, session_id: str, user_id: str) -> dict[str, Any] | None:
        """
        Get summary information about a session.

        Args:
            session_id: Session ID
            user_id: ID of the user to filter session for

        Returns:
            Dictionary with session stats or None if session doesn't exist
        """
        with self.db_config.create_session() as session:
            result = (
                session.query(
                    Message.character_id, func.count().label("message_count"), func.min(Message.created_at).label("first_message_time"), func.max(Message.created_at).label("last_message_time")
                )
                .filter(Message.session_id == session_id, Message.user_id == user_id)
                .group_by(Message.character_id, Message.session_id)
                .first()
            )

            if result:
                return {
                    "session_id": session_id,
                    "character_id": result.character_id,
                    "message_count": result.message_count,
                    "first_message_time": result.first_message_time.isoformat(),
                    "last_message_time": result.last_message_time.isoformat(),
                }

            return None

    def health_check(self) -> bool:
        """Check if the database is accessible and healthy."""
        return self.db_config.health_check()

    def close(self) -> None:
        """Close the database connection and dispose of engine resources."""
        self.db_config.dispose()
