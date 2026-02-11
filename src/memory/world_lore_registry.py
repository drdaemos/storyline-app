"""Registry for storing and retrieving world lore assets."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .database_config import DatabaseConfig
from .db_models import WorldLoreRecord


class WorldLoreRegistry:
    """Persistent storage for world lore records."""

    def __init__(self, memory_dir: Path | None = None) -> None:
        self.db_config = DatabaseConfig(memory_dir)

    def save_world_lore(
        self,
        name: str,
        lore_text: str,
        lore_json: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        keywords: list[str] | None = None,
        world_lore_id: str | None = None,
        user_id: str = "anonymous",
    ) -> str:
        if world_lore_id is None:
            world_lore_id = str(uuid.uuid4())

        with self.db_config.create_session() as session:
            existing = session.query(WorldLoreRecord).filter(WorldLoreRecord.id == world_lore_id).first()
            merged_lore_json: dict[str, Any] = {}
            if existing and isinstance(existing.lore_json, dict):
                merged_lore_json.update(existing.lore_json)
            if lore_json:
                merged_lore_json.update(lore_json)

            normalized_tags = self._normalize_terms(tags) if tags is not None else self._normalize_terms(self._extract_terms(merged_lore_json, "tags"))
            normalized_keywords = self._normalize_terms(keywords) if keywords is not None else self._normalize_terms(self._extract_terms(merged_lore_json, "keywords"))
            merged_lore_json["tags"] = normalized_tags
            merged_lore_json["keywords"] = normalized_keywords

            if existing:
                existing.name = name
                existing.lore_text = lore_text
                existing.lore_json = merged_lore_json
                existing.updated_at = datetime.now()
            else:
                session.add(
                    WorldLoreRecord(
                        id=world_lore_id,
                        name=name,
                        lore_text=lore_text,
                        lore_json=merged_lore_json,
                    )
                )
            session.commit()
            return world_lore_id

    def get_world_lore(self, world_lore_id: str, user_id: str = "anonymous") -> dict[str, Any] | None:
        with self.db_config.create_session() as session:
            row = session.query(WorldLoreRecord).filter(WorldLoreRecord.id == world_lore_id).first()
            if row is None:
                return None
            lore_json = row.lore_json if isinstance(row.lore_json, dict) else {}
            return {
                "id": row.id,
                "name": row.name,
                "lore_text": row.lore_text,
                "tags": self._extract_terms(lore_json, "tags"),
                "keywords": self._extract_terms(lore_json, "keywords"),
                "lore_json": lore_json,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
            }

    def list_world_lore(self, user_id: str = "anonymous") -> list[dict[str, Any]]:
        with self.db_config.create_session() as session:
            rows = session.query(WorldLoreRecord).order_by(WorldLoreRecord.updated_at.desc()).all()
            return [{
                    "id": row.id,
                    "name": row.name,
                    "lore_text": row.lore_text,
                    "tags": self._extract_terms(row.lore_json if isinstance(row.lore_json, dict) else {}, "tags"),
                    "keywords": self._extract_terms(row.lore_json if isinstance(row.lore_json, dict) else {}, "keywords"),
                    "lore_json": row.lore_json if isinstance(row.lore_json, dict) else {},
                    "created_at": row.created_at.isoformat(),
                    "updated_at": row.updated_at.isoformat(),
                }
                for row in rows
            ]

    def delete_world_lore(self, world_lore_id: str, user_id: str = "anonymous") -> bool:
        if world_lore_id == "default-world":
            return False
        with self.db_config.create_session() as session:
            count = session.query(WorldLoreRecord).filter(WorldLoreRecord.id == world_lore_id).delete()
            session.commit()
            return count > 0

    def _extract_terms(self, lore_json: dict[str, Any], key: str) -> list[str]:
        raw = lore_json.get(key, [])
        if not isinstance(raw, list):
            return []
        return self._normalize_terms([str(item) for item in raw if isinstance(item, str)])

    def _normalize_terms(self, values: list[str] | None) -> list[str]:
        if not values:
            return []
        normalized: list[str] = []
        for raw in values:
            value = " ".join(raw.split()).strip()
            if not value:
                continue
            if value not in normalized:
                normalized.append(value)
        return normalized[:50]
