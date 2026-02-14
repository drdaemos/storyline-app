"""Registry for storing and retrieving rulesets from database."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import or_

from .database_config import DatabaseConfig
from .db_models import RulesetDB


class RulesetRegistry:
    """SQLAlchemy-based persistent ruleset storage."""

    def __init__(self, memory_dir: Path | None = None) -> None:
        self.db_config = DatabaseConfig(memory_dir)

    def save_ruleset(
        self,
        name: str,
        rules_text: str,
        state_schemas: dict[str, Any],
        config: dict[str, Any],
        ruleset_id: str | None = None,
        user_id: str = "anonymous",
    ) -> str:
        """Save or update a ruleset. Returns the ruleset ID."""
        if ruleset_id is None:
            ruleset_id = str(uuid.uuid4())

        with self.db_config.create_session() as session:
            existing = session.query(RulesetDB).filter(RulesetDB.id == ruleset_id).first()

            if existing:
                existing.name = name
                existing.rules_text = rules_text
                existing.state_schemas = state_schemas
                existing.config = config
                existing.user_id = user_id
                existing.updated_at = datetime.now()
            else:
                ruleset = RulesetDB(
                    id=ruleset_id,
                    name=name,
                    rules_text=rules_text,
                    state_schemas=state_schemas,
                    config=config,
                    user_id=user_id,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                session.add(ruleset)

            session.commit()
            return ruleset_id

    def get_ruleset(self, ruleset_id: str, user_id: str = "anonymous") -> dict[str, Any] | None:
        """Retrieve a ruleset by ID."""
        with self.db_config.create_session() as session:
            ruleset = (
                session.query(RulesetDB)
                .filter(
                    RulesetDB.id == ruleset_id,
                    or_(RulesetDB.user_id == user_id, RulesetDB.user_id == "anonymous"),
                )
                .first()
            )

            if ruleset:
                return {
                    "id": ruleset.id,
                    "name": ruleset.name,
                    "rules_text": ruleset.rules_text,
                    "state_schemas": ruleset.state_schemas,
                    "config": ruleset.config,
                    "user_id": ruleset.user_id,
                    "created_at": ruleset.created_at.isoformat(),
                    "updated_at": ruleset.updated_at.isoformat(),
                }
            return None

    def get_all_rulesets(self, user_id: str = "anonymous") -> list[dict[str, Any]]:
        """Retrieve all rulesets for a user."""
        with self.db_config.create_session() as session:
            rulesets = (
                session.query(RulesetDB)
                .filter(or_(RulesetDB.user_id == user_id, RulesetDB.user_id == "anonymous"))
                .order_by(RulesetDB.updated_at.desc())
                .all()
            )

            return [
                {
                    "id": r.id,
                    "name": r.name,
                    "rules_text": r.rules_text,
                    "state_schemas": r.state_schemas,
                    "config": r.config,
                    "user_id": r.user_id,
                    "created_at": r.created_at.isoformat(),
                    "updated_at": r.updated_at.isoformat(),
                }
                for r in rulesets
            ]

    def delete_ruleset(self, ruleset_id: str, user_id: str = "anonymous") -> bool:
        """Delete a ruleset by ID. Returns True if deleted."""
        with self.db_config.create_session() as session:
            count = (
                session.query(RulesetDB)
                .filter(RulesetDB.id == ruleset_id, RulesetDB.user_id == user_id)
                .delete()
            )
            session.commit()
            return count > 0

    def health_check(self) -> bool:
        return self.db_config.health_check()

    def close(self) -> None:
        self.db_config.dispose()
