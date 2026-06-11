"""Factory for creating PromptProcessor instances based on processor type."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

from src.models.prompt_processor import PromptProcessor
from src.processors.claude_prompt_processor import ClaudePromptProcessor
from src.processors.cohere_prompt_processor import CoherePromptProcessor
from src.processors.openrouter_prompt_processor import OpenRouterPromptProcessor


@dataclass(frozen=True)
class ProcessorOptionDescriptor:
    """Prompt processor option metadata exposed to the frontend."""

    id: str
    display_name: str


class PromptProcessorFactory:
    """Factory for creating PromptProcessor instances."""

    _PROCESSOR_CATALOG: ClassVar[
        tuple[tuple[str, str, Callable[[], PromptProcessor]], ...]
    ] = (
        ("claude-opus", "Claude Opus 4.5", lambda: ClaudePromptProcessor(model="claude-opus-4-5")),
        ("claude-sonnet", "Claude Sonnet 4.5", lambda: ClaudePromptProcessor(model="claude-sonnet-4-5")),
        ("claude-haiku", "Claude Haiku 4.5", lambda: ClaudePromptProcessor(model="claude-haiku-4-5")),
        ("gpt-5.2", "GPT-5.2 Chat", lambda: OpenRouterPromptProcessor(model="openai/gpt-5.2-chat")),
        ("google-flash", "Gemini 3 Flash", lambda: OpenRouterPromptProcessor(model="google/gemini-3-flash-preview")),
        ("google-pro", "Gemini 3 Pro", lambda: OpenRouterPromptProcessor(model="google/gemini-3-pro-preview")),
        ("deepseek-v32", "DeepSeek V3.2", lambda: OpenRouterPromptProcessor(model="deepseek/deepseek-v3.2")),
        ("kimi", "Kimi K2", lambda: OpenRouterPromptProcessor(model="moonshotai/kimi-k2-0905")),
        ("kimi-thinking", "Kimi K2 Thinking", lambda: OpenRouterPromptProcessor(model="moonshotai/kimi-k2-thinking")),
        ("mistral", "Mistral Small Creative", lambda: OpenRouterPromptProcessor(model="mistralai/mistral-small-creative")),
        ("grok", "Grok 4.1 Fast", lambda: OpenRouterPromptProcessor(model="x-ai/grok-4.1-fast")),
        ("glm", "GLM-4.7", lambda: OpenRouterPromptProcessor(model="z-ai/glm-4.7")),
        ("cohere", "Cohere Command A", CoherePromptProcessor),
    )
    _PROCESSOR_BUILDERS: ClassVar[dict[str, Callable[[], PromptProcessor]]] = {
        processor_id: builder for processor_id, _display_name, builder in _PROCESSOR_CATALOG
    }
    _PROCESSOR_DISPLAY_NAMES: ClassVar[dict[str, str]] = {
        processor_id: display_name
        for processor_id, display_name, _builder in _PROCESSOR_CATALOG
    }
    _PROCESSOR_ALIASES: ClassVar[dict[str, str]] = {
        "claude": "claude-haiku",
        "google": "google-flash",
    }

    @classmethod
    def create_processor(cls, processor_type: str) -> PromptProcessor:
        """
        Create a PromptProcessor instance based on the processor type.

        Args:
            processor_type: The type of processor to create

        Returns:
            PromptProcessor instance

        Raises:
            ValueError: If processor_type is not supported
        """
        normalized_type = processor_type.strip().lower()
        canonical_type = cls._PROCESSOR_ALIASES.get(normalized_type, normalized_type)
        processor_builder = cls._PROCESSOR_BUILDERS.get(canonical_type)
        if processor_builder is None:
            raise ValueError(f"Unsupported processor type: {processor_type}")
        return processor_builder()

    @classmethod
    def get_available_processor_types(cls) -> list[str]:
        """Return all selectable processor types for UI/model selection."""
        return list(cls._PROCESSOR_BUILDERS.keys())

    @classmethod
    def get_available_processor_options(cls) -> list[ProcessorOptionDescriptor]:
        """Return selectable processor IDs with user-facing display names."""
        return [
            ProcessorOptionDescriptor(id=processor_id, display_name=cls._PROCESSOR_DISPLAY_NAMES[processor_id])
            for processor_id in cls._PROCESSOR_BUILDERS
        ]

    @classmethod
    def get_default_backup_processor(cls) -> PromptProcessor:
        """
        Get the default backup processor.

        Returns:
            Default backup PromptProcessor instance
        """
        return OpenRouterPromptProcessor(model="deepseek/deepseek-v3.2")
