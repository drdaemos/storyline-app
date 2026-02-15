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
        self.db_config = DatabaseConfig(memory_dir)
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the database with the required schema."""
        pass

    def save_scenario(
        self,
        scenario_data: dict[str, Any],
        scenario_id: str | None = None,
        schema_version: int = 2,
        user_id: str = "anonymous",
        ruleset_id: str | None = None,
        character_ids: list[str] | None = None,
    ) -> str:
        """
        Save or update a scenario in the database.

        Args:
            scenario_data: All scenario fields as a dictionary
            scenario_id: Optional scenario ID (generated if not provided)
            schema_version: Schema version for the scenario data (default: 2)
            user_id: ID of the user (defaults to 'anonymous')
            ruleset_id: Ruleset ID referenced by this scenario (required)
            character_ids: Optional list of NPC character IDs

        Returns:
            The scenario ID (generated or provided)

        Raises:
            ValueError: If ruleset_id is not provided
        """
        if not ruleset_id:
            raise ValueError("Scenarios must have a ruleset_id")

        if scenario_id is None:
            scenario_id = str(uuid.uuid4())

        with self.db_config.create_session() as session:
            existing_scenario = session.query(Scenario).filter(Scenario.id == scenario_id).first()

            if existing_scenario:
                existing_scenario.scenario_data = scenario_data
                existing_scenario.schema_version = schema_version
                existing_scenario.user_id = user_id
                existing_scenario.ruleset_id = ruleset_id
                existing_scenario.character_ids = character_ids
                existing_scenario.updated_at = datetime.now()
            else:
                scenario = Scenario(
                    id=scenario_id,
                    scenario_data=scenario_data,
                    schema_version=schema_version,
                    user_id=user_id,
                    ruleset_id=ruleset_id,
                    character_ids=character_ids,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                session.add(scenario)

            session.commit()
            return scenario_id

    def get_scenario(self, scenario_id: str, user_id: str = "anonymous") -> dict[str, Any] | None:
        """Retrieve a scenario by ID."""
        with self.db_config.create_session() as session:
            scenario = (
                session.query(Scenario)
                .filter(
                    Scenario.id == scenario_id,
                    or_(Scenario.user_id == user_id, Scenario.user_id == "anonymous"),
                )
                .first()
            )

            if scenario:
                return self._row_to_dict(scenario)
            return None

    def get_all_scenarios(
        self,
        user_id: str = "anonymous",
        schema_version: int | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve all scenarios for a user."""
        with self.db_config.create_session() as session:
            query = session.query(Scenario).filter(
                or_(Scenario.user_id == user_id, Scenario.user_id == "anonymous")
            )

            if schema_version is not None:
                query = query.filter(Scenario.schema_version == schema_version)

            scenarios = query.order_by(Scenario.updated_at.desc()).all()
            return [self._row_to_dict(s) for s in scenarios]

    def get_scenarios_by_ruleset(
        self,
        ruleset_id: str,
        user_id: str = "anonymous",
    ) -> list[dict[str, Any]]:
        """Retrieve all scenarios referencing a specific ruleset."""
        with self.db_config.create_session() as session:
            scenarios = (
                session.query(Scenario)
                .filter(
                    Scenario.ruleset_id == ruleset_id,
                    or_(Scenario.user_id == user_id, Scenario.user_id == "anonymous"),
                )
                .order_by(Scenario.updated_at.desc())
                .all()
            )
            return [self._row_to_dict(s) for s in scenarios]

    def get_scenario_ids_for_character(
        self,
        character_id: str,
        user_id: str = "anonymous",
    ) -> set[str]:
        """
        Return scenario IDs where the character participates.

        Matches both NPC participation (`character_ids`) and persona usage (`persona_id`).
        Also supports legacy single-character scenario payloads (`character_id`).
        """
        with self.db_config.create_session() as session:
            scenarios = (
                session.query(Scenario)
                .filter(or_(Scenario.user_id == user_id, Scenario.user_id == "anonymous"))
                .all()
            )

            matching_ids: set[str] = set()
            for scenario in scenarios:
                scenario_data = scenario.scenario_data or {}
                scenario_character_ids = set(scenario.character_ids or [])
                scenario_character_ids.update(scenario_data.get("character_ids") or [])

                persona_id = scenario_data.get("persona_id")
                legacy_character_id = scenario_data.get("character_id")

                if (
                    character_id in scenario_character_ids
                    or persona_id == character_id
                    or legacy_character_id == character_id
                ):
                    matching_ids.add(scenario.id)

            return matching_ids

    def delete_scenario(self, scenario_id: str, user_id: str = "anonymous") -> bool:
        """Delete a scenario by ID."""
        with self.db_config.create_session() as session:
            count = (
                session.query(Scenario)
                .filter(Scenario.id == scenario_id, Scenario.user_id == user_id)
                .delete()
            )
            session.commit()
            return count > 0

    def scenario_exists(self, scenario_id: str, user_id: str = "anonymous") -> bool:
        """Check if a scenario exists for a specific user."""
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
        """Get the total number of scenarios stored for a user."""
        with self.db_config.create_session() as session:
            return (
                session.query(func.count(Scenario.id))
                .filter(or_(Scenario.user_id == user_id, Scenario.user_id == "anonymous"))
                .scalar()
            )

    def _row_to_dict(self, scenario: Scenario) -> dict[str, Any]:
        return {
            "id": scenario.id,
            "scenario_data": scenario.scenario_data,
            "schema_version": scenario.schema_version,
            "ruleset_id": scenario.ruleset_id,
            "character_ids": scenario.character_ids,
            "created_at": scenario.created_at.isoformat(),
            "updated_at": scenario.updated_at.isoformat(),
        }

    def health_check(self) -> bool:
        """Check if the database is accessible and healthy."""
        return self.db_config.health_check()

    def close(self) -> None:
        """Close the database connection and dispose of engine resources."""
        self.db_config.dispose()
