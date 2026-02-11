from __future__ import annotations

from src.models.prompt_processor import PromptProcessor
from src.models.prompt_processor_factory import PromptProcessorFactory


class ModelRouter:
    """Resolves model keys to prompt processors."""

    def __init__(self) -> None:
        self._cache: dict[str, PromptProcessor] = {}

    def get_processor(self, model_key: str) -> PromptProcessor:
        key = model_key.strip().lower()
        if not key:
            raise ValueError("model_key cannot be empty")
        if key not in self._cache:
            self._cache[key] = PromptProcessorFactory.create_processor(key)
        return self._cache[key]
