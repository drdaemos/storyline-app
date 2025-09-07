import os
from collections.abc import Iterator
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from src.chat_logger import ChatLogger
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

    def set_logger(self, logger: ChatLogger) -> None:
        self.logger = logger

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

    def respond_with_text(
        self,
        prompt: str,
        user_prompt: str,
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None,
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
        response = self._process_string(messages, max_tokens)
        
        self.logger.log_message(f"{self.__class__}", response)
        return response

    def respond_with_model(
        self,
        prompt: str,
        user_prompt: str,
        output_type: type[T],
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None,
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
        return self._process_structured(messages, output_type, max_tokens)

    def respond_with_stream(
        self,
        prompt: str,
        user_prompt: str,
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None,
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
        return self._process_string_streaming(messages, max_tokens)

    def _create_messages(self, prompt: str, user_prompt: str, conversation_history: list[GenericMessage] | None = None) -> list[GenericMessage]:
        """Create messages list from prompt components."""
        messages = [{ "role": "developer", "content": prompt }] + (conversation_history or []) + [
            {
                "role": "user",
                "content": user_prompt.strip()
            }
        ]
        return messages

    def _process_structured(
        self,
        messages: list[GenericMessage],
        output_type: type[T],
        max_tokens: int | None
    ) -> T:
        """Process prompt and return structured Pydantic model using structured outputs."""
        response = self.client.responses.parse(
            model=self.model,
            input=messages,
            text_format=output_type,
            max_output_tokens=max_tokens
        )

        if response.output_parsed is None:
            raise ValueError("Failed to parse structured response from OpenAI API")

        return response.output_parsed

    def _process_string(
        self,
        messages: list[GenericMessage],
        max_tokens: int | None
    ) -> str:
        """Process prompt and return string response."""
        response = self.client.responses.create(
            model=self.model,
            input=messages,
            max_output_tokens=max_tokens,
            stream=False
        )

        return response.output_text

    def _process_string_streaming(
        self,
        messages: list[GenericMessage],
        max_tokens: int | None
    ) -> Iterator[str]:
        """Process prompt and yield streaming string response chunks."""
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens or 4096,
            stream=True
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

