"""Registry for storing and retrieving scenarios from database."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, or_

from .database_config import DatabaseConfig
from .db_models import Scenario


class ScenarioRegistry:
    """SQLAlchemy-based persistent scenario storage system."""

    def __init__(self, memory_dir: Path | None = None) -> None:
        """
        Initialize the scenario registry.

        Args:
            memory_dir: Directory to store the database. Defaults to ./memory
        """
        self.db_config = DatabaseConfig(memory_dir)
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the database with the required schema."""
        # Database initialization is handled by DatabaseConfig
        pass

    def save_scenario(
        self,
        scenario_data: dict[str, Any],
        character_id: str,
        scenario_id: str | None = None,
        schema_version: int = 1,
        user_id: str = "anonymous",
    ) -> str:
        """
        Save or update a scenario in the database.

        Args:
            scenario_data: All scenario fields as a dictionary
            character_id: ID of the character this scenario is for
            scenario_id: Optional scenario ID (generated if not provided)
            schema_version: Schema version for the scenario data (default: 1)
            user_id: ID of the user (defaults to 'anonymous')

        Returns:
            The scenario ID (generated or provided)
        """
        if scenario_id is None:
            scenario_id = str(uuid.uuid4())

        with self.db_config.create_session() as session:
            existing_scenario = session.query(Scenario).filter(Scenario.id == scenario_id).first()

            if existing_scenario:
                # Update existing scenario
                existing_scenario.scenario_data = scenario_data
                existing_scenario.character_id = character_id
                existing_scenario.schema_version = schema_version
                existing_scenario.user_id = user_id
                existing_scenario.updated_at = datetime.now()
            else:
                # Create new scenario
                scenario = Scenario(
                    id=scenario_id,
                    character_id=character_id,
                    scenario_data=scenario_data,
                    schema_version=schema_version,
                    user_id=user_id,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                session.add(scenario)

            session.commit()
            return scenario_id

    def get_scenario(self, scenario_id: str, user_id: str = "anonymous") -> dict[str, Any] | None:
        """
        Retrieve a scenario by ID.

        Args:
            scenario_id: Scenario ID to retrieve
            user_id: ID of the user to filter scenario for (also includes anonymous scenarios)

        Returns:
            Scenario data dictionary or None if not found
        """
        with self.db_config.create_session() as session:
            # Query for scenarios that belong to the user OR are anonymous
            scenario = (
                session.query(Scenario)
                .filter(
                    Scenario.id == scenario_id,
                    or_(Scenario.user_id == user_id, Scenario.user_id == "anonymous"),
                )
                .first()
            )

            if scenario:
                return {
                    "id": scenario.id,
                    "character_id": scenario.character_id,
                    "scenario_data": scenario.scenario_data,
                    "schema_version": scenario.schema_version,
                    "created_at": scenario.created_at.isoformat(),
                    "updated_at": scenario.updated_at.isoformat(),
                }

            return None

    def get_scenarios_for_character(
        self,
        character_id: str,
        user_id: str = "anonymous",
        schema_version: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve all scenarios for a specific character.

        Args:
            character_id: ID of the character to get scenarios for
            user_id: ID of the user to filter scenarios for (also includes anonymous scenarios)
            schema_version: Optional schema version filter

        Returns:
            List of scenario data dictionaries
        """
        with self.db_config.create_session() as session:
            # Query for scenarios that belong to the user OR are anonymous
            query = session.query(Scenario).filter(
                Scenario.character_id == character_id,
                or_(Scenario.user_id == user_id, Scenario.user_id == "anonymous"),
            )

            if schema_version is not None:
                query = query.filter(Scenario.schema_version == schema_version)

            scenarios = query.order_by(Scenario.updated_at.desc()).all()

            return [
                {
                    "id": s.id,
                    "character_id": s.character_id,
                    "scenario_data": s.scenario_data,
                    "schema_version": s.schema_version,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                }
                for s in scenarios
            ]

    def get_all_scenarios(
        self,
        user_id: str = "anonymous",
        schema_version: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve all scenarios for a user.

        Args:
            user_id: ID of the user to filter scenarios for (also includes anonymous scenarios)
            schema_version: Optional schema version filter

        Returns:
            List of scenario data dictionaries
        """
        with self.db_config.create_session() as session:
            # Query for scenarios that belong to the user OR are anonymous
            query = session.query(Scenario).filter(
                or_(Scenario.user_id == user_id, Scenario.user_id == "anonymous")
            )

            if schema_version is not None:
                query = query.filter(Scenario.schema_version == schema_version)

            scenarios = query.order_by(Scenario.updated_at.desc()).all()

            return [
                {
                    "id": s.id,
                    "character_id": s.character_id,
                    "scenario_data": s.scenario_data,
                    "schema_version": s.schema_version,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                }
                for s in scenarios
            ]

    def delete_scenario(self, scenario_id: str, user_id: str = "anonymous") -> bool:
        """
        Delete a scenario by ID.

        Args:
            scenario_id: Scenario ID to delete
            user_id: ID of the user (for authorization check)

        Returns:
            True if scenario was deleted, False if not found
        """
        with self.db_config.create_session() as session:
            count = (
                session.query(Scenario)
                .filter(Scenario.id == scenario_id, Scenario.user_id == user_id)
                .delete()
            )
            session.commit()
            return count > 0

    def scenario_exists(self, scenario_id: str, user_id: str = "anonymous") -> bool:
        """
        Check if a scenario exists for a specific user.

        Args:
            scenario_id: Scenario ID to check
            user_id: ID of the user to filter scenario for (also includes anonymous scenarios)

        Returns:
            True if scenario exists, False otherwise
        """
        with self.db_config.create_session() as session:
            return (
                session.query(Scenario)
                .filter(
                    Scenario.id == scenario_id,
                    or_(Scenario.user_id == user_id, Scenario.user_id == "anonymous"),
                )
                .first()
                is not None
            )

    def get_scenario_count(self, user_id: str = "anonymous") -> int:
        """
        Get the total number of scenarios stored for a user.

        Args:
            user_id: ID of the user to count scenarios for

        Returns:
            Total scenario count for the user
        """
        with self.db_config.create_session() as session:
            return (
                session.query(func.count(Scenario.id))
                .filter(or_(Scenario.user_id == user_id, Scenario.user_id == "anonymous"))
                .scalar()
            )

    def get_scenario_count_for_character(self, character_id: str, user_id: str = "anonymous") -> int:
        """
        Get the total number of scenarios for a specific character.

        Args:
            character_id: ID of the character to count scenarios for
            user_id: ID of the user to filter scenarios for

        Returns:
            Scenario count for the character
        """
        with self.db_config.create_session() as session:
            return (
                session.query(func.count(Scenario.id))
                .filter(
                    Scenario.character_id == character_id,
                    or_(Scenario.user_id == user_id, Scenario.user_id == "anonymous"),
                )
                .scalar()
            )

    def health_check(self) -> bool:
        """Check if the database is accessible and healthy."""
        return self.db_config.health_check()

    def close(self) -> None:
        """Close the database connection and dispose of engine resources."""
        self.db_config.dispose()
