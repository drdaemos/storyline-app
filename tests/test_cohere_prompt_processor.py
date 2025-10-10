import os
from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel

from src.models.message import GenericMessage
from src.processors.cohere_prompt_processor import CoherePromptProcessor


class MockResponse(BaseModel):
    name: str
    age: int
    description: str


class TestCoherePromptProcessor:

    @patch.dict(os.environ, {'COHERE_API_KEY': 'test-key'})
    @patch('src.processors.cohere_prompt_processor.cohere.ClientV2')
    def test_init_with_env_key(self, mock_cohere):
        processor = CoherePromptProcessor()
        mock_cohere.assert_called_once_with(api_key='test-key')
        assert processor.model == "command-a-03-2025"

    @patch('src.processors.cohere_prompt_processor.cohere.ClientV2')
    def test_init_with_explicit_key(self, mock_cohere):
        CoherePromptProcessor(api_key='explicit-key')
        mock_cohere.assert_called_once_with(api_key='explicit-key')

    def test_init_with_custom_model(self):
        processor = CoherePromptProcessor(api_key='test-key', model='command-r-08-2024')
        assert processor.model == 'command-r-08-2024'

    @patch('src.processors.cohere_prompt_processor.cohere.ClientV2')
    def test_respond_with_text_output(self, mock_cohere):
        # Mock the response
        mock_message = Mock()
        mock_message.content = "This is a test response"

        mock_response = Mock()
        mock_response.message = mock_message
        mock_cohere.return_value.chat.return_value = mock_response

        processor = CoherePromptProcessor(api_key='test-key')
        result = processor.respond_with_text("Test system prompt", "Test user prompt")

        assert result == "This is a test response"
        mock_cohere.return_value.chat.assert_called_once()

    @patch('src.processors.cohere_prompt_processor.cohere.ClientV2')
    def test_respond_with_model_output(self, mock_cohere):
        # Mock the response with JSON content
        mock_message = Mock()
        mock_message.content = [Mock(text='{"name": "John", "age": 30, "description": "Test person"}')]

        mock_response = Mock()
        mock_response.message = mock_message
        mock_cohere.return_value.chat.return_value = mock_response

        processor = CoherePromptProcessor(api_key='test-key')
        result = processor.respond_with_model("Test system prompt", "Test user prompt", MockResponse)

        assert isinstance(result, MockResponse)
        assert result.name == "John"
        assert result.age == 30
        assert result.description == "Test person"
        mock_cohere.return_value.chat.assert_called_once()

    @patch('src.processors.cohere_prompt_processor.cohere.ClientV2')
    def test_respond_with_model_string_content(self, mock_cohere):
        # Mock the response with string content instead of list
        mock_message = Mock()
        mock_message.content = '{"name": "John", "age": 30, "description": "Test person"}'

        mock_response = Mock()
        mock_response.message = mock_message
        mock_cohere.return_value.chat.return_value = mock_response

        processor = CoherePromptProcessor(api_key='test-key')
        result = processor.respond_with_model("Test system prompt", "Test user prompt", MockResponse)

        assert isinstance(result, MockResponse)
        assert result.name == "John"
        assert result.age == 30
        assert result.description == "Test person"

    @patch('src.processors.cohere_prompt_processor.cohere.ClientV2')
    def test_respond_with_text_with_substituted_string_output(self, mock_cohere):
        mock_message = Mock()
        mock_message.content = "Hello Alice, you are 25 years old!"

        mock_response = Mock()
        mock_response.message = mock_message
        mock_cohere.return_value.chat.return_value = mock_response

        processor = CoherePromptProcessor(api_key='test-key')
        system_prompt = "You are a helpful assistant"
        user_prompt = "Generate a greeting for Alice who is 25 years old"

        result = processor.respond_with_text(system_prompt, user_prompt)

        assert result == "Hello Alice, you are 25 years old!"

    @patch('src.processors.cohere_prompt_processor.cohere.ClientV2')
    def test_respond_with_text_empty_response(self, mock_cohere):
        mock_response = Mock()
        mock_response.message = None
        mock_cohere.return_value.chat.return_value = mock_response

        processor = CoherePromptProcessor(api_key='test-key')

        with pytest.raises(ValueError, match="No response content received from Cohere API"):
            processor.respond_with_text("Test system prompt", "Test user prompt")

    @patch('src.processors.cohere_prompt_processor.cohere.ClientV2')
    def test_respond_with_text_no_content(self, mock_cohere):
        mock_message = Mock()
        mock_message.content = None

        mock_response = Mock()
        mock_response.message = mock_message
        mock_cohere.return_value.chat.return_value = mock_response

        processor = CoherePromptProcessor(api_key='test-key')

        with pytest.raises(ValueError, match="No response content received from Cohere API"):
            processor.respond_with_text("Test system prompt", "Test user prompt")

    @patch('src.processors.cohere_prompt_processor.cohere.ClientV2')
    def test_respond_with_model_invalid_json(self, mock_cohere):
        mock_message = Mock()
        mock_message.content = [Mock(text='invalid json')]

        mock_response = Mock()
        mock_response.message = mock_message
        mock_cohere.return_value.chat.return_value = mock_response

        processor = CoherePromptProcessor(api_key='test-key')

        with pytest.raises(ValueError, match="Failed to parse structured response"):
            processor.respond_with_model("Test system prompt", "Test user prompt", MockResponse)

    @patch('src.processors.cohere_prompt_processor.cohere.ClientV2')
    def test_respond_with_model_invalid_data(self, mock_cohere):
        mock_message = Mock()
        mock_message.content = [Mock(text='{"invalid": "data"}')]  # Missing required fields

        mock_response = Mock()
        mock_response.message = mock_message
        mock_cohere.return_value.chat.return_value = mock_response

        processor = CoherePromptProcessor(api_key='test-key')

        with pytest.raises(ValueError, match="Failed to parse structured response"):
            processor.respond_with_model("Test system prompt", "Test user prompt", MockResponse)

    @patch('src.processors.cohere_prompt_processor.cohere.ClientV2')
    def test_respond_with_text_custom_parameters(self, mock_cohere):
        mock_message = Mock()
        mock_message.content = "Custom response"

        mock_response = Mock()
        mock_response.message = mock_message
        mock_cohere.return_value.chat.return_value = mock_response

        processor = CoherePromptProcessor(api_key='test-key')
        processor.respond_with_text("Test system prompt", "Test user prompt", max_tokens=100)

        call_args = mock_cohere.return_value.chat.call_args
        assert call_args[1]['max_tokens'] == 100

    @patch('src.processors.cohere_prompt_processor.cohere.ClientV2')
    def test_respond_with_text_conversation_history(self, mock_cohere):
        mock_message = Mock()
        mock_message.content = "Response with history"

        mock_response = Mock()
        mock_response.message = mock_message
        mock_cohere.return_value.chat.return_value = mock_response

        processor = CoherePromptProcessor(api_key='test-key')
        conversation_history: list[GenericMessage] = [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"}
        ]

        result = processor.respond_with_text("System prompt", "Current prompt", conversation_history=conversation_history)

        assert result == "Response with history"

        # Check that conversation history was included in the messages
        call_args = mock_cohere.return_value.chat.call_args
        messages = call_args[1]['messages']

        assert len(messages) == 4  # 1 system + 2 history + 1 current
        # Messages are now proper Cohere message objects
        assert messages[0].role == "system"
        assert messages[0].content == "System prompt"
        assert messages[1].role == "user"
        assert messages[1].content == "Previous message"
        assert messages[2].role == "assistant"
        assert messages[2].content == "Previous response"
        assert messages[3].role == "user"
        assert messages[3].content == "Current prompt"

    @patch('src.processors.cohere_prompt_processor.cohere.ClientV2')
    def test_respond_with_text_with_list_content(self, mock_cohere):
        # Mock response with list content for string processing
        mock_text_block1 = Mock()
        mock_text_block1.text = "First part "

        mock_text_block2 = Mock()
        mock_text_block2.text = "second part"

        mock_message = Mock()
        mock_message.content = [mock_text_block1, mock_text_block2]

        mock_response = Mock()
        mock_response.message = mock_message
        mock_cohere.return_value.chat.return_value = mock_response

        processor = CoherePromptProcessor(api_key='test-key')
        result = processor.respond_with_text("Test system prompt", "Test user prompt")

        assert result == "First part second part"

    @patch('src.processors.cohere_prompt_processor.cohere.ClientV2')
    def test_respond_with_stream(self, mock_cohere):
        # Mock the streaming response chunks
        chunk1 = Mock()
        chunk1.delta = Mock()
        chunk1.delta.message = Mock()
        chunk1.delta.message.content = [Mock()]
        chunk1.delta.message.content[0].text = "Hello "

        chunk2 = Mock()
        chunk2.delta = Mock()
        chunk2.delta.message = Mock()
        chunk2.delta.message.content = [Mock()]
        chunk2.delta.message.content[0].text = "world"

        chunk3 = Mock()
        chunk3.delta = Mock()
        chunk3.delta.message = Mock()
        chunk3.delta.message.content = [Mock()]
        chunk3.delta.message.content[0].text = "!"

        mock_cohere.return_value.chat_stream.return_value = iter([chunk1, chunk2, chunk3])

        processor = CoherePromptProcessor(api_key='test-key')
        result = list(processor.respond_with_stream("Test system prompt", "Test user prompt"))

        assert result == ["Hello ", "world", "!"]
        mock_cohere.return_value.chat_stream.assert_called_once()

    @patch('src.processors.cohere_prompt_processor.cohere.ClientV2')
    def test_respond_with_model_custom_parameters(self, mock_cohere):
        mock_message = Mock()
        mock_message.content = [Mock(text='{"name": "John", "age": 30, "description": "Test person"}')]

        mock_response = Mock()
        mock_response.message = mock_message
        mock_cohere.return_value.chat.return_value = mock_response

        processor = CoherePromptProcessor(api_key='test-key')
        processor.respond_with_model("Test system prompt", "Test user prompt", MockResponse, max_tokens=100)

        call_args = mock_cohere.return_value.chat.call_args
        assert call_args[1]['max_tokens'] == 100

    @patch('src.processors.cohere_prompt_processor.cohere.ClientV2')
    def test_respond_with_model_conversation_history(self, mock_cohere):
        mock_message = Mock()
        mock_message.content = [Mock(text='{"name": "John", "age": 30, "description": "Test person"}')]

        mock_response = Mock()
        mock_response.message = mock_message
        mock_cohere.return_value.chat.return_value = mock_response

        processor = CoherePromptProcessor(api_key='test-key')
        conversation_history: list[GenericMessage] = [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"}
        ]

        result = processor.respond_with_model("System prompt", "Current prompt", MockResponse, conversation_history=conversation_history)

        assert isinstance(result, MockResponse)
        assert result.name == "John"

        # Check that conversation history was included in the messages
        call_args = mock_cohere.return_value.chat.call_args
        messages = call_args[1]['messages']

        assert len(messages) == 4  # 1 system + 2 history + 1 current

