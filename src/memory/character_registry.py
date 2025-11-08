from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, or_

from .database_config import DatabaseConfig
from .db_models import Character


class CharacterRegistry:
    """SQLAlchemy-based persistent character storage system."""

    def __init__(self, memory_dir: Path | None = None) -> None:
        """
        Initialize the character memory system.

        Args:
            memory_dir: Directory to store the database. Defaults to ./memory
        """
        self.db_config = DatabaseConfig(memory_dir)
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the database with the required schema."""
        # Database initialization is handled by DatabaseConfig
        pass

    def save_character(self, character_id: str, character_data: dict[str, Any], schema_version: int = 1, user_id: str = "anonymous", is_persona: bool = False) -> bool:
        """
        Save or update a character in the database.

        Args:
            character_id: Character ID (same as filename in characters folder)
            character_data: All character fields as a dictionary
            schema_version: Schema version for the character data (default: 1)
            user_id: ID of the user (defaults to 'anonymous')
            is_persona: Whether this character is a persona (user character) (default: False)

        Returns:
            True if character was saved/updated successfully
        """
        with self.db_config.create_session() as session:
            existing_character = session.query(Character).filter(Character.id == character_id).first()

            if existing_character:
                # Update existing character
                existing_character.character_data = character_data
                existing_character.schema_version = schema_version
                existing_character.user_id = user_id
                existing_character.is_persona = is_persona
                existing_character.updated_at = datetime.now()
            else:
                # Create new character
                character = Character(id=character_id, character_data=character_data, schema_version=schema_version, user_id=user_id, is_persona=is_persona, created_at=datetime.now(), updated_at=datetime.now())
                session.add(character)

            session.commit()
            return True

    def get_character(self, character_id: str, user_id: str) -> dict[str, Any] | None:
        """
        Retrieve a character by ID.

        Args:
            character_id: Character ID to retrieve
            user_id: ID of the user to filter character for (also includes anonymous characters)

        Returns:
            Character data dictionary or None if not found
        """
        with self.db_config.create_session() as session:
            # Query for characters that belong to the user OR are anonymous
            character = session.query(Character).filter(Character.id == character_id, or_(Character.user_id == user_id, Character.user_id == "anonymous")).first()

            if character:
                return {
                    "id": character.id,
                    "character_data": character.character_data,
                    "schema_version": character.schema_version,
                    "created_at": character.created_at.isoformat(),
                    "updated_at": character.updated_at.isoformat(),
                }

            return None

    def get_all_characters(self, user_id: str, schema_version: int | None = None, include_personas: bool = False) -> list[dict[str, Any]]:
        """
        Retrieve all characters for a user, optionally filtered by schema version.

        Args:
            user_id: ID of the user to filter characters for (also includes anonymous characters)
            schema_version: Optional schema version filter
            include_personas: Whether to include persona characters (default: False)

        Returns:
            List of character data dictionaries
        """
        with self.db_config.create_session() as session:
            # Query for characters that belong to the user OR are anonymous
            query = session.query(Character).filter(or_(Character.user_id == user_id, Character.user_id == "anonymous"))

            if schema_version is not None:
                query = query.filter(Character.schema_version == schema_version)

            # Filter out personas by default
            if not include_personas:
                query = query.filter(~Character.is_persona)

            characters = query.order_by(Character.updated_at.desc()).all()

            return [
                {"id": char.id, "character_data": char.character_data, "schema_version": char.schema_version, "created_at": char.created_at.isoformat(), "updated_at": char.updated_at.isoformat()}
                for char in characters
            ]

    def delete_character(self, character_id: str, user_id: str) -> bool:
        """
        Delete a character by ID.

        Args:
            character_id: Character ID to delete
            user_id: ID of the user (for authorization check)

        Returns:
            True if character was deleted, False if not found
        """
        with self.db_config.create_session() as session:
            count = session.query(Character).filter(Character.id == character_id, Character.user_id == user_id).delete()
            session.commit()
            return count > 0

    def character_exists(self, character_id: str, user_id: str) -> bool:
        """
        Check if a character exists for a specific user.

        Args:
            character_id: Character ID to check
            user_id: ID of the user to filter character for

        Returns:
            True if character exists, False otherwise
        """
        with self.db_config.create_session() as session:
            return session.query(Character).filter(Character.id == character_id, Character.user_id == user_id).first() is not None

    def get_personas(self, user_id: str) -> list[dict[str, Any]]:
        """
        Retrieve all persona characters for a user.

        Args:
            user_id: ID of the user to filter personas for (also includes anonymous personas)

        Returns:
            List of persona character data dictionaries
        """
        with self.db_config.create_session() as session:
            # Query for personas that belong to the user OR are anonymous
            query = session.query(Character).filter(or_(Character.user_id == user_id, Character.user_id == "anonymous"), Character.is_persona)

            characters = query.order_by(Character.updated_at.desc()).all()

            return [
                {"id": char.id, "character_data": char.character_data, "schema_version": char.schema_version, "created_at": char.created_at.isoformat(), "updated_at": char.updated_at.isoformat()}
                for char in characters
            ]

    def get_characters_by_schema_version(self, user_id: str, schema_version: int) -> list[dict[str, Any]]:
        """
        Get all characters with a specific schema version for a specific user.

        Args:
            user_id: ID of the user to filter characters for
            schema_version: Schema version to filter by

        Returns:
            List of character data dictionaries
        """
        return self.get_all_characters(user_id=user_id, schema_version=schema_version)

    def update_character_schema(self, character_id: str, user_id: str, new_schema_version: int) -> bool:
        """
        Update only the schema version of a character.

        Args:
            character_id: Character ID to update
            user_id: ID of the user (for authorization check)
            new_schema_version: New schema version

        Returns:
            True if updated successfully, False if character not found
        """
        with self.db_config.create_session() as session:
            count = (
                session.query(Character).filter(Character.id == character_id, Character.user_id == user_id).update({Character.schema_version: new_schema_version, Character.updated_at: datetime.now()})
            )
            session.commit()
            return count > 0

    def get_character_count(self, user_id: str) -> int:
        """
        Get the total number of characters stored for a user.

        Args:
            user_id: ID of the user to count characters for

        Returns:
            Total character count for the user
        """
        with self.db_config.create_session() as session:
            return session.query(func.count(Character.id)).filter(Character.user_id == user_id).scalar()

    def health_check(self) -> bool:
        """Check if the database is accessible and healthy."""
        return self.db_config.health_check()

    def close(self) -> None:
        """Close the database connection and dispose of engine resources."""
        self.db_config.dispose()
