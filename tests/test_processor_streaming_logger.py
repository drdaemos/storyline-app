"""Streaming must work on a freshly constructed processor (no ChatLogger attached).

Regression: the VN pipeline streams without calling set_logger; reading self.logger
after the stream used to raise AttributeError. SDK clients are fully mocked.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from src.processors.claude_prompt_processor import ClaudePromptProcessor
from src.processors.openrouter_prompt_processor import OpenRouterPromptProcessor


def _openrouter_chunk(content: str | None, reasoning: str | None) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=content, reasoning=reasoning))])


class TestStreamingWithoutLogger:
    def test_openrouter_stream_with_reasoning_and_no_logger(self) -> None:
        processor = OpenRouterPromptProcessor(api_key="test-key")
        processor.client = MagicMock()
        processor.client.chat.completions.create.return_value = iter(
            [
                _openrouter_chunk(None, "thinking..."),
                _openrouter_chunk("Hello ", None),
                _openrouter_chunk("world", None),
            ]
        )

        chunks = list(processor.respond_with_stream(prompt="system", user_prompt="user"))

        assert "".join(chunks) == "Hello world"

    def test_claude_stream_with_thinking_and_no_logger(self) -> None:
        processor = ClaudePromptProcessor(api_key="test-key")
        stream = MagicMock()
        stream.__enter__ = MagicMock(
            return_value=iter(
                [
                    SimpleNamespace(type="thinking", thinking="hm"),
                    SimpleNamespace(type="text", text="Hello"),
                ]
            )
        )
        stream.__exit__ = MagicMock(return_value=False)
        processor.client = MagicMock()
        processor.client.messages.stream.return_value = stream

        chunks = list(processor.respond_with_stream(prompt="system", user_prompt="user"))

        assert "".join(chunks) == "Hello"

    def test_logger_used_when_attached(self) -> None:
        processor = OpenRouterPromptProcessor(api_key="test-key")
        processor.client = MagicMock()
        processor.client.chat.completions.create.return_value = iter([_openrouter_chunk("text", "a thought")])
        logger = MagicMock()
        processor.set_logger(logger)

        list(processor.respond_with_stream(prompt="system", user_prompt="user"))

        logger.log_message.assert_called_once()
