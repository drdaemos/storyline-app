import json
import os
from typing import Any, TypeVar, overload

import cohere
from pydantic import BaseModel

from src.chat_logger import ChatLogger
from src.models.message import GenericMessage
from src.models.prompt_processor import PromptProcessor

T = TypeVar('T', bound=BaseModel)

class CoherePromptProcessor(PromptProcessor):
    """
    Abstraction for processing text-based prompts using Cohere v2 API.

    Supports:
    - String input variables with template rendering
    - Structured outputs for Pydantic models
    - String outputs for simple text responses
    """

    def __init__(self, api_key: str | None = None, model: str = "command-a-03-2025") -> None:
        """
        Initialize the CoherePromptProcessor.

        Args:
            api_key: Cohere API key. If None, uses COHERE_API_KEY environment variable
            model: Cohere model to use for completions
        """
        self.client = cohere.ClientV2(api_key=api_key or os.getenv("COHERE_API_KEY"))
        self.model = model

    def set_logger(self, logger: ChatLogger) -> None:
        self.logger = logger

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
            prompt: The system prompt
            user_prompt: The user prompt template with {variable_name} placeholders
            conversation_history: Previous conversation messages
            output_type: Expected output type (str or Pydantic model class)
            max_tokens: Maximum tokens in response

        Returns:
            Structured Pydantic model instance if output_type is BaseModel subclass,
            otherwise returns string response
        """

        # Build messages list
        messages: list[GenericMessage] = [{"role": "system", "content": prompt.strip()}]
        if conversation_history:
            for msg in conversation_history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        messages.append({
            "role": "user",
            "content": user_prompt.strip(),
        })

        # Check if output_type is a Pydantic model
        if (issubclass(output_type, BaseModel) and
            output_type is not BaseModel):
            return self._process_structured(messages, output_type, max_tokens)
        else:
            return self._process_string(messages, max_tokens)
        
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

    def _render_prompt(self, prompt: str, variables: dict[str, Any]) -> str:
        """Render prompt template with provided variables."""
        try:
            return prompt.format(**variables)
        except KeyError as e:
            missing_var = str(e).strip("'")
            raise ValueError(f"Missing required variable in prompt: {missing_var}") from e

    def _process_structured(
        self,
        messages: list[GenericMessage],
        output_type: type[T],
        max_tokens: int | None
    ) -> T:
        """Process prompt and return structured Pydantic model."""
        response = self.client.chat(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens or 4096,
            response_format={
                "type": "json_object",
                "schema": output_type.model_json_schema()
            }
        )

        if not response.message or not response.message.content:
            raise ValueError("No response content received from Cohere API")

        # Parse the structured output
        try:
            content_text = response.message.content[0].text if isinstance(response.message.content, list) else response.message.content
            parsed_json = json.loads(content_text)
            return output_type.model_validate(parsed_json)
        except Exception as e:
            raise ValueError(f"Failed to parse structured response: {e}") from e

    def _process_string(
        self,
        messages: list[GenericMessage],
        max_tokens: int | None
    ) -> str:
        """Process prompt and return string response."""
        response = self.client.chat(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens or 4096
        )

        if not response.message or not response.message.content:
            raise ValueError("No response content received from Cohere API")

        # Extract text from response
        if isinstance(response.message.content, list):
            return "".join(block.text for block in response.message.content)
        else:
            return response.message.content
