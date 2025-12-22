"""Factory for creating PromptProcessor instances based on processor type."""

from src.models.prompt_processor import PromptProcessor
from src.processors.claude_prompt_processor import ClaudePromptProcessor
from src.processors.cohere_prompt_processor import CoherePromptProcessor
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
            case "claude-opus":
                return ClaudePromptProcessor(model="claude-opus-4-5")
            case "claude-sonnet":
                return ClaudePromptProcessor(model="claude-sonnet-4-5")
            case "claude" | "claude-haiku":
                return ClaudePromptProcessor(model="claude-haiku-4-5")
            case "gpt-5.2":
                return OpenRouterPromptProcessor(model="openai/gpt-5.2-chat")
            case "google" | "google-flash":
                return OpenRouterPromptProcessor(model="google/gemini-3-flash-preview")
            case "google-pro":
                return OpenRouterPromptProcessor(model="google/gemini-3-pro-preview")
            case "deepseek-v32":
                return OpenRouterPromptProcessor(model="deepseek/deepseek-v3.2")
            case "kimi":
                return OpenRouterPromptProcessor(model="moonshotai/kimi-k2-0905")
            case "kimi-thinking":
                return OpenRouterPromptProcessor(model="moonshotai/kimi-k2-thinking")
            case "mistral":
                return OpenRouterPromptProcessor(model="mistralai/mistral-small-creative")
            case "grok":
                return OpenRouterPromptProcessor(model="x-ai/grok-4.1-fast")
            case "glm":
                return OpenRouterPromptProcessor(model="z-ai/glm-4.7")
            case "cohere":
                return CoherePromptProcessor()
            case _:
                raise ValueError(f"Unsupported processor type: {processor_type}")

    @classmethod
    def get_default_backup_processor(cls) -> PromptProcessor:
        """
        Get the default backup processor.

        Returns:
            Default backup PromptProcessor instance
        """
        return OpenRouterPromptProcessor(model="deepseek/deepseek-v3.2")