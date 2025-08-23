import os
from typing import Any, TypedDict, TypeVar

import anthropic
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

class Message(TypedDict):
    role: str
    content: str

class ClaudePromptProcessor:
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
            prompt: The system prompt
            user_prompt: The user prompt template with {variable_name} placeholders
            conversation_history: Previous conversation messages
            variables: Dictionary of variables to substitute in the prompt
            output_type: Expected output type (str or Pydantic model class)
            max_tokens: Maximum tokens in response

        Returns:
            Structured Pydantic model instance if output_type is BaseModel subclass,
            otherwise returns string response
        """
        # Render prompt template with variables
        rendered_prompt = self._render_prompt(user_prompt, variables or {})

        # Build messages list
        messages = []
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({
            "role": "user",
            "content": rendered_prompt
        })

        # Check if output_type is a Pydantic model
        if (isinstance(output_type, type) and
            issubclass(output_type, BaseModel) and
            output_type is not BaseModel):
            return self._process_structured(prompt, messages, output_type, max_tokens)
        else:
            return self._process_string(prompt, messages, max_tokens)

    def _render_prompt(self, prompt: str, variables: dict[str, Any]) -> str:
        """Render prompt template with provided variables."""
        try:
            return prompt.format(**variables)
        except KeyError as e:
            missing_var = str(e).strip("'")
            raise ValueError(f"Missing required variable in prompt: {missing_var}") from e

    def _process_structured(
        self,
        system_prompt: str,
        messages: list[Message],
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
        system_prompt: str,
        messages: list[Message],
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
        text_content = []
        for block in response.content:
            if block.type == "text":
                text_content.append(block.text)

        if not text_content:
            raise ValueError("No text content received from Claude API")

        return "".join(text_content)
