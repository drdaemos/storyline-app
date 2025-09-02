import os
from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel

from src.processors.claude_prompt_processor import ClaudePromptProcessor
from src.models.message import GenericMessage


class MockResponse(BaseModel):
    name: str
    age: int
    description: str


class TestClaudePromptProcessor:

    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'})
    def test_init_with_env_key(self):
        processor = ClaudePromptProcessor()
        assert processor.client.api_key == 'test-key'
        assert processor.model == "claude-sonnet-4-20250514"

    def test_init_with_explicit_key(self):
        processor = ClaudePromptProcessor(api_key='explicit-key')
        assert processor.client.api_key == 'explicit-key'

    def test_init_with_custom_model(self):
        processor = ClaudePromptProcessor(api_key='test-key', model='claude-3-haiku-20240307')
        assert processor.model == 'claude-3-haiku-20240307'

    @patch('src.processors.claude_prompt_processor.anthropic.Anthropic')
    def test_process_string_output(self, mock_anthropic):
        # Mock the response
        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "This is a test response"

        mock_response = Mock()
        mock_response.content = [mock_text_block]
        mock_anthropic.return_value.messages.create.return_value = mock_response

        processor = ClaudePromptProcessor(api_key='test-key')
        result = processor.process("Test system prompt", "Test user prompt", output_type=str)

        assert result == "This is a test response"
        mock_anthropic.return_value.messages.create.assert_called_once()

    @patch('src.processors.claude_prompt_processor.anthropic.Anthropic')
    def test_process_structured_output(self, mock_anthropic):
        # Mock the response with tool use
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.input = {"name": "John", "age": 30, "description": "Test person"}

        mock_response = Mock()
        mock_response.content = [mock_tool_block]
        mock_anthropic.return_value.messages.create.return_value = mock_response

        processor = ClaudePromptProcessor(api_key='test-key')
        result = processor.process("Test system prompt", "Test user prompt", output_type=MockResponse)

        assert isinstance(result, MockResponse)
        assert result.name == "John"
        assert result.age == 30
        assert result.description == "Test person"
        mock_anthropic.return_value.messages.create.assert_called_once()

    @patch('src.processors.claude_prompt_processor.anthropic.Anthropic')
    def test_process_with_substituted_string_output(self, mock_anthropic):
        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "Hello Alice, you are 25 years old!"

        mock_response = Mock()
        mock_response.content = [mock_text_block]
        mock_anthropic.return_value.messages.create.return_value = mock_response

        processor = ClaudePromptProcessor(api_key='test-key')
        system_prompt = "You are a helpful assistant"
        user_prompt = "Generate a greeting for Alice who is 25 years old"

        result = processor.process(system_prompt, user_prompt, output_type=str)

        assert result == "Hello Alice, you are 25 years old!"

    @patch('src.processors.claude_prompt_processor.anthropic.Anthropic')
    def test_process_string_empty_response(self, mock_anthropic):
        mock_response = Mock()
        mock_response.content = []
        mock_anthropic.return_value.messages.create.return_value = mock_response

        processor = ClaudePromptProcessor(api_key='test-key')

        with pytest.raises(ValueError, match="No response content received from Claude API"):
            processor.process("Test system prompt", "Test user prompt", output_type=str)

    @patch('src.processors.claude_prompt_processor.anthropic.Anthropic')
    def test_process_string_no_text_content(self, mock_anthropic):
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"

        mock_response = Mock()
        mock_response.content = [mock_tool_block]
        mock_anthropic.return_value.messages.create.return_value = mock_response

        processor = ClaudePromptProcessor(api_key='test-key')

        with pytest.raises(ValueError, match="No text content received from Claude API"):
            processor.process("Test system prompt", "Test user prompt", output_type=str)

    @patch('src.processors.claude_prompt_processor.anthropic.Anthropic')
    def test_process_structured_no_tool_use(self, mock_anthropic):
        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "Some text"

        mock_response = Mock()
        mock_response.content = [mock_text_block]
        mock_anthropic.return_value.messages.create.return_value = mock_response

        processor = ClaudePromptProcessor(api_key='test-key')

        with pytest.raises(ValueError, match="No structured output received from Claude API"):
            processor.process("Test system prompt", "Test user prompt", output_type=MockResponse)

    @patch('src.processors.claude_prompt_processor.anthropic.Anthropic')
    def test_process_structured_invalid_data(self, mock_anthropic):
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.input = {"invalid": "data"}  # Missing required fields

        mock_response = Mock()
        mock_response.content = [mock_tool_block]
        mock_anthropic.return_value.messages.create.return_value = mock_response

        processor = ClaudePromptProcessor(api_key='test-key')

        with pytest.raises(ValueError, match="Failed to parse structured response"):
            processor.process("Test system prompt", "Test user prompt", output_type=MockResponse)

    @patch('src.processors.claude_prompt_processor.anthropic.Anthropic')
    def test_process_with_custom_parameters(self, mock_anthropic):
        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "Custom response"

        mock_response = Mock()
        mock_response.content = [mock_text_block]
        mock_anthropic.return_value.messages.create.return_value = mock_response

        processor = ClaudePromptProcessor(api_key='test-key')
        processor.process("Test system prompt", "Test user prompt", max_tokens=100)

        call_args = mock_anthropic.return_value.messages.create.call_args
        assert call_args[1]['max_tokens'] == 100

    @patch('src.processors.claude_prompt_processor.anthropic.Anthropic')
    def test_process_with_conversation_history(self, mock_anthropic):
        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "Response with history"

        mock_response = Mock()
        mock_response.content = [mock_text_block]
        mock_anthropic.return_value.messages.create.return_value = mock_response

        processor = ClaudePromptProcessor(api_key='test-key')
        conversation_history: list[GenericMessage] = [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"}
        ]

        result = processor.process("System prompt", "Current prompt", conversation_history=conversation_history)

        assert result == "Response with history"

        # Check that conversation history was included in the messages
        call_args = mock_anthropic.return_value.messages.create.call_args
        messages = call_args[1]['messages']

        assert len(messages) == 3  # 2 history + 1 current
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Previous message"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Previous response"
        assert messages[2]["role"] == "user"
        assert messages[2]["content"] == [{
            "type": "text",
            "text": "Current prompt",
            "cache_control": {
                "type": "ephemeral",
            }
        }]

    @patch('src.processors.claude_prompt_processor.anthropic.Anthropic')
    def test_process_multiple_text_blocks(self, mock_anthropic):
        # Mock response with multiple text blocks
        mock_text_block1 = Mock()
        mock_text_block1.type = "text"
        mock_text_block1.text = "First part "

        mock_text_block2 = Mock()
        mock_text_block2.type = "text"
        mock_text_block2.text = "second part"

        mock_response = Mock()
        mock_response.content = [mock_text_block1, mock_text_block2]
        mock_anthropic.return_value.messages.create.return_value = mock_response

        processor = ClaudePromptProcessor(api_key='test-key')
        result = processor.process("Test system prompt", "Test user prompt", output_type=str)

        assert result == "First part second part"
