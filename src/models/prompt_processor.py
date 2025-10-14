from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import TypeVar

from pydantic import BaseModel

from src.models.message import GenericMessage

T = TypeVar("T", bound=BaseModel)


class PromptProcessor(ABC):
    @abstractmethod
    def get_processor_specific_prompt(self) -> str:
        pass

    @abstractmethod
    def respond_with_stream(
        self,
        prompt: str,
        user_prompt: str,
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None,
        reasoning: bool = False,
    ) -> Iterator[str]:
        pass

    @abstractmethod
    def respond_with_model(
        self,
        prompt: str,
        user_prompt: str,
        output_type: type[T],
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None,
        reasoning: bool = False,
    ) -> T:
        pass

    @abstractmethod
    def respond_with_text(
        self,
        prompt: str,
        user_prompt: str,
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None,
        reasoning: bool = False,
    ) -> str:
        pass
