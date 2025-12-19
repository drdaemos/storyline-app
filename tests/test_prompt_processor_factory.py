"""Tests for PromptProcessorFactory."""

from unittest.mock import patch

import pytest

from src.models.prompt_processor_factory import PromptProcessorFactory
from src.processors.claude_prompt_processor import ClaudePromptProcessor
from src.processors.cohere_prompt_processor import CoherePromptProcessor
from src.processors.openai_prompt_processor import OpenAiPromptProcessor
from src.processors.openrouter_prompt_processor import OpenRouterPromptProcessor


class TestPromptProcessorFactory:
    """Test cases for PromptProcessorFactory."""

    def test_create_claude_sonnet_processor(self) -> None:
        """Test creating Claude Sonnet processor."""
        processor = PromptProcessorFactory.create_processor("claude-sonnet")
        assert isinstance(processor, ClaudePromptProcessor)
        assert processor.model == "claude-sonnet-4-5"

    def test_create_claude_haiku_processor(self) -> None:
        """Test creating Claude Haiku processor."""
        processor = PromptProcessorFactory.create_processor("claude-haiku")
        assert isinstance(processor, ClaudePromptProcessor)
        assert processor.model == "claude-haiku-4-5"

    def test_case_insensitive_processor_creation(self) -> None:
        """Test that processor creation is case insensitive."""
        processor_lower = PromptProcessorFactory.create_processor("claude-sonnet")
        processor_upper = PromptProcessorFactory.create_processor("CLAUDE-SONNET")
        processor_mixed = PromptProcessorFactory.create_processor("Claude-Sonnet")

        assert isinstance(processor_lower, type(processor_upper)) and isinstance(processor_lower, type(processor_mixed))

    def test_unsupported_processor_type_raises_error(self) -> None:
        """Test that unsupported processor types raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported processor type: unknown"):
            PromptProcessorFactory.create_processor("unknown")

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"})
    def test_get_default_backup_processor(self) -> None:
        """Test getting default backup processor."""
        processor = PromptProcessorFactory.get_default_backup_processor()
        assert isinstance(processor, OpenRouterPromptProcessor)
        assert processor.model == "deepseek/deepseek-v3.2"
