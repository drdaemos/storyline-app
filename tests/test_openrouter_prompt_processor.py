import json
import os
from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel

from src.models.message import GenericMessage
from src.processors.openrouter_prompt_processor import OpenRouterPromptProcessor


class MockResponse(BaseModel):
    name: str
    age: int
    description: str


class TestOpenRouterPromptProcessor:

    @patch.dict(os.environ, {'OPENROUTER_API_KEY': 'test-key'})
    def test_init_with_env_key(self):
        processor = OpenRouterPromptProcessor()
        assert processor.client.api_key == 'test-key'
        assert processor.model == "deepseek/deepseek-chat-v3.1"

    def test_init_with_explicit_key(self):
        processor = OpenRouterPromptProcessor(api_key='explicit-key')
        assert processor.client.api_key == 'explicit-key'

    def test_init_with_custom_model(self):
        processor = OpenRouterPromptProcessor(api_key='test-key', model='anthropic/claude-3-sonnet')
        assert processor.model == 'anthropic/claude-3-sonnet'

    @patch('src.processors.openrouter_prompt_processor.OpenAI')
    def test_respond_with_text_output(self, mock_openai):
        mock_choice = Mock()
        mock_choice.message.content = "This is a test response"
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_openai.return_value.chat.completions.create.return_value = mock_response

        processor = OpenRouterPromptProcessor(api_key='test-key')
        processor.set_logger(Mock())
        result = processor.respond_with_text("System prompt", "Test prompt")

        assert result == "This is a test response"
        mock_openai.return_value.chat.completions.create.assert_called_once()

    @patch('src.processors.openrouter_prompt_processor.OpenAI')
    def test_respond_with_model_output(self, mock_openai):
        # Create mock parsed response
        mock_parsed = MockResponse(name="John", age=30, description="Test person")
        mock_choice = Mock()
        mock_choice.message.parsed = mock_parsed
        mock_choice.message.content = json.dumps({"name": "John", "age": 30, "description": "Test person"})
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_openai.return_value.chat.completions.parse.return_value = mock_response

        processor = OpenRouterPromptProcessor(api_key='test-key')
        result = processor.respond_with_model("System prompt", "Test prompt", MockResponse)

        assert result == mock_parsed
        assert result.name == "John"
        assert result.age == 30
        assert result.description == "Test person"

    @patch('src.processors.openrouter_prompt_processor.OpenAI')
    def test_respond_with_text_empty_response(self, mock_openai):
        mock_response = Mock()
        mock_response.choices = []
        mock_openai.return_value.chat.completions.create.return_value = mock_response

        processor = OpenRouterPromptProcessor(api_key='test-key')

        with pytest.raises(ValueError, match="No response content received from OpenRouter API"):
            processor.respond_with_text("System prompt", "Test prompt")

    @patch('src.processors.openrouter_prompt_processor.OpenAI')
    def test_respond_with_model_failed_parsing(self, mock_openai):
        mock_choice = Mock()
        mock_choice.message.parsed = None
        mock_choice.message.content = "invalid json"
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_openai.return_value.chat.completions.parse.return_value = mock_response

        processor = OpenRouterPromptProcessor(api_key='test-key')

        with pytest.raises(ValueError, match="Failed to parse structured response"):
            processor.respond_with_model("System prompt", "Test prompt", MockResponse)

    @patch('src.processors.openrouter_prompt_processor.OpenAI')
    def test_respond_with_text_custom_parameters(self, mock_openai):
        mock_choice = Mock()
        mock_choice.message.content = "Custom response"
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_openai.return_value.chat.completions.create.return_value = mock_response

        processor = OpenRouterPromptProcessor(api_key='test-key')
        processor.set_logger(Mock())
        processor.respond_with_text("System prompt", "Test prompt", max_tokens=100)

        call_args = mock_openai.return_value.chat.completions.create.call_args
        assert call_args[1]['max_tokens'] == 100

    @patch('src.processors.openrouter_prompt_processor.OpenAI')
    def test_respond_with_text_conversation_history(self, mock_openai):
        mock_choice = Mock()
        mock_choice.message.content = "Response with history"
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_openai.return_value.chat.completions.create.return_value = mock_response

        processor = OpenRouterPromptProcessor(api_key='test-key')
        processor.set_logger(Mock())
        conversation_history: list[GenericMessage] = [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"}
        ]

        result = processor.respond_with_text("System prompt", "Current prompt", conversation_history=conversation_history)

        assert result == "Response with history"

        # Check that conversation history was included in the messages
        call_args = mock_openai.return_value.chat.completions.create.call_args
        messages = call_args[1]['messages']

        assert len(messages) == 4  # 1 system + 2 history + 1 current
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "System prompt"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Previous message"
        assert messages[2]["role"] == "assistant"
        assert messages[2]["content"] == "Previous response"
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "Current prompt"

    @patch('src.processors.openrouter_prompt_processor.OpenAI')
    def test_respond_with_stream(self, mock_openai):
        # Mock the streaming response chunks
        chunk1 = Mock()
        chunk1.choices = [Mock()]
        chunk1.choices[0].delta = Mock()
        chunk1.choices[0].delta.content = "Hello "

        chunk2 = Mock()
        chunk2.choices = [Mock()]
        chunk2.choices[0].delta = Mock()
        chunk2.choices[0].delta.content = "world"

        chunk3 = Mock()
        chunk3.choices = [Mock()]
        chunk3.choices[0].delta = Mock()
        chunk3.choices[0].delta.content = "!"

        mock_openai.return_value.chat.completions.create.return_value = iter([chunk1, chunk2, chunk3])

        processor = OpenRouterPromptProcessor(api_key='test-key')
        result = list(processor.respond_with_stream("System prompt", "Test prompt"))

        assert result == ["Hello ", "world", "!"]
        mock_openai.return_value.chat.completions.create.assert_called_once()

    @patch('src.processors.openrouter_prompt_processor.OpenAI')
    def test_respond_with_model_custom_parameters(self, mock_openai):
        mock_parsed = MockResponse(name="John", age=30, description="Test person")
        mock_choice = Mock()
        mock_choice.message.parsed = mock_parsed
        mock_choice.message.content = json.dumps({"name": "John", "age": 30, "description": "Test person"})
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_openai.return_value.chat.completions.parse.return_value = mock_response

        processor = OpenRouterPromptProcessor(api_key='test-key')
        processor.respond_with_model("System prompt", "Test prompt", MockResponse, max_tokens=100)

        call_args = mock_openai.return_value.chat.completions.parse.call_args
        assert call_args[1]['max_tokens'] == 100

    @patch('src.processors.openrouter_prompt_processor.OpenAI')
    def test_respond_with_model_conversation_history(self, mock_openai):
        mock_parsed = MockResponse(name="John", age=30, description="Test person")
        mock_choice = Mock()
        mock_choice.message.parsed = mock_parsed
        mock_choice.message.content = json.dumps({"name": "John", "age": 30, "description": "Test person"})
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_openai.return_value.chat.completions.parse.return_value = mock_response

        processor = OpenRouterPromptProcessor(api_key='test-key')
        conversation_history: list[GenericMessage] = [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"}
        ]

        result = processor.respond_with_model("System prompt", "Current prompt", MockResponse, conversation_history=conversation_history)

        assert result == mock_parsed
        assert result.name == "John"

        # Check that conversation history was included in the messages
        call_args = mock_openai.return_value.chat.completions.parse.call_args
        messages = call_args[1]['messages']

        assert len(messages) == 4  # 1 system + 2 history + 1 current
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "System prompt"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Previous message"
        assert messages[2]["role"] == "assistant"
        assert messages[2]["content"] == "Previous response"
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "Current prompt"

    def test_get_processor_specific_prompt(self):
        processor = OpenRouterPromptProcessor(api_key='test-key')
        prompt = processor.get_processor_specific_prompt()

        # Don't test for specific text as prompts get rephrased often
        assert isinstance(prompt, str)
        assert len(prompt) > 0
