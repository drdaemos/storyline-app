import os
from typing import Any, TypedDict, TypeVar

from openai import OpenAI
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

class Message(TypedDict):
    role: str
    content: str

class PromptProcessor:
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

    def process(
        self,
        prompt: str,
        user_prompt: str,
        conversation_history: list[Message] | None = None,
        variables: dict[str, Any] | None = None,
        output_type: type[str | BaseModel] = str,
        max_tokens: int | None = None
    ) -> str | BaseModel:
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
        # Render prompt template with variables
        rendered_prompt = self._render_prompt(user_prompt, variables or {})
        input = [{ "role": "developer", "content": prompt }] + (conversation_history or []) + [
            {
                "role": "user",
                "content": rendered_prompt
            }
        ]

        # Check if output_type is a Pydantic model
        if (isinstance(output_type, type) and
            issubclass(output_type, BaseModel) and
            output_type is not BaseModel):
            return self._process_structured(input, output_type, max_tokens)
        else:
            return self._process_string(input, max_tokens)

    def _render_prompt(self, prompt: str, variables: dict[str, Any]) -> str:
        """Render prompt template with provided variables."""
        try:
            return prompt.format(**variables)
        except KeyError as e:
            missing_var = str(e).strip("'")
            raise ValueError(f"Missing required variable in prompt: {missing_var}") from e

    def _process_structured(
        self,
        input: list[Message],
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
        input: list[Message],
        max_tokens: int | None
    ) -> str:
        """Process prompt and return string response."""
        response = self.client.responses.create(
            model=self.model,
            input=input,
            max_output_tokens=max_tokens
        )

        if response.output_text is None:
            raise ValueError("Received response from OpenAI API")

        return response.output_text

