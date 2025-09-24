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

    def test_create_claude_processor(self) -> None:
        """Test creating Claude processor."""
        processor = PromptProcessorFactory.create_processor("claude")
        assert isinstance(processor, ClaudePromptProcessor)

    @patch.dict('os.environ', {'CO_API_KEY': 'test_key'})
    def test_create_cohere_processor(self) -> None:
        """Test creating Cohere processor."""
        processor = PromptProcessorFactory.create_processor("cohere")
        assert isinstance(processor, CoherePromptProcessor)

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'})
    def test_create_gpt_processor(self) -> None:
        """Test creating GPT processor."""
        processor = PromptProcessorFactory.create_processor("gpt")
        assert isinstance(processor, OpenAiPromptProcessor)

    @patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test_key'})
    def test_create_grok_processor(self) -> None:
        """Test creating Grok processor."""
        processor = PromptProcessorFactory.create_processor("grok")
        assert isinstance(processor, OpenRouterPromptProcessor)
        assert processor.model == "x-ai/grok-4-fast:free"

    @patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test_key'})
    def test_create_deepseek_processor(self) -> None:
        """Test creating DeepSeek processor."""
        processor = PromptProcessorFactory.create_processor("deepseek")
        assert isinstance(processor, OpenRouterPromptProcessor)
        assert processor.model == "deepseek/deepseek-v3.1-terminus"

    @patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test_key'})
    def test_create_google_processor(self) -> None:
        """Test creating Google processor."""
        processor = PromptProcessorFactory.create_processor("google")
        assert isinstance(processor, OpenRouterPromptProcessor)
        assert processor.model == "google/gemini-2.5-flash"

    def test_case_insensitive_processor_creation(self) -> None:
        """Test that processor creation is case insensitive."""
        processor_lower = PromptProcessorFactory.create_processor("claude")
        processor_upper = PromptProcessorFactory.create_processor("CLAUDE")
        processor_mixed = PromptProcessorFactory.create_processor("Claude")

        assert isinstance(processor_lower, type(processor_upper)) and isinstance(processor_lower, type(processor_mixed))

    def test_unsupported_processor_type_raises_error(self) -> None:
        """Test that unsupported processor types raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported processor type: unknown"):
            PromptProcessorFactory.create_processor("unknown")

    @patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test_key'})
    def test_get_default_backup_processor(self) -> None:
        """Test getting default backup processor."""
        processor = PromptProcessorFactory.get_default_backup_processor()
        assert isinstance(processor, OpenRouterPromptProcessor)
        assert processor.model == "deepseek/deepseek-chat-v3.1:free"

    def test_get_available_processor_types(self) -> None:
        """Test getting list of available processor types."""
        types = PromptProcessorFactory.get_available_processor_types()
        expected_types = ["cohere", "claude", "gpt", "grok", "deepseek", "gpt-oss", "google"]
        assert types == expected_types

    @patch.dict('os.environ', {
        'OPENROUTER_API_KEY': 'test_key',
        'CO_API_KEY': 'test_key',
        'OPENAI_API_KEY': 'test_key'
    })
    def test_all_listed_types_can_be_created(self) -> None:
        """Test that all listed processor types can actually be created."""
        types = PromptProcessorFactory.get_available_processor_types()
        for processor_type in types:
            processor = PromptProcessorFactory.create_processor(processor_type)
            assert processor is not None
