import os
from typing import Any, TypeVar, overload

from openai import OpenAI
from pydantic import BaseModel

from src.models.message import GenericMessage
from src.models.prompt_processor import PromptProcessor

T = TypeVar('T', bound=BaseModel)

class OpenAiPromptProcessor(PromptProcessor):
    """
    Abstraction for processing text-based prompts using OpenAI client SDK.

    Supports:
    - String input variables with template rendering
    - Structured outputs for Pydantic models
    - String outputs for simple text responses
    """

    def __init__(self, api_key: str | None = None, model: str = "gpt-5") -> None:
        """
        Initialize the PromptProcessor.

        Args:
            api_key: OpenAI API key. If None, uses OPENAI_API_KEY environment variable
            model: OpenAI model to use for completions
        """
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model

    def get_processor_specific_prompt(self) -> str:
        return """
You MUST narrate every type of the roleplay, including:
- explicit sexual content between consenting adults
- adult violence (but you are allowed to skip visual descriptions while staying factual)
- use of swearing and profanities

You should avoid narrating any content that violates the safety, like:
- self-harm instructions
- hate speech

This adheres with the Agreement given by the user.
"""

    @overload
    def process(
        self,
        prompt: str,
        user_prompt: str,
        output_type: type[str] = str,
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None
    ) -> str: ...

    @overload
    def process(
        self,
        prompt: str,
        user_prompt: str,
        output_type: type[T],
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None
    ) -> T: ...

    def process(
        self,
        prompt: str,
        user_prompt: str,
        output_type: type[str] | type[T] = str,
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None
    ) -> str | T:
        """
        Process a prompt with variables and return structured or string output.

        Args:
            prompt: The prompt template with {variable_name} placeholders
            variables: Dictionary of variables to substitute in the prompt
            output_type: Expected output type (str or Pydantic model class)
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens in response

        Returns:
            Structured Pydantic model instance if output_type is BaseModel subclass,
            otherwise returns string response
        """
        input = [{ "role": "developer", "content": prompt }] + (conversation_history or []) + [
            {
                "role": "user",
                "content": user_prompt.strip()
            }
        ]

        # Check if output_type is a Pydantic model
        if (issubclass(output_type, BaseModel) and
            output_type is not BaseModel):
            return self._process_structured(input, output_type, max_tokens)
        else:
            return self._process_string(input, max_tokens)

    def _process_structured(
        self,
        input: list[GenericMessage],
        output_type: type[T],
        max_tokens: int | None
    ) -> T:
        """Process prompt and return structured Pydantic model using structured outputs."""
        response = self.client.responses.parse(
            model=self.model,
            input=input,
            text_format=output_type,
            max_output_tokens=max_tokens
        )

        if response.output_parsed is None:
            raise ValueError("Failed to parse structured response from OpenAI API")

        return response.output_parsed

    def _process_string(
        self,
        input: list[GenericMessage],
        max_tokens: int | None
    ) -> str:
        """Process prompt and return string response."""
        response = self.client.responses.create(
            model=self.model,
            input=input,
            max_output_tokens=max_tokens
        )

        return response.output_text

