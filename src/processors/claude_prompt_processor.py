import os
from typing import Type, TypeVar, Union, overload

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
        output_type: Type[T],
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None
    ) -> T: ...

    def process(
        self,
        prompt: str,
        user_prompt: str,
        output_type: Union[type[str], Type[T]] = str,
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None
    ) -> Union[str, T]:
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
                } # type: ignore
            }],
        })

        system_prompt: ClaudeContent = [{
            "type": "text",
            "text": prompt.strip(),
            "cache_control": {
                "type": "ephemeral",
                "ttl": "1h",
            }
        }]

        # Check if output_type is a Pydantic model
        if (issubclass(output_type, BaseModel) and
            output_type is not BaseModel):
            return self._process_structured(system_prompt, messages, output_type, max_tokens)
        else:
            return self._process_string(system_prompt, messages, max_tokens)

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
