"""Registry for storing and retrieving world lore entries from database."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import or_

from .database_config import DatabaseConfig
from .db_models import WorldLoreDB


class WorldLoreRegistry:
    """SQLAlchemy-based persistent world lore storage."""

    def __init__(self, memory_dir: Path | None = None) -> None:
        self.db_config = DatabaseConfig(memory_dir)

    def save_lore(
        self,
        name: str,
        content: str,
        tags: list[str],
        lore_id: str | None = None,
        user_id: str = "anonymous",
    ) -> str:
        """Save or update a world lore entry. Returns the lore ID."""
        if lore_id is None:
            lore_id = str(uuid.uuid4())

        with self.db_config.create_session() as session:
            existing = session.query(WorldLoreDB).filter(WorldLoreDB.id == lore_id).first()

            if existing:
                existing.name = name
                existing.content = content
                existing.tags = tags
                existing.user_id = user_id
                existing.updated_at = datetime.now()
            else:
                lore = WorldLoreDB(
                    id=lore_id,
                    name=name,
                    content=content,
                    tags=tags,
                    user_id=user_id,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                session.add(lore)

            session.commit()
            return lore_id

    def get_lore(self, lore_id: str, user_id: str = "anonymous") -> dict[str, Any] | None:
        """Retrieve a lore entry by ID."""
        with self.db_config.create_session() as session:
            lore = (
                session.query(WorldLoreDB)
                .filter(
                    WorldLoreDB.id == lore_id,
                    or_(WorldLoreDB.user_id == user_id, WorldLoreDB.user_id == "anonymous"),
                )
                .first()
            )

            if lore:
                return {
                    "id": lore.id,
                    "name": lore.name,
                    "content": lore.content,
                    "tags": lore.tags,
                    "user_id": lore.user_id,
                    "created_at": lore.created_at.isoformat(),
                    "updated_at": lore.updated_at.isoformat(),
                }
            return None

    def get_all_lore(self, user_id: str = "anonymous") -> list[dict[str, Any]]:
        """Retrieve all lore entries for a user."""
        with self.db_config.create_session() as session:
            entries = (
                session.query(WorldLoreDB)
                .filter(or_(WorldLoreDB.user_id == user_id, WorldLoreDB.user_id == "anonymous"))
                .order_by(WorldLoreDB.updated_at.desc())
                .all()
            )

            return [
                {
                    "id": e.id,
                    "name": e.name,
                    "content": e.content,
                    "tags": e.tags,
                    "user_id": e.user_id,
                    "created_at": e.created_at.isoformat(),
                    "updated_at": e.updated_at.isoformat(),
                }
                for e in entries
            ]

    def get_lore_by_tags(self, tags: list[str], user_id: str = "anonymous") -> list[dict[str, Any]]:
        """Retrieve lore entries that contain any of the given tags.

        Uses JSON containment for tag matching. For SQLite, filters in Python
        since SQLite lacks native JSON array containment operators.
        """
        with self.db_config.create_session() as session:
            entries = (
                session.query(WorldLoreDB)
                .filter(or_(WorldLoreDB.user_id == user_id, WorldLoreDB.user_id == "anonymous"))
                .order_by(WorldLoreDB.updated_at.desc())
                .all()
            )

            # Filter by tag overlap in Python (works for both SQLite and PostgreSQL)
            tag_set = set(tags)
            return [
                {
                    "id": e.id,
                    "name": e.name,
                    "content": e.content,
                    "tags": e.tags,
                    "user_id": e.user_id,
                    "created_at": e.created_at.isoformat(),
                    "updated_at": e.updated_at.isoformat(),
                }
                for e in entries
                if tag_set.intersection(e.tags or [])
            ]

    def get_lore_by_ids(self, lore_ids: list[str], user_id: str = "anonymous") -> list[dict[str, Any]]:
        """Retrieve multiple lore entries by their IDs."""
        if not lore_ids:
            return []

        with self.db_config.create_session() as session:
            entries = (
                session.query(WorldLoreDB)
                .filter(
                    WorldLoreDB.id.in_(lore_ids),
                    or_(WorldLoreDB.user_id == user_id, WorldLoreDB.user_id == "anonymous"),
                )
                .all()
            )

            return [
                {
                    "id": e.id,
                    "name": e.name,
                    "content": e.content,
                    "tags": e.tags,
                    "user_id": e.user_id,
                    "created_at": e.created_at.isoformat(),
                    "updated_at": e.updated_at.isoformat(),
                }
                for e in entries
            ]

    def get_all_tags(self, user_id: str = "anonymous") -> list[str]:
        """Get all unique tags across all lore entries for a user."""
        with self.db_config.create_session() as session:
            entries = (
                session.query(WorldLoreDB.tags)
                .filter(or_(WorldLoreDB.user_id == user_id, WorldLoreDB.user_id == "anonymous"))
                .all()
            )

            all_tags: set[str] = set()
            for (tags,) in entries:
                if tags:
                    all_tags.update(tags)

            return sorted(all_tags)

    def delete_lore(self, lore_id: str, user_id: str = "anonymous") -> bool:
        """Delete a lore entry by ID. Returns True if deleted."""
        with self.db_config.create_session() as session:
            count = (
                session.query(WorldLoreDB)
                .filter(WorldLoreDB.id == lore_id, WorldLoreDB.user_id == user_id)
                .delete()
            )
            session.commit()
            return count > 0

    def health_check(self) -> bool:
        return self.db_config.health_check()

    def close(self) -> None:
        self.db_config.dispose()
