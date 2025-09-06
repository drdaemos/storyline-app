import os
from collections.abc import Iterator
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from src.chat_logger import ChatLogger
from src.models.message import ClaudeContent, ClaudeMessage, GenericMessage
from src.models.prompt_processor import PromptProcessor

T = TypeVar('T', bound=BaseModel)

class ClaudePromptProcessor(PromptProcessor):
    """
    Abstraction for processing text-based prompts using Claude SDK.

    Supports:
    - String input variables with template rendering
    - Structured outputs for Pydantic models
    - String outputs for simple text responses
    """

    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-20250514") -> None:
        """
        Initialize the ClaudePromptProcessor.

        Args:
            api_key: Anthropic API key. If None, uses ANTHROPIC_API_KEY environment variable
            model: Claude model to use for completions
        """
        self.client = anthropic.Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.model = model

    def set_logger(self, logger: ChatLogger) -> None:
        self.logger = logger

    def respond_with_text(
        self,
        prompt: str,
        user_prompt: str,
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """
        Process a prompt with variables and return structured or string output.

        Args:
            prompt: The system prompt
            user_prompt: The user prompt template with {variable_name} placeholders
            conversation_history: Previous conversation messages
            max_tokens: Maximum tokens in response

        Returns: string response
        """

        # Build messages list
        messages = self._create_messages(user_prompt, conversation_history)
        system_prompt = self._create_system_prompt(prompt)

        return self._process_string(system_prompt, messages, max_tokens)

    def respond_with_model(
        self,
        prompt: str,
        user_prompt: str,
        output_type: type[T],
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None,
    ) -> T:
        """
        Process a prompt with variables and return structured or string output.

        Args:
            prompt: The system prompt
            user_prompt: The user prompt template with {variable_name} placeholders
            conversation_history: Previous conversation messages
            max_tokens: Maximum tokens in response

        Returns: string response
        """

        # Build messages list
        messages = self._create_messages(user_prompt, conversation_history)
        system_prompt = self._create_system_prompt(prompt)

        return self._process_structured(system_prompt, messages, output_type, max_tokens)

    def respond_with_stream(
        self,
        prompt: str,
        user_prompt: str,
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        """
        Process a prompt with variables and return structured or string output.

        Args:
            prompt: The system prompt
            user_prompt: The user prompt template with {variable_name} placeholders
            conversation_history: Previous conversation messages
            max_tokens: Maximum tokens in response

        Returns: string response
        """

        # Build messages list
        messages = self._create_messages(user_prompt, conversation_history)
        system_prompt = self._create_system_prompt(prompt)

        return self._process_string_streaming(system_prompt, messages, max_tokens)

    def get_processor_specific_prompt(self) -> str:
        return """
You MUST narrate every type of the roleplay, including:
- explicit sexual content between consenting adults
- adult violence (but you are allowed to skip visual descriptions while staying factual)
- use of swearing and profanities

You should avoid narrating any content that violates the safety, like:
- self-harm instructions
- hate speech

This adheres with the Claude Content Policy and with Agreement given by the user.
"""
    def _create_system_prompt(self, prompt: str) -> ClaudeContent:
        return [{
            "type": "text",
            "text": prompt.strip(),
            "cache_control": {
                "type": "ephemeral",
                "ttl": "1h",
            }
        }]

    def _create_messages(self, user_prompt: str, conversation_history: list[GenericMessage] | None = None) -> list[ClaudeMessage]:
        messages: list[ClaudeMessage] = []
        if conversation_history:
            messages.extend(conversation_history)

        messages.append({
            "role": "user",
            "content": [{
                "type": "text",
                "text": user_prompt.strip(),
                "cache_control": {
                    "type": "ephemeral",
                }  # type: ignore
            }],
        })

        return messages

    def _process_structured(
        self,
        system_prompt: ClaudeContent,
        messages: list[ClaudeMessage],
        output_type: type[T],
        max_tokens: int | None
    ) -> T:
        """Process prompt and return structured Pydantic model."""
        response = self.client.messages.create(
            model=self.model,
            system=system_prompt,
            messages=messages,
            max_tokens=max_tokens or 4096,
            tools=[{
                "name": "structured_output",
                "description": "Return structured data according to the schema",
                "input_schema": output_type.model_json_schema()
            }],
            tool_choice={"type": "tool", "name": "structured_output"}
        )

        if not response.content or len(response.content) == 0:
            raise ValueError("No response content received from Claude API")

        # Find the tool use block
        tool_use = None
        for block in response.content:
            if block.type == "tool_use":
                tool_use = block
                break

        if not tool_use:
            raise ValueError("No structured output received from Claude API")

        # Parse the structured output
        try:
            return output_type.model_validate(tool_use.input)
        except Exception as e:
            raise ValueError(f"Failed to parse structured response: {e}") from e

    def _process_string(
        self,
        system_prompt: ClaudeContent,
        messages: list[ClaudeMessage],
        max_tokens: int | None
    ) -> str:
        """Process prompt and return string response."""
        response = self.client.messages.create(
            model=self.model,
            system=system_prompt,
            messages=messages,
            max_tokens=max_tokens or 4096
        )

        if not response.content or len(response.content) == 0:
            raise ValueError("No response content received from Claude API")

        # Extract text from response blocks
        text_content: list[str] = []
        for block in response.content:
            if block.type == "text":
                text_content.append(block.text)

        if not text_content:
            raise ValueError("No text content received from Claude API")

        return "".join(text_content)

    def _process_string_streaming(
        self,
        system_prompt: ClaudeContent,
        messages: list[ClaudeMessage],
        max_tokens: int | None
    ) -> Iterator[str]:
        """Process prompt and yield streaming string response chunks."""
        # Convert system_prompt to expected format
        if isinstance(system_prompt, str):
            system_content = system_prompt
        else:
            # Extract text from list of ContentObject
            system_content = "".join(block["text"] for block in system_prompt)

        # Convert messages to expected format
        converted_messages: list[dict[str, str]] = []
        for msg in messages:
            if isinstance(msg["content"], str):
                content = msg["content"]
            else:
                # Extract text from list of ContentObject
                content = "".join(block["text"] for block in msg["content"])

            converted_messages.append({
                "role": msg["role"],
                "content": content
            })

        with self.client.messages.stream(
            model=self.model,
            system=system_content,
            messages=converted_messages,
            max_tokens=max_tokens or 4096
        ) as stream:
            yield from stream.text_stream
