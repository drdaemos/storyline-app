"""Registry for storing and retrieving scenarios from database."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, or_

from .database_config import DatabaseConfig
from .db_models import SimulationScenario, SimulationScenarioCharacter


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

        character_ids = self._normalize_character_ids(scenario_data)
        if not character_id:
            if character_ids:
                character_id = character_ids[0]
            else:
                raise ValueError("Scenario must include at least one character")
        if character_id not in character_ids:
            character_ids = [character_id, *character_ids]

        payload = dict(scenario_data)
        payload["character_id"] = character_id
        payload["character_ids"] = character_ids
        ruleset_id = str(payload.get("ruleset_id") or "everyday-tension")
        world_lore_id = str(payload.get("world_lore_id") or "default-world")
        summary = str(payload.get("summary") or "Untitled")
        intro_seed = str(payload.get("intro_message") or "")
        scene_seed = payload.get("scene_seed")
        if not isinstance(scene_seed, dict):
            scene_seed = {}
        stakes = str(payload.get("stakes") or "")
        tone = str(payload.get("narrative_category") or "")
        goals = payload.get("character_goals")
        if not isinstance(goals, dict):
            goals = {}

        with self.db_config.create_session() as session:
            existing_scenario = session.query(SimulationScenario).filter(SimulationScenario.id == scenario_id).first()

            if existing_scenario:
                # Update existing scenario
                existing_scenario.title = summary
                existing_scenario.summary = summary
                existing_scenario.scenario_data = payload
                existing_scenario.ruleset_id = ruleset_id
                existing_scenario.world_lore_id = world_lore_id
                existing_scenario.scene_seed = scene_seed
                existing_scenario.stakes = stakes
                existing_scenario.tone = tone
                existing_scenario.goals = goals
                existing_scenario.intro_seed = intro_seed
                existing_scenario.character_id = character_id
                existing_scenario.schema_version = schema_version
                existing_scenario.user_id = user_id
                existing_scenario.updated_at = datetime.now()
            else:
                # Create new scenario
                scenario = SimulationScenario(
                    id=scenario_id,
                    title=summary,
                    summary=summary,
                    scenario_data=payload,
                    ruleset_id=ruleset_id,
                    world_lore_id=world_lore_id,
                    scene_seed=scene_seed,
                    stakes=stakes,
                    goals=goals,
                    tone=tone,
                    intro_seed=intro_seed,
                    character_id=character_id,
                    schema_version=schema_version,
                    user_id=user_id,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                session.add(scenario)

            session.query(SimulationScenarioCharacter).filter(SimulationScenarioCharacter.scenario_id == scenario_id).delete()
            for member_id in character_ids:
                session.add(
                    SimulationScenarioCharacter(
                        scenario_id=scenario_id,
                        character_id=member_id,
                    )
                )
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
            scenario = (
                session.query(SimulationScenario)
                .filter(
                    SimulationScenario.id == scenario_id,
                    or_(SimulationScenario.user_id == user_id, SimulationScenario.user_id == "anonymous"),
                )
                .first()
            )

            if scenario:
                scenario_payload = self._build_payload(session, scenario)
                return {
                    "id": scenario.id,
                    "character_id": scenario.character_id,
                    "scenario_data": scenario_payload,
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
            query = session.query(SimulationScenario).filter(
                or_(SimulationScenario.user_id == user_id, SimulationScenario.user_id == "anonymous"),
            )

            if schema_version is not None:
                query = query.filter(SimulationScenario.schema_version == schema_version)

            raw_scenarios = query.order_by(SimulationScenario.updated_at.desc()).all()
            scenarios: list[SimulationScenario] = []
            for scenario in raw_scenarios:
                members = self._load_scenario_members(session, scenario.id)
                payload = self._build_payload(session, scenario, members_override=members)
                if scenario.character_id == character_id or character_id in members:
                    scenario.scenario_data = payload
                    scenarios.append(scenario)

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
            query = session.query(SimulationScenario).filter(
                or_(SimulationScenario.user_id == user_id, SimulationScenario.user_id == "anonymous")
            )

            if schema_version is not None:
                query = query.filter(SimulationScenario.schema_version == schema_version)

            scenarios = query.order_by(SimulationScenario.updated_at.desc()).all()

            return [
                {
                    "id": s.id,
                    "character_id": s.character_id,
                    "scenario_data": self._build_payload(session, s),
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
            session.query(SimulationScenarioCharacter).filter(SimulationScenarioCharacter.scenario_id == scenario_id).delete()
            count = (
                session.query(SimulationScenario)
                .filter(SimulationScenario.id == scenario_id, SimulationScenario.user_id == user_id)
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
                session.query(SimulationScenario)
                .filter(
                    SimulationScenario.id == scenario_id,
                    or_(SimulationScenario.user_id == user_id, SimulationScenario.user_id == "anonymous"),
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
                session.query(func.count(SimulationScenario.id))
                .filter(or_(SimulationScenario.user_id == user_id, SimulationScenario.user_id == "anonymous"))
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
            member_scenarios = {row[0] for row in session.query(SimulationScenarioCharacter.scenario_id).filter(SimulationScenarioCharacter.character_id == character_id).all()}
            if not member_scenarios:
                return 0
            return (
                session.query(func.count(SimulationScenario.id))
                .filter(
                    SimulationScenario.id.in_(member_scenarios),
                    or_(SimulationScenario.user_id == user_id, SimulationScenario.user_id == "anonymous"),
                )
                .scalar()
            )

    def health_check(self) -> bool:
        """Check if the database is accessible and healthy."""
        return self.db_config.health_check()

    def close(self) -> None:
        """Close the database connection and dispose of engine resources."""
        self.db_config.dispose()

    def _normalize_character_ids(self, scenario_data: dict[str, Any]) -> list[str]:
        ids = scenario_data.get("character_ids")
        if not isinstance(ids, list):
            return []
        ordered: list[str] = []
        for item in ids:
            value = str(item).strip()
            if value and value not in ordered:
                ordered.append(value)
        return ordered

    def _load_scenario_members(self, session: Any, scenario_id: str) -> list[str]:
        rows = (
            session.query(SimulationScenarioCharacter)
            .filter(SimulationScenarioCharacter.scenario_id == scenario_id)
            .order_by(SimulationScenarioCharacter.created_at.asc(), SimulationScenarioCharacter.character_id.asc())
            .all()
        )
        return [row.character_id for row in rows]

    def _build_payload(self, session: Any, scenario: SimulationScenario, members_override: list[str] | None = None) -> dict[str, Any]:
        payload = dict(scenario.scenario_data or {})
        character_ids = members_override if members_override is not None else self._load_scenario_members(session, scenario.id)
        payload.setdefault("summary", scenario.summary)
        payload.setdefault("intro_message", scenario.intro_seed)
        payload.setdefault("narrative_category", scenario.tone)
        payload.setdefault("character_id", scenario.character_id)
        payload["character_ids"] = character_ids
        payload.setdefault("ruleset_id", scenario.ruleset_id)
        payload.setdefault("world_lore_id", scenario.world_lore_id)
        payload.setdefault("scene_seed", scenario.scene_seed or {})
        payload.setdefault("stakes", scenario.stakes)
        payload.setdefault("character_goals", scenario.goals or {})
        return payload
