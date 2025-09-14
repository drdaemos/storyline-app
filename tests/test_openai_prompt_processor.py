import os
from unittest.mock import Mock, patch

import pytest
from openai.types.responses.response_text_delta_event import ResponseTextDeltaEvent
from pydantic import BaseModel

from src.models.message import GenericMessage
from src.processors.openai_prompt_processor import OpenAiPromptProcessor


class MockResponse(BaseModel):
    name: str
    age: int
    description: str


class TestOpenAiPromptProcessor:

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'})
    def test_init_with_env_key(self):
        processor = OpenAiPromptProcessor()
        assert processor.client.api_key == 'test-key'
        assert processor.model == "gpt-5"

    def test_init_with_explicit_key(self):
        processor = OpenAiPromptProcessor(api_key='explicit-key')
        assert processor.client.api_key == 'explicit-key'

    def test_init_with_custom_model(self):
        processor = OpenAiPromptProcessor(api_key='test-key', model='gpt-4')
        assert processor.model == 'gpt-4'

    @patch('src.processors.openai_prompt_processor.OpenAI')
    def test_respond_with_text_output(self, mock_openai):
        mock_response = Mock()
        mock_response.output_text = "This is a test response"
        mock_openai.return_value.responses.create.return_value = mock_response

        processor = OpenAiPromptProcessor(api_key='test-key')
        result = processor.respond_with_text("System prompt", "Test prompt")

        assert result == "This is a test response"
        mock_openai.return_value.responses.create.assert_called_once()

    @patch('src.processors.openai_prompt_processor.OpenAI')
    def test_respond_with_model_output(self, mock_openai):
        mock_parsed_response = MockResponse(name="John", age=30, description="Test person")
        mock_response = Mock()
        mock_response.output_parsed = mock_parsed_response
        mock_openai.return_value.responses.parse.return_value = mock_response

        processor = OpenAiPromptProcessor(api_key='test-key')
        result = processor.respond_with_model("System prompt", "Test prompt", MockResponse)

        assert isinstance(result, MockResponse)
        assert result.name == "John"
        assert result.age == 30
        assert result.description == "Test person"
        mock_openai.return_value.responses.parse.assert_called_once()

    @patch('src.processors.openai_prompt_processor.OpenAI')
    def test_respond_with_text_with_substituted_string_output(self, mock_openai):
        mock_response = Mock()
        mock_response.output_text = "Hello Alice, you are 25 years old!"
        mock_openai.return_value.responses.create.return_value = mock_response

        processor = OpenAiPromptProcessor(api_key='test-key')
        prompt = "Generate a greeting for Alice who is 25 years old"

        result = processor.respond_with_text("System prompt", prompt)

        assert result == "Hello Alice, you are 25 years old!"

    @patch('src.processors.openai_prompt_processor.OpenAI')
    def test_respond_with_text_empty_response(self, mock_openai):
        mock_response = Mock()
        mock_response.output_text = None
        mock_openai.return_value.responses.create.return_value = mock_response

        processor = OpenAiPromptProcessor(api_key='test-key')

        result = processor.respond_with_text("System prompt", "Test prompt")
        assert result is None

    @patch('src.processors.openai_prompt_processor.OpenAI')
    def test_respond_with_model_failed_parsing(self, mock_openai):
        mock_response = Mock()
        mock_response.output_parsed = None
        mock_openai.return_value.responses.parse.return_value = mock_response

        processor = OpenAiPromptProcessor(api_key='test-key')

        with pytest.raises(ValueError, match="Failed to parse structured response from OpenAI API"):
            processor.respond_with_model("System prompt", "Test prompt", MockResponse)

    @patch('src.processors.openai_prompt_processor.OpenAI')
    def test_respond_with_text_custom_parameters(self, mock_openai):
        mock_response = Mock()
        mock_response.output_text = "Custom response"
        mock_openai.return_value.responses.create.return_value = mock_response

        processor = OpenAiPromptProcessor(api_key='test-key')
        processor.respond_with_text("System prompt", "Test prompt", max_tokens=100)

        call_args = mock_openai.return_value.responses.create.call_args
        assert call_args[1]['max_output_tokens'] == 100

    @patch('src.processors.openai_prompt_processor.OpenAI')
    def test_respond_with_text_conversation_history(self, mock_openai):
        mock_response = Mock()
        mock_response.output_text = "Response with history"
        mock_openai.return_value.responses.create.return_value = mock_response

        processor = OpenAiPromptProcessor(api_key='test-key')
        conversation_history: list[GenericMessage] = [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"}
        ]

        result = processor.respond_with_text("System prompt", "Current prompt", conversation_history=conversation_history)

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

    @patch('src.processors.openai_prompt_processor.OpenAI')
    def test_respond_with_stream(self, mock_openai):
        # Mock the streaming response chunks
        chunk1 = Mock(spec=ResponseTextDeltaEvent)
        chunk1.delta = "Hello "

        chunk2 = Mock(spec=ResponseTextDeltaEvent)
        chunk2.delta = "world"

        chunk3 = Mock(spec=ResponseTextDeltaEvent)
        chunk3.delta = "!"

        mock_openai.return_value.responses.create.return_value = iter([chunk1, chunk2, chunk3])

        processor = OpenAiPromptProcessor(api_key='test-key')
        result = list(processor.respond_with_stream("System prompt", "Test prompt"))

        assert result == ["Hello ", "world", "!"]
        mock_openai.return_value.responses.create.assert_called_once()

    @patch('src.processors.openai_prompt_processor.OpenAI')
    def test_respond_with_model_custom_parameters(self, mock_openai):
        mock_parsed_response = MockResponse(name="John", age=30, description="Test person")
        mock_response = Mock()
        mock_response.output_parsed = mock_parsed_response
        mock_openai.return_value.responses.parse.return_value = mock_response

        processor = OpenAiPromptProcessor(api_key='test-key')
        processor.respond_with_model("System prompt", "Test prompt", MockResponse, max_tokens=100)

        call_args = mock_openai.return_value.responses.parse.call_args
        assert call_args[1]['max_output_tokens'] == 100

    @patch('src.processors.openai_prompt_processor.OpenAI')
    def test_respond_with_model_conversation_history(self, mock_openai):
        mock_parsed_response = MockResponse(name="John", age=30, description="Test person")
        mock_response = Mock()
        mock_response.output_parsed = mock_parsed_response
        mock_openai.return_value.responses.parse.return_value = mock_response

        processor = OpenAiPromptProcessor(api_key='test-key')
        conversation_history: list[GenericMessage] = [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"}
        ]

        result = processor.respond_with_model("System prompt", "Current prompt", MockResponse, conversation_history=conversation_history)

        assert isinstance(result, MockResponse)
        assert result.name == "John"

        # Check that conversation history was included in the input
        call_args = mock_openai.return_value.responses.parse.call_args
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

