"""Shared test doubles for VN tests that exercise LLM-driven components."""

from pydantic import BaseModel

from src.models.prompt_processor import PromptProcessor


class FakeProcessor(PromptProcessor):
    """Returns queued model outputs in order; a queued string simulates an unparseable response. No real LLM involved."""

    def __init__(self, outputs: list[BaseModel | str]) -> None:
        self.outputs = list(outputs)
        self.calls: list[type] = []

    def get_processor_specific_prompt(self) -> str:
        return ""

    def respond_with_stream(self, prompt, user_prompt, conversation_history=None, max_tokens=None, reasoning=False):
        raise NotImplementedError

    def respond_with_text(self, prompt, user_prompt, conversation_history=None, max_tokens=None, reasoning=False):
        raise NotImplementedError

    def respond_with_model(self, prompt, user_prompt, output_type, conversation_history=None, max_tokens=None, reasoning=False):
        self.calls.append(output_type)
        output = self.outputs.pop(0)
        if isinstance(output, str):
            raise ValueError(f"no structured output: {output}")
        assert isinstance(output, output_type), f"test setup error: expected {output_type}, queued {type(output)}"
        return output
