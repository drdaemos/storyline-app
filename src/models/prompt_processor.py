from abc import ABC, abstractmethod
from typing import TypeVar, overload

from pydantic import BaseModel

from src.models.message import GenericMessage

T = TypeVar('T', bound=BaseModel)

class PromptProcessor(ABC):
    @abstractmethod
    def get_processor_specific_prompt(self) -> str:
        pass

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

    @abstractmethod
    def process(
        self,
        prompt: str,
        user_prompt: str,
        output_type: type[str] | type[T] = str,
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None
    ) -> str | T:
        pass