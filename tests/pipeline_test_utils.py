from collections import deque
from collections.abc import Iterator

from src.models.message import GenericMessage
from src.models.prompt_processor import PromptProcessor


class FakePromptProcessor(PromptProcessor):
    """Configurable prompt processor test double for pipeline step tests."""

    def __init__(self) -> None:
        self.model_responses: deque = deque()
        self.stream_responses: deque[list[str]] = deque()
        self.raise_on_model: Exception | None = None
        self.raise_on_stream: Exception | None = None
        self.last_prompt: str = ""
        self.last_user_prompt: str = ""

    def get_processor_specific_prompt(self) -> str:
        return "test-processor"

    def respond_with_model(
        self,
        prompt: str,
        user_prompt: str,
        output_type: type,
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None,
        reasoning: bool = False,
    ):  # noqa: ANN201
        self.last_prompt = prompt
        self.last_user_prompt = user_prompt
        if self.raise_on_model is not None:
            raise self.raise_on_model
        response = self.model_responses.popleft()
        if isinstance(response, output_type):
            return response
        return output_type.model_validate(response)

    def respond_with_stream(
        self,
        prompt: str,
        user_prompt: str,
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None,
        reasoning: bool = False,
    ) -> Iterator[str]:
        self.last_prompt = prompt
        self.last_user_prompt = user_prompt
        if self.raise_on_stream is not None:
            raise self.raise_on_stream
        chunks = self.stream_responses.popleft() if self.stream_responses else []
        yield from chunks

    def respond_with_text(
        self,
        prompt: str,
        user_prompt: str,
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None,
        reasoning: bool = False,
    ) -> str:
        self.last_prompt = prompt
        self.last_user_prompt = user_prompt
        if self.raise_on_model is not None:
            raise self.raise_on_model
        response = self.model_responses.popleft()
        return str(response)
