import json
import os
from collections.abc import Iterator
from typing import TypeVar

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionUserMessageParam, ChatCompletionAssistantMessageParam
from pydantic import BaseModel

from src.chat_logger import ChatLogger
from src.models.message import GenericMessage
from src.models.prompt_processor import PromptProcessor

T = TypeVar('T', bound=BaseModel)

class OpenRouterPromptProcessor(PromptProcessor):
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

    def _create_messages(self, prompt: str, user_prompt: str, conversation_history: list[GenericMessage] | None = None) -> list[ChatCompletionMessageParam]:
        """Create messages list from prompt components."""
        messages: list[ChatCompletionMessageParam] = [{"role": "system", "content": prompt.strip()}]

        if conversation_history:
            for msg in conversation_history:
                match msg["role"]:
                    case "user":
                        messages.append(ChatCompletionUserMessageParam(role="user", content=msg["content"]))
                    case "assistant":
                        messages.append(ChatCompletionAssistantMessageParam(role="assistant", content=msg["content"]))
                    case _:
                        pass

        messages.append({
            "role": "user",
            "content": user_prompt.strip(),
        })
        return messages

    def _process_structured(
        self,
        messages: list[ChatCompletionMessageParam],
        output_type: type[T],
        max_tokens: int | None
    ) -> T:
        """Process prompt and return structured Pydantic model."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens or 4096,
            response_format={
                "type": "json_object"
            },
            extra_body={
                "json_schema": output_type.model_json_schema()
            }
        )

        if not response.choices or not response.choices[0].message.content:
            raise ValueError("No response content received from OpenRouter API")

        # Parse the structured output
        try:
            content_text = response.choices[0].message.content
            parsed_json = json.loads(content_text)
            return output_type.model_validate(parsed_json)
        except Exception as e:
            raise ValueError(f"Failed to parse structured response: {e}") from e

    def _process_string(
        self,
        messages: list[ChatCompletionMessageParam],
        max_tokens: int | None
    ) -> str:
        """Process prompt and return string response."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens or 4096
        )

        if not response.choices or not response.choices[0].message.content:
            raise ValueError("No response content received from OpenRouter API")

        return response.choices[0].message.content

    def _process_string_streaming(
        self,
        messages: list[ChatCompletionMessageParam],
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
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


