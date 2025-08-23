import os
from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel

from src.prompt_processor import Message, PromptProcessor


class MockResponse(BaseModel):
    name: str
    age: int
    description: str


class TestPromptProcessor:

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'})
    def test_init_with_env_key(self):
        processor = PromptProcessor()
        assert processor.client.api_key == 'test-key'
        assert processor.model == "gpt-5"

    def test_init_with_explicit_key(self):
        processor = PromptProcessor(api_key='explicit-key')
        assert processor.client.api_key == 'explicit-key'

    def test_init_with_custom_model(self):
        processor = PromptProcessor(api_key='test-key', model='gpt-4')
        assert processor.model == 'gpt-4'

    def test_render_prompt_with_variables(self):
        processor = PromptProcessor(api_key='test-key')
        prompt = "Hello {name}, you are {age} years old."
        variables = {"name": "Alice", "age": 25}

        result = processor._render_prompt(prompt, variables)
        assert result == "Hello Alice, you are 25 years old."

    def test_render_prompt_missing_variable(self):
        processor = PromptProcessor(api_key='test-key')
        prompt = "Hello {name}, you are {age} years old."
        variables = {"name": "Alice"}

        with pytest.raises(ValueError, match="Missing required variable in prompt: age"):
            processor._render_prompt(prompt, variables)

    def test_render_prompt_no_variables(self):
        processor = PromptProcessor(api_key='test-key')
        prompt = "This is a simple prompt without variables."

        result = processor._render_prompt(prompt, {})
        assert result == "This is a simple prompt without variables."

    @patch('src.prompt_processor.OpenAI')
    def test_process_string_output(self, mock_openai):
        mock_response = Mock()
        mock_response.output_text = "This is a test response"
        mock_openai.return_value.responses.create.return_value = mock_response

        processor = PromptProcessor(api_key='test-key')
        result = processor.process("System prompt", "Test prompt", output_type=str)

        assert result == "This is a test response"
        mock_openai.return_value.responses.create.assert_called_once()

    @patch('src.prompt_processor.OpenAI')
    def test_process_structured_output(self, mock_openai):
        mock_parsed_response = MockResponse(name="John", age=30, description="Test person")
        mock_response = Mock()
        mock_response.output_parsed = mock_parsed_response
        mock_openai.return_value.responses.parse.return_value = mock_response

        processor = PromptProcessor(api_key='test-key')
        result = processor.process("System prompt", "Test prompt", output_type=MockResponse)

        assert isinstance(result, MockResponse)
        assert result.name == "John"
        assert result.age == 30
        assert result.description == "Test person"
        mock_openai.return_value.responses.parse.assert_called_once()

    @patch('src.prompt_processor.OpenAI')
    def test_process_with_variables_and_string_output(self, mock_openai):
        mock_response = Mock()
        mock_response.output_text = "Hello Alice, you are 25 years old!"
        mock_openai.return_value.responses.create.return_value = mock_response

        processor = PromptProcessor(api_key='test-key')
        prompt = "Generate a greeting for {name} who is {age} years old"
        variables = {"name": "Alice", "age": 25}

        result = processor.process("System prompt", prompt, variables=variables, output_type=str)

        assert result == "Hello Alice, you are 25 years old!"

    @patch('src.prompt_processor.OpenAI')
    def test_process_string_empty_response(self, mock_openai):
        mock_response = Mock()
        mock_response.output_text = None
        mock_openai.return_value.responses.create.return_value = mock_response

        processor = PromptProcessor(api_key='test-key')

        with pytest.raises(ValueError, match="Received response from OpenAI API"):
            processor.process("System prompt", "Test prompt", output_type=str)

    @patch('src.prompt_processor.OpenAI')
    def test_process_structured_failed_parsing(self, mock_openai):
        mock_response = Mock()
        mock_response.output_parsed = None
        mock_openai.return_value.responses.parse.return_value = mock_response

        processor = PromptProcessor(api_key='test-key')

        with pytest.raises(ValueError, match="Failed to parse structured response from OpenAI API"):
            processor.process("System prompt", "Test prompt", output_type=MockResponse)

    @patch('src.prompt_processor.OpenAI')
    def test_process_with_custom_parameters(self, mock_openai):
        mock_response = Mock()
        mock_response.output_text = "Custom response"
        mock_openai.return_value.responses.create.return_value = mock_response

        processor = PromptProcessor(api_key='test-key')
        processor.process("System prompt", "Test prompt", max_tokens=100)

        call_args = mock_openai.return_value.responses.create.call_args
        assert call_args[1]['max_output_tokens'] == 100

    @patch('src.prompt_processor.OpenAI')
    def test_process_with_conversation_history(self, mock_openai):
        mock_response = Mock()
        mock_response.output_text = "Response with history"
        mock_openai.return_value.responses.create.return_value = mock_response

        processor = PromptProcessor(api_key='test-key')
        conversation_history: list[Message] = [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"}
        ]

        result = processor.process("System prompt", "Current prompt", conversation_history=conversation_history)

        assert result == "Response with history"

        # Check that conversation history was included in the input
        call_args = mock_openai.return_value.responses.create.call_args
        input_messages = call_args[1]['input']

        assert len(input_messages) == 4  # 1 system + 2 history + 1 current
        assert input_messages[0]["role"] == "developer"
        assert input_messages[0]["content"] == "System prompt"
        assert input_messages[1]["role"] == "user"
        assert input_messages[1]["content"] == "Previous message"
        assert input_messages[2]["role"] == "assistant"
        assert input_messages[2]["content"] == "Previous response"
        assert input_messages[3]["role"] == "user"
        assert input_messages[3]["content"] == "Current prompt"
