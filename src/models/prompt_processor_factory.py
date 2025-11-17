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
                return ClaudePromptProcessor(model="claude-sonnet-4-5")
            case "claude" | "claude-haiku":
                return ClaudePromptProcessor(model="claude-haiku-4-5")
            case "gpt":
                return OpenAiPromptProcessor()
            case "gpt-5.1":
                return OpenRouterPromptProcessor(model="openai/gpt-5.1-chat")
            case "grok":
                return OpenRouterPromptProcessor(model="x-ai/grok-4-fast")
            case "deepseek":
                return OpenRouterPromptProcessor(model="deepseek/deepseek-r1-0528")
            case "deepseek-chat-v3.1":
                return OpenRouterPromptProcessor(model="deepseek/deepseek-chat-v3.1")
            case "google" | "google-flash":
                return OpenRouterPromptProcessor(model="google/gemini-2.5-flash")
            case "google-pro":
                return OpenRouterPromptProcessor(model="google/gemini-2.5-pro")
            case "hermes":
                return OpenRouterPromptProcessor(model="nousresearch/hermes-4-405b")
            case "kimi":
                return OpenRouterPromptProcessor(model="moonshotai/kimi-k2-0905")
            case "glm":
                return OpenRouterPromptProcessor(model="z-ai/glm-4.6")
            case "sherlock-think":
                return OpenRouterPromptProcessor(model="openrouter/sherlock-think-alpha")
            case "kimi-thinking":
                return OpenRouterPromptProcessor(model="moonshotai/kimi-k2-thinking")
            case "qwen3-max":
                return OpenRouterPromptProcessor(model="qwen/qwen3-max")
            case "magistral-thinking":
                return OpenRouterPromptProcessor(model="mistralai/magistral-medium-2506:thinking")
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
        return ["cohere", "claude-sonnet", "claude-haiku", "gpt", "gpt-4.1", "grok", "deepseek", "deepseek-chat-v3.1", "google-flash", "google-pro", "hermes", "kimi", "glm", "polaris", "kimi-thinking", "qwen3-max", "magistral-thinking"]
