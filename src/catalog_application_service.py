from __future__ import annotations

from dataclasses import dataclass

from src.character_loader import CharacterLoader
from src.character_manager import CharacterManager
from src.memory.scenario_registry import ScenarioRegistry
from src.memory.world_lore_registry import WorldLoreRegistry
from src.models.api_models import (
    CharacterSummary,
    SaveScenarioRequest,
    SaveWorldLoreRequest,
    Scenario,
    ScenarioSummary,
    WorldLoreAsset,
)
from src.simulation.repository import SimulationRepository


def _normalize_tag(term: str) -> str:
    return " ".join(term.split()).strip().lower()


@dataclass
class CatalogApplicationService:
    """Application boundary for non-session catalog operations."""

    character_loader: CharacterLoader
    character_manager: CharacterManager
    scenario_registry: ScenarioRegistry
    world_lore_registry: WorldLoreRegistry
    simulation_repository: SimulationRepository

    @classmethod
    def create_default(
        cls,
        *,
        character_loader: CharacterLoader,
        character_manager: CharacterManager,
        scenario_registry: ScenarioRegistry,
        world_lore_registry: WorldLoreRegistry,
        simulation_repository: SimulationRepository,
    ) -> CatalogApplicationService:
        return cls(
            character_loader=character_loader,
            character_manager=character_manager,
            scenario_registry=scenario_registry,
            world_lore_registry=world_lore_registry,
            simulation_repository=simulation_repository,
        )

    def list_characters(self, user_id: str) -> list[CharacterSummary]:
        return self.character_loader.list_character_summaries(user_id)

    def list_personas(self, user_id: str) -> list[CharacterSummary]:
        return self.character_loader.list_persona_summaries(user_id)

    def get_character_info(self, character_name: str, user_id: str):
        return self.character_loader.get_character_info(character_name, user_id)

    def create_character(self, payload: dict, user_id: str, *, is_yaml_text: bool = False, is_persona: bool = False) -> tuple[str, str]:
        if is_yaml_text:
            if not isinstance(payload, str):
                raise ValueError("When is_yaml_text is true, data must be a string")
            character_data = self.character_manager.validate_yaml_text(payload)
        else:
            if not isinstance(payload, dict):
                raise ValueError("When is_yaml_text is false, data must be structured character data")
            character_data = payload
        filename = self.character_manager.create_character_file(character_data, user_id=user_id, is_persona=is_persona)
        return (filename, character_data["name"])

    def update_character(self, character_id: str, payload: dict, user_id: str, *, is_yaml_text: bool = False) -> tuple[str, str]:
        if is_yaml_text:
            if not isinstance(payload, str):
                raise ValueError("When is_yaml_text is true, data must be a string")
            character_data = self.character_manager.validate_yaml_text(payload)
        else:
            if not isinstance(payload, dict):
                raise ValueError("When is_yaml_text is false, data must be structured character data")
            character_data = payload
        updated_character_id = self.character_manager.update_character(character_id, character_data, user_id=user_id)
        return (updated_character_id, character_data["name"])

    def list_rulesets(self):
        return self.simulation_repository.list_rulesets()

    def get_ruleset(self, ruleset_id: str):
        return self.simulation_repository.get_ruleset(ruleset_id)

    def _resolve_character_ids_from_tags(self, tags: list[str], user_id: str) -> list[str]:
        normalized_tags = {_normalize_tag(tag) for tag in tags if _normalize_tag(tag)}
        if not normalized_tags:
            return []
        matched: list[str] = []
        for character in self.character_loader.list_character_summaries(user_id):
            if character.is_persona:
                continue
            character_tags = {_normalize_tag(tag) for tag in character.tags}
            if character_tags.intersection(normalized_tags):
                matched.append(character.id)
        return matched

    def _resolve_world_lore_id_from_tags(self, tags: list[str], user_id: str) -> str | None:
        normalized_tags = {_normalize_tag(tag) for tag in tags if _normalize_tag(tag)}
        if not normalized_tags:
            return None
        items = self.world_lore_registry.list_world_lore(user_id)
        best_id: str | None = None
        best_score = 0
        for item in items:
            item_tags = {_normalize_tag(tag) for tag in item.get("tags", [])}
            score = len(item_tags.intersection(normalized_tags))
            if score > best_score:
                best_score = score
                best_id = str(item["id"])
        return best_id

    def save_scenario(self, request: SaveScenarioRequest, user_id: str) -> str:
        if not request.scenario.summary or not request.scenario.intro_message:
            raise ValueError("Scenario must have summary and intro_message")

        character_tags = request.scenario.character_tags or []
        if not character_tags:
            raise ValueError("Scenario must include at least one character tag")
        character_ids = self._resolve_character_ids_from_tags(character_tags, user_id)
        if not character_ids:
            raise ValueError("No characters found for selected character tags")

        world_lore_tags = request.scenario.world_lore_tags or []
        world_lore_id = self._resolve_world_lore_id_from_tags(world_lore_tags, user_id) if world_lore_tags else "default-world"
        if world_lore_tags and not world_lore_id:
            raise ValueError("No world lore found for selected world lore tags")

        ruleset_id = request.scenario.ruleset_id or "everyday-tension"
        self.simulation_repository.get_ruleset(ruleset_id)

        primary_character_id = character_ids[0]
        scenario_payload = request.scenario.model_dump()
        scenario_payload["character_id"] = primary_character_id
        scenario_payload["character_ids"] = character_ids
        scenario_payload["world_lore_id"] = world_lore_id
        scenario_payload["ruleset_id"] = ruleset_id

        return self.scenario_registry.save_scenario(
            scenario_data=scenario_payload,
            character_id=primary_character_id,
            scenario_id=request.scenario_id,
            user_id=user_id,
        )

    def list_scenarios_for_character(self, character_name: str, user_id: str) -> list[ScenarioSummary]:
        character = self.character_loader.load_character(character_name, user_id)
        if not character:
            raise FileNotFoundError(f"Character '{character_name}' not found")
        scenarios = self.scenario_registry.get_scenarios_for_character(character_name, user_id)
        return [self._to_scenario_summary(row) for row in scenarios]

    def list_all_scenarios(self, user_id: str) -> list[ScenarioSummary]:
        scenarios = self.scenario_registry.get_all_scenarios(user_id)
        return [self._to_scenario_summary(row) for row in scenarios]

    def get_scenario_detail(self, scenario_id: str, user_id: str) -> Scenario | None:
        scenario_data = self.scenario_registry.get_scenario(scenario_id, user_id)
        if not scenario_data:
            return None
        return Scenario(**scenario_data["scenario_data"])

    def delete_scenario(self, scenario_id: str, user_id: str) -> bool:
        if not self.scenario_registry.scenario_exists(scenario_id, user_id):
            return False
        return self.scenario_registry.delete_scenario(scenario_id, user_id)

    def list_world_lore(self, user_id: str) -> list[WorldLoreAsset]:
        rows = self.world_lore_registry.list_world_lore(user_id)
        return [WorldLoreAsset(**row) for row in rows]

    def get_world_lore(self, world_lore_id: str, user_id: str) -> WorldLoreAsset | None:
        row = self.world_lore_registry.get_world_lore(world_lore_id, user_id)
        if row is None:
            return None
        return WorldLoreAsset(**row)

    def save_world_lore(self, request: SaveWorldLoreRequest, user_id: str) -> str:
        return self.world_lore_registry.save_world_lore(
            name=request.name,
            lore_text=request.lore_text,
            tags=request.tags,
            keywords=request.keywords,
            lore_json=request.lore_json,
            world_lore_id=request.world_lore_id,
            user_id=user_id,
        )

    def delete_world_lore(self, world_lore_id: str, user_id: str) -> bool:
        return self.world_lore_registry.delete_world_lore(world_lore_id, user_id)

    def _to_scenario_summary(self, row: dict) -> ScenarioSummary:
        payload = row["scenario_data"]
        return ScenarioSummary(
            id=row["id"],
            summary=payload.get("summary", "Untitled"),
            narrative_category=payload.get("narrative_category", ""),
            character_id=row["character_id"],
            character_ids=payload.get("character_ids", []),
            character_tags=payload.get("character_tags", []),
            ruleset_id=payload.get("ruleset_id", "everyday-tension"),
            world_lore_id=payload.get("world_lore_id"),
            world_lore_tags=payload.get("world_lore_tags", []),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
