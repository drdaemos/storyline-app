import os
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from src.processors.openai_prompt_processor import OpenAiPromptProcessor

T = TypeVar('T', bound=BaseModel)

class OpenRouterPromptProcessor(OpenAiPromptProcessor):
    """
    Abstraction for processing text-based prompts using OpenAI client SDK and OpenRouter API.

    Supports:
    - String input variables with template rendering
    - Structured outputs for Pydantic models
    - String outputs for simple text responses
    """

    def __init__(self, api_key: str | None = None, model: str = "deepseek/deepseek-chat-v3.1") -> None:
        """
        Initialize the PromptProcessor.

        Args:
            api_key: OpenRouter API key. If None, uses OPENROUTER_API_KEY environment variable
            model: OpenRouter model to use for completions
        """
        self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key or os.getenv("OPENROUTER_API_KEY"))
        self.model = model


