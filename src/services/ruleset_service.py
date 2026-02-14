"""Service for loading rulesets and applying programmatic state updates."""

from typing import Any

from src.memory.ruleset_registry import RulesetRegistry
from src.models.simulation import (
    CharacterStateData,
    EmotionalStateData,
    Ruleset,
    RulesetConfig,
    RulesetStateSchemas,
)


class RulesetService:
    """Loads rulesets, validates state against schemas, and applies programmatic updates."""

    def __init__(self, ruleset_registry: RulesetRegistry) -> None:
        self.registry = ruleset_registry

    def load_ruleset(self, ruleset_id: str, user_id: str = "anonymous") -> Ruleset | None:
        """Load a ruleset from the registry and parse it into the domain model."""
        data = self.registry.get_ruleset(ruleset_id, user_id)
        if not data:
            return None

        return Ruleset(
            id=data["id"],
            name=data["name"],
            rules_text=data.get("rules_text", ""),
            state_schemas=RulesetStateSchemas(**data.get("state_schemas", {})),
            config=RulesetConfig(**data.get("config", {})),
            user_id=data.get("user_id", "anonymous"),
        )

    def initialize_character_state(
        self,
        ruleset: Ruleset,
        starting_drives: dict[str, float] | None = None,
        starting_skills: dict[str, float] | None = None,
        starting_emotional_state: dict[str, Any] | None = None,
    ) -> CharacterStateData:
        """Create a CharacterStateData from ruleset defaults, optionally overridden.

        Args:
            ruleset: The ruleset providing schema defaults
            starting_drives: Optional override for drive values
            starting_skills: Optional override for skill values
            starting_emotional_state: Optional override for emotional state

        Returns:
            Initialized CharacterStateData
        """
        schemas = ruleset.state_schemas

        # Initialize drives from schema defaults, then override
        drives: dict[str, float] = {}
        for drive_schema in schemas.drives:
            drives[drive_schema.name] = float(drive_schema.default)
        if starting_drives:
            for name, value in starting_drives.items():
                if name in drives:
                    drives[name] = value

        # Initialize skills (no defaults in schema — must come from character card)
        skills: dict[str, float] = {}
        for skill_schema in schemas.skills:
            skills[skill_schema.name] = 0.0
        if starting_skills:
            for name, value in starting_skills.items():
                if name in skills:
                    skills[name] = value

        # Initialize emotional state
        global_state: dict[str, float] = {}
        for dim in schemas.emotional_state.global_dims:
            global_state[dim.name] = float(dim.default)

        emotional_data = EmotionalStateData(global_state=global_state, per_relationship={})

        if starting_emotional_state:
            if "global_state" in starting_emotional_state:
                for name, value in starting_emotional_state["global_state"].items():
                    if name in emotional_data.global_state:
                        emotional_data.global_state[name] = value
            if "per_relationship" in starting_emotional_state:
                emotional_data.per_relationship = starting_emotional_state["per_relationship"]

        return CharacterStateData(
            drives=drives,
            skills=skills,
            emotional_state=emotional_data,
        )

    def apply_drive_decay(
        self,
        state: CharacterStateData,
        ruleset: Ruleset,
    ) -> CharacterStateData:
        """Apply per-turn drive decay: value = max(range_min, value - decay_rate).

        Modifies and returns the state.
        """
        schema_map = {d.name: d for d in ruleset.state_schemas.drives}

        for name in list(state.drives.keys()):
            schema = schema_map.get(name)
            if schema:
                state.drives[name] = max(
                    float(schema.range_min),
                    state.drives[name] - schema.decay_rate,
                )

        return state

    def apply_drive_effects(
        self,
        state: CharacterStateData,
        effects: list[dict[str, Any]],
        ruleset: Ruleset,
    ) -> CharacterStateData:
        """Apply drive effects (from GM evaluation) and clamp to range.

        Args:
            state: Current character state
            effects: List of {drive: str, change: float}
            ruleset: Ruleset for range bounds

        Returns:
            Updated state
        """
        schema_map = {d.name: d for d in ruleset.state_schemas.drives}

        for effect in effects:
            drive_name = effect.get("drive", "")
            change = float(effect.get("change", 0))

            if drive_name in state.drives:
                schema = schema_map.get(drive_name)
                new_val = state.drives[drive_name] + change
                if schema:
                    new_val = max(float(schema.range_min), min(float(schema.range_max), new_val))
                state.drives[drive_name] = new_val

        return state

    def apply_state_diffs(
        self,
        state: CharacterStateData,
        diffs: list[dict[str, Any]],
        ruleset: Ruleset,
    ) -> CharacterStateData:
        """Apply state diffs from character processing step (6.7).

        Diffs can target drives, skills, or emotional state dimensions.

        Args:
            state: Current character state
            diffs: List of {stat: str, target: str|None, change: float}
            ruleset: Ruleset for range bounds
        """
        drive_map = {d.name: d for d in ruleset.state_schemas.drives}
        skill_map = {s.name: s for s in ruleset.state_schemas.skills}
        global_dim_map = {d.name: d for d in ruleset.state_schemas.emotional_state.global_dims}
        rel_dim_map = {d.name: d for d in ruleset.state_schemas.emotional_state.per_relationship}

        for diff in diffs:
            stat = diff.get("stat", "")
            target = diff.get("target")
            change = float(diff.get("change", 0))

            # Check if it's a drive
            if stat in drive_map:
                schema = drive_map[stat]
                new_val = state.drives.get(stat, float(schema.default)) + change
                new_val = max(float(schema.range_min), min(float(schema.range_max), new_val))
                state.drives[stat] = new_val
                continue

            # Check if it's a skill
            if stat in skill_map:
                schema = skill_map[stat]
                new_val = state.skills.get(stat, 0.0) + change
                new_val = max(float(schema.range_min), min(float(schema.range_max), new_val))
                state.skills[stat] = new_val
                continue

            # Check if it's a global emotional dimension
            if stat in global_dim_map and target is None:
                schema = global_dim_map[stat]
                new_val = state.emotional_state.global_state.get(stat, float(schema.default)) + change
                new_val = max(float(schema.range_min), min(float(schema.range_max), new_val))
                state.emotional_state.global_state[stat] = new_val
                continue

            # Check if it's a per-relationship emotional dimension
            if stat in rel_dim_map and target is not None:
                schema = rel_dim_map[stat]
                if target not in state.emotional_state.per_relationship:
                    # Initialize from defaults
                    state.emotional_state.per_relationship[target] = {
                        d.name: float(d.default)
                        for d in ruleset.state_schemas.emotional_state.per_relationship
                    }
                current = state.emotional_state.per_relationship[target].get(stat, float(schema.default))
                new_val = current + change
                new_val = max(float(schema.range_min), min(float(schema.range_max), new_val))
                state.emotional_state.per_relationship[target][stat] = new_val

        return state

    def apply_offscreen_restore(
        self,
        state: CharacterStateData,
        ruleset: Ruleset,
    ) -> CharacterStateData:
        """Restore offscreen baselines when a character re-enters.

        Drives/emotions with offscreen_baseline set are restored to that value.
        Those with offscreen_baseline=None remain frozen (kept as-is).
        """
        for drive_schema in ruleset.state_schemas.drives:
            if drive_schema.offscreen_baseline is not None:
                state.drives[drive_schema.name] = float(drive_schema.offscreen_baseline)

        for dim in ruleset.state_schemas.emotional_state.global_dims:
            if dim.offscreen_baseline is not None:
                state.emotional_state.global_state[dim.name] = float(dim.offscreen_baseline)

        return state

    def clamp_all(
        self,
        state: CharacterStateData,
        ruleset: Ruleset,
    ) -> CharacterStateData:
        """Clamp all drives, skills, and emotional dimensions to their schema ranges."""
        for drive_schema in ruleset.state_schemas.drives:
            if drive_schema.name in state.drives:
                state.drives[drive_schema.name] = max(
                    float(drive_schema.range_min),
                    min(float(drive_schema.range_max), state.drives[drive_schema.name]),
                )

        for skill_schema in ruleset.state_schemas.skills:
            if skill_schema.name in state.skills:
                state.skills[skill_schema.name] = max(
                    float(skill_schema.range_min),
                    min(float(skill_schema.range_max), state.skills[skill_schema.name]),
                )

        for dim in ruleset.state_schemas.emotional_state.global_dims:
            if dim.name in state.emotional_state.global_state:
                state.emotional_state.global_state[dim.name] = max(
                    float(dim.range_min),
                    min(float(dim.range_max), state.emotional_state.global_state[dim.name]),
                )

        for _target, dims in state.emotional_state.per_relationship.items():
            for dim in ruleset.state_schemas.emotional_state.per_relationship:
                if dim.name in dims:
                    dims[dim.name] = max(
                        float(dim.range_min),
                        min(float(dim.range_max), dims[dim.name]),
                    )

        return state
