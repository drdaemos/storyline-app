"""Tests for PromptProcessorFactory."""

from unittest.mock import patch

import pytest

from src.models.prompt_processor_factory import PromptProcessorFactory
from src.processors.claude_prompt_processor import ClaudePromptProcessor
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

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key"})
    def test_alias_processor_creation(self) -> None:
        """Test that compatibility aliases resolve to canonical processors."""
        processor = PromptProcessorFactory.create_processor("google")
        assert isinstance(processor, OpenRouterPromptProcessor)
        assert processor.model == "google/gemini-3-flash-preview"

    def test_get_available_processor_types(self) -> None:
        """Test that available processor types expose the full canonical model list."""
        assert PromptProcessorFactory.get_available_processor_types() == [
            "claude-opus",
            "claude-sonnet",
            "claude-haiku",
            "gpt-5.2",
            "google-flash",
            "google-pro",
            "deepseek-v32",
            "kimi",
            "kimi-thinking",
            "mistral",
            "grok",
            "glm",
            "cohere",
        ]

    def test_get_available_processor_options(self) -> None:
        """Test that available options include display names aligned with canonical IDs."""
        assert [
            (option.id, option.display_name)
            for option in PromptProcessorFactory.get_available_processor_options()
        ] == [
            ("claude-opus", "Claude Opus 4.5"),
            ("claude-sonnet", "Claude Sonnet 4.5"),
            ("claude-haiku", "Claude Haiku 4.5"),
            ("gpt-5.2", "GPT-5.2 Chat"),
            ("google-flash", "Gemini 3 Flash"),
            ("google-pro", "Gemini 3 Pro"),
            ("deepseek-v32", "DeepSeek V3.2"),
            ("kimi", "Kimi K2"),
            ("kimi-thinking", "Kimi K2 Thinking"),
            ("mistral", "Mistral Small Creative"),
            ("grok", "Grok 4.1 Fast"),
            ("glm", "GLM-4.7"),
            ("cohere", "Cohere Command A"),
        ]

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
