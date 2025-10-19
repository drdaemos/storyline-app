"""Factory for creating PromptProcessor instances based on processor type."""

from src.models.prompt_processor import PromptProcessor
from src.processors.claude_prompt_processor import ClaudePromptProcessor
from src.processors.cohere_prompt_processor import CoherePromptProcessor
from src.processors.openai_prompt_processor import OpenAiPromptProcessor
from src.processors.openrouter_prompt_processor import OpenRouterPromptProcessor


class PromptProcessorFactory:
    """Factory for creating PromptProcessor instances."""

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
        match processor_type.lower():
            case "cohere":
                return CoherePromptProcessor()
            case "claude-sonnet":
                return ClaudePromptProcessor(model="claude-sonnet-4-5-20250929")
            case "claude-haiku":
                return ClaudePromptProcessor(model="claude-haiku-4.5-20251015")
            case "gpt":
                return OpenAiPromptProcessor()
            case "gpt-4.1":
                return OpenAiPromptProcessor(model="gpt-4.1")
            case "grok":
                return OpenRouterPromptProcessor(model="x-ai/grok-4-fast")
            case "deepseek":
                return OpenRouterPromptProcessor(model="deepseek/deepseek-r1-0528")
            case "deepseek-chimera":
                return OpenRouterPromptProcessor(model="tngtech/deepseek-r1t2-chimera")
            case "google-flash":
                return OpenRouterPromptProcessor(model="google/gemini-2.5-flash")
            case "google-pro":
                return OpenRouterPromptProcessor(model="google/gemini-2.5-pro")
            case "ring":
                return OpenRouterPromptProcessor(model="inclusionai/ring-1t")
            case "glm":
                return OpenRouterPromptProcessor(model="z-ai/glm-4.6")
            case _:
                raise ValueError(f"Unsupported processor type: {processor_type}")

    @classmethod
    def get_default_backup_processor(cls) -> PromptProcessor:
        """
        Get the default backup processor.

        Returns:
            Default backup PromptProcessor instance
        """
        return OpenRouterPromptProcessor(model="deepseek/deepseek-chat-v3.1:free")

    @classmethod
    def get_available_processor_types(cls) -> list[str]:
        """
        Get list of available processor types.

        Returns:
            List of supported processor type names
        """
        return ["cohere", "claude-sonnet", "claude-haiku", "gpt", "gpt-4.1", "grok", "deepseek", "deepseek-chimera", "google-flash", "google-pro", "ring", "glm"]
