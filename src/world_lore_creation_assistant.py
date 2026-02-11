"""Interactive AI assistant for creating world lore through conversation."""

import json
import re
from collections.abc import Callable

from pydantic import ValidationError

from .models.api_models import ChatMessageModel, PartialWorldLore
from .models.message import GenericMessage
from .models.prompt_processor import PromptProcessor


class WorldLoreCreationAssistant:
    """AI assistant that iteratively builds world lore entries."""

    def __init__(self, prompt_processor: PromptProcessor) -> None:
        self.prompt_processor = prompt_processor

    def process_message(
        self,
        user_message: str,
        current_world_lore: PartialWorldLore,
        conversation_history: list[ChatMessageModel],
        streaming_callback: Callable[[str], None] | None = None,
    ) -> tuple[str, PartialWorldLore]:
        system_prompt = self._build_system_prompt()
        history = [
            GenericMessage(role="user" if msg.is_user else "assistant", content=msg.content)
            for msg in conversation_history
        ]
        user_prompt = self._build_user_prompt(user_message, current_world_lore)

        if streaming_callback:
            ai_response_parts: list[str] = []
            for chunk in self.prompt_processor.respond_with_stream(
                prompt=system_prompt,
                user_prompt=user_prompt,
                conversation_history=history,
                max_tokens=2000,
            ):
                ai_response_parts.append(chunk)
                streaming_callback(chunk)
            ai_response = "".join(ai_response_parts)
        else:
            ai_response = self.prompt_processor.respond_with_text(
                prompt=system_prompt,
                user_prompt=user_prompt,
                conversation_history=history,
                max_tokens=2000,
            )

        updated_world_lore = self._extract_world_lore_updates(ai_response, current_world_lore)
        return ai_response, updated_world_lore

    def _build_system_prompt(self) -> str:
        return """You are an AI worldbuilding assistant helping users craft reusable world lore assets.

Your goal is to produce concise, rich, reusable context for scenario generation and runtime narration.

Rules:
- Be proactive: infer useful details and propose concrete improvements.
- Keep lore coherent and grounded in the user's requested tone/genre.
- Avoid filler and generic phrasing.
- Keep tags high-signal and filter-friendly (short labels).
- Keep keywords retrieval-oriented (alternate names, motifs, entities, places, themes).

Output updates in this exact block when modifying fields:
<world_lore_update>
{
  "name": "World lore name",
  "lore_text": "Main lore text",
  "tags": ["tag1", "tag2"],
  "keywords": ["keyword1", "keyword2"]
}
</world_lore_update>

Update guidance:
- `name`: concise and memorable.
- `lore_text`: should include social context, constraints, tone, institutions, and conflict vectors.
- `tags`: broad, user-facing filter buckets.
- `keywords`: denser retrieval terms and aliases for later search/vector workflows.
- Keep existing good content unless user asks to replace it.
"""

    def _build_user_prompt(self, user_message: str, current_world_lore: PartialWorldLore) -> str:
        return (
            "Current world lore state:\n\n"
            f"```json\n{current_world_lore.model_dump_json(indent=2)}\n```\n\n"
            f"User message: {user_message}\n"
            "Respond naturally and include <world_lore_update> when fields should be updated."
        )

    def _extract_world_lore_updates(self, ai_response: str, current_world_lore: PartialWorldLore) -> PartialWorldLore:
        update_pattern = r"<world_lore_update>\s*(\{[\s\S]*?\})\s*</world_lore_update>"
        match = re.search(update_pattern, ai_response)
        if not match:
            return current_world_lore
        try:
            update_json = match.group(1)
            parsed = PartialWorldLore.model_validate_json(update_json)
            cleaned = self._normalize_lists(parsed)
            return current_world_lore.model_copy(
                update=cleaned.model_dump(exclude_defaults=True, exclude_unset=True, exclude_none=True),
                deep=True,
            )
        except (json.JSONDecodeError, AttributeError, ValidationError):
            return current_world_lore

    def _normalize_lists(self, world_lore: PartialWorldLore) -> PartialWorldLore:
        return world_lore.model_copy(
            update={
                "tags": self._clean_terms(world_lore.tags),
                "keywords": self._clean_terms(world_lore.keywords),
            }
        )

    def _clean_terms(self, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for raw in values:
            term = " ".join(raw.split()).strip()
            if not term:
                continue
            if term not in normalized:
                normalized.append(term)
        return normalized[:50]
