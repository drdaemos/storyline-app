import json
import os
from collections.abc import Iterator
from typing import TypeVar

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

    def respond_with_text(
        self,
        prompt: str,
        user_prompt: str,
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None,
        reasoning: bool = False,
    ) -> str:
        """
        Process a prompt and return text response.

        Args:
            prompt: The system prompt
            user_prompt: The user prompt
            conversation_history: Previous conversation messages
            max_tokens: Maximum tokens in response

        Returns: string response
        """
        messages = self._create_messages(prompt, user_prompt, conversation_history)
        response = self._process_string(messages, max_tokens,reasoning)

        return response

    def respond_with_model(
        self,
        prompt: str,
        user_prompt: str,
        output_type: type[T],
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None,
        reasoning: bool = False,
    ) -> T:
        """
        Process a prompt and return structured model response.

        Args:
            prompt: The system prompt
            user_prompt: The user prompt
            output_type: Expected Pydantic model type
            conversation_history: Previous conversation messages
            max_tokens: Maximum tokens in response

        Returns: structured model response
        """
        messages = self._create_messages(prompt, user_prompt, conversation_history)
        return self._process_structured(messages, output_type, max_tokens,reasoning)

    def respond_with_stream(
        self,
        prompt: str,
        user_prompt: str,
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None,
        reasoning: bool = False,
    ) -> Iterator[str]:
        """
        Process a prompt and yield streaming text response chunks.

        Args:
            prompt: The system prompt
            user_prompt: The user prompt
            conversation_history: Previous conversation messages
            max_tokens: Maximum tokens in response

        Returns: iterator of string chunks
        """
        messages = self._create_messages(prompt, user_prompt, conversation_history)
        return self._process_string_streaming(messages, max_tokens,reasoning)

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

    def _create_messages(self, prompt: str, user_prompt: str, conversation_history: list[GenericMessage] | None = None) -> list[GenericMessage]:
        """Create messages list from prompt components."""
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
        return messages

    def _process_structured(
        self,
        messages: list[GenericMessage],
        output_type: type[T],
        max_tokens: int | None,
        reasoning: bool = False
    ) -> T:
        """Process prompt and return structured Pydantic model."""
        response = self.client.chat(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens or 4096,
            thinking=None if reasoning else {"type": "disabled"},
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
        max_tokens: int | None,
        reasoning: bool = False,
    ) -> str:
        """Process prompt and return string response."""
        response = self.client.chat(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens or 4096,
            thinking=None if reasoning else {"type": "disabled"}
        )

        if not response.message or not response.message.content:
            raise ValueError("No response content received from Cohere API")

        # Extract text from response
        if isinstance(response.message.content, list):
            return "".join(block.text for block in response.message.content)
        else:
            return response.message.content

    def _process_string_streaming(
        self,
        messages: list[GenericMessage],
        max_tokens: int | None,
        reasoning: bool = False,
    ) -> Iterator[str]:
        """Process prompt and yield streaming string response chunks."""
        stream = self.client.chat_stream(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens or 4096,
            thinking=None if reasoning else {"type": "disabled"}
        )

        for chunk in stream:
            if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'message') and chunk.delta.message:
                if hasattr(chunk.delta.message, 'content') and chunk.delta.message.content:
                    if isinstance(chunk.delta.message.content, list):
                        for block in chunk.delta.message.content:
                            if hasattr(block, 'text'):
                                yield block.text
                    elif isinstance(chunk.delta.message.content, str):
                        yield chunk.delta.message.content
