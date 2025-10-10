from collections.abc import Iterator
from typing import Any, TypeVar

from pydantic import BaseModel

from src.chat_logger import ChatLogger
from src.components.character_pipeline import CharacterPipeline, CharacterResponseInput, EvaluationInput, PlanGenerationInput
from src.models.character import Character
from src.models.message import GenericMessage
from src.models.prompt_processor import PromptProcessor

T = TypeVar('T', bound=BaseModel)

class MockPromptProcessor(PromptProcessor):
    """Test implementation of PromptProcessor for testing."""

    def __init__(self, response: str | Iterator[str] | BaseModel = "Mock response"):
        self.response = response
        self.call_history: list[dict[str, Any]] = []
        self.logger = None

    def get_processor_specific_prompt(self) -> str:
        return "Mock processor specific prompt for testing"

    def set_logger(self, logger: ChatLogger) -> None:
        """Set the logger for this processor."""
        self.logger = logger


    def respond_with_model(
        self,
        prompt: str,
        user_prompt: str,
        output_type: type[T],
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None
    ) -> T:
        # Record the call for verification
        self.call_history.append({
            "prompt": prompt,
            "user_prompt": user_prompt,
            "output_type": output_type,
            "conversation_history": conversation_history,
            "max_tokens": max_tokens
        })
        # Return the response if it's already a model, otherwise raise error
        if isinstance(self.response, BaseModel):
            return self.response # type: ignore
        raise NotImplementedError("Model response not provided")

    def respond_with_text(
        self,
        prompt: str,
        user_prompt: str,
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None,
        reasoning: bool = False
    ) -> str:
        # Record the call for verification
        self.call_history.append({
            "prompt": prompt,
            "user_prompt": user_prompt,
            "conversation_history": conversation_history,
            "max_tokens": max_tokens,
            "reasoning": reasoning
        })
        return self.response # type: ignore

    def respond_with_stream(
        self,
        prompt: str,
        user_prompt: str,
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None,
        reasoning: bool = False
    ) -> Iterator[str]:
        # Record the call for verification
        self.call_history.append({
            "prompt": prompt,
            "user_prompt": user_prompt,
            "conversation_history": conversation_history,
            "max_tokens": max_tokens,
            "reasoning": reasoning
        })
        if isinstance(self.response, str):
            # Convert string to iterator by yielding character by character (to simulate streaming)
            yield from self.response
        else:
            yield from self.response


class TestCharacterPipeline:
    def setup_method(self):
        """Set up test fixtures."""
        self.test_character = Character(
            name="Alice",
            role="Detective",
            backstory="Former police officer turned private investigator",
            personality="Sharp, analytical, slightly cynical but caring",
            appearance="Tall, auburn hair, piercing green eyes",
            relationships={"user": "professional acquaintance"},
            key_locations=["downtown office", "crime scenes", "local diner"],
            setting_description="Urban detective story setting"
        )

    def test_get_evaluation_success(self):
        """Test successful evaluation generation."""
        from src.models.evaluation import Evaluation

        # Mock processor response with Evaluation model
        evaluation_response = Evaluation(
            patterns_to_avoid="Avoid being too confrontational without evidence",
            status_update="Alice is in her office reviewing case files. User appears nervous and needs help with something important.",
            time_passed="A few minutes have passed since the last interaction",
            user_name="Unknown"
        )

        mock_processor = MockPromptProcessor(evaluation_response)

        input_data: EvaluationInput = {
            "summary": "Previous case discussion",
            "plans": "Investigate the missing person case",
            "user_message": "I need your help with something important",
            "character": self.test_character
        }

        memory: list[GenericMessage] = [
            {"role": "user", "content": "Hello Alice"},
            {"role": "assistant", "content": "Hello, what can I help you with?"}
        ]

        result = CharacterPipeline.get_evaluation(mock_processor, input_data, memory)

        assert result == evaluation_response
        assert isinstance(result, Evaluation)

        # Verify processor was called with correct arguments
        assert len(mock_processor.call_history) == 1
        call = mock_processor.call_history[0]

        # Check that prompt contains character information
        assert "Former police officer" in call['prompt']
        assert "Detective" in call['prompt'] or "investigator" in call['prompt']

        # Check that user prompt was passed
        assert call['user_prompt'] == "I need your help with something important"

        # Check conversation history was included
        assert len(call['conversation_history']) >= 2


    def test_get_character_plans_success(self):
        """Test successful character plan generation."""
        plans_response = """
        <story_plan>
        - Review the case files in detail
        - Contact the missing person's family
        - Visit the last known location
        - Interview potential witnesses
        - Check security camera footage
        - File a preliminary report
        </story_plan>
        """

        mock_processor = MockPromptProcessor(plans_response)

        input_data: PlanGenerationInput = {
            "character": self.test_character,
            "user_name": "John",
            "summary": "Missing person case discussion",
            "scenario_state": "Office meeting, case files on desk"
        }

        result = CharacterPipeline.get_character_plans(mock_processor, input_data)

        expected_plans = """- Review the case files in detail
        - Contact the missing person's family
        - Visit the last known location
        - Interview potential witnesses
        - Check security camera footage
        - File a preliminary report"""

        assert result == expected_plans

        # Verify processor was called
        assert len(mock_processor.call_history) == 1
        call = mock_processor.call_history[0]

        # Check character information in prompt
        assert "Alice" in call['prompt']
        assert "John" in call['prompt']

    def test_get_character_plans_missing_story_plan_tag(self):
        """Test plan generation fails when <story_plan> tag is missing."""
        plans_response = "Just some text without story plan tags."

        mock_processor = MockPromptProcessor(plans_response)

        input_data: PlanGenerationInput = {
            "character": self.test_character,
            "user_name": "John",
            "summary": "Test summary",
            "scenario_state": "Test state"
        }

        result = CharacterPipeline.get_character_plans(mock_processor, input_data)

        assert result is None

    def test_get_character_response_success(self):
        """Test successful character response generation."""
        character_response = "*Alice looks up from the case files, her green eyes sharp with focus*\n\n\"I've reviewed what you've given me, and there are definitely some inconsistencies here.\""

        mock_processor = MockPromptProcessor(character_response)

        input_data: CharacterResponseInput = {
            "summary": "Discussion about missing person case",
            "previous_response": "I understand you need help",
            "character": self.test_character,
            "user_name": "John",
            "user_message": "Here are the case files",
            "scenario_state": "Office meeting, files on desk"
        }

        memory: list[GenericMessage] = [
            {"role": "user", "content": "I need help with a case"},
            {"role": "assistant", "content": "I can help you with that"}
        ]

        result = CharacterPipeline.get_character_response(mock_processor, input_data, memory)

        # Just check that result is not None and collect the content from the generator
        assert result is not None
        content = "".join(result)
        assert "Alice looks up" in content

        # Verify processor was called
        assert len(mock_processor.call_history) == 1
        call = mock_processor.call_history[0]

        # Check character information in prompt
        assert "Alice" in call['prompt']
        assert "John" in call['prompt']


    def test_get_memory_summary(self):
        """Test memory summarization."""
        summary_response = "Alice met with John to discuss a missing person case. Key details include timeline inconsistencies and missing witness statements."

        mock_processor = MockPromptProcessor(summary_response)

        memory: list[GenericMessage] = [
            {"role": "user", "content": "I need help with a case"},
            {"role": "assistant", "content": "I can help you with that"},
            {"role": "user", "content": "Here are the details"},
            {"role": "assistant", "content": "I see some inconsistencies"}
        ]

        result = CharacterPipeline.get_memory_summary(mock_processor, memory)

        assert result == summary_response

        # Verify processor was called
        assert len(mock_processor.call_history) == 1
        call = mock_processor.call_history[0]

        # Check that memory content was included in user prompt
        user_prompt = call['user_prompt']
        assert "I need help with a case" in user_prompt
        assert "Here are the details" in user_prompt

    def test_parse_xml_tag_success(self):
        """Test successful XML tag parsing."""
        response_text = """
        Some intro text
        <test_tag>
        This is the content inside the tag
        </test_tag>
        Some outro text
        """

        result = CharacterPipeline.parse_xml_tag(response_text, "test_tag")

        assert result == "This is the content inside the tag"

    def test_parse_xml_tag_case_insensitive(self):
        """Test XML tag parsing is case insensitive."""
        response_text = """
        <TEST_TAG>
        Content in uppercase tag
        </TEST_TAG>
        """

        result = CharacterPipeline.parse_xml_tag(response_text, "test_tag")

        assert result == "Content in uppercase tag"

    def test_parse_xml_tag_multiline(self):
        """Test XML tag parsing with multiline content."""
        response_text = """
        <character_response>
        Line 1 of response
        Line 2 of response
        Line 3 of response
        </character_response>
        """

        result = CharacterPipeline.parse_xml_tag(response_text, "character_response")

        expected = "Line 1 of response\n        Line 2 of response\n        Line 3 of response"
        assert result == expected

    def test_parse_xml_tag_multiple_tags_returns_first(self):
        """Test XML parsing returns first match when multiple tags exist."""
        response_text = """
        <option>First option</option>
        Some text in between
        <option>Second option</option>
        """

        result = CharacterPipeline.parse_xml_tag(response_text, "option")

        assert result == "First option"

    def test_parse_xml_tag_no_tag_returns_none(self):
        """Test XML parsing returns None when tag is not found."""
        response_text = "Some text without any XML tags"

        result = CharacterPipeline.parse_xml_tag(response_text, "missing_tag")

        assert result is None

    def test_parse_xml_tag_empty_tag(self):
        """Test XML parsing with empty tag content."""
        response_text = "<empty_tag></empty_tag>"

        result = CharacterPipeline.parse_xml_tag(response_text, "empty_tag")

        assert result == ""

    def test_map_character_to_prompt_variables(self):
        """Test mapping character to prompt variables."""
        result = CharacterPipeline._map_character_to_prompt_variables(self.test_character)

        expected = {
            "character_name": "Alice",
            "character_background": "Former police officer turned private investigator",
            "character_appearance": "Tall, auburn hair, piercing green eyes",
            "character_personality": "Sharp, analytical, slightly cynical but caring",
            "relationships": "- user: professional acquaintance",
            "key_locations": "- downtown office\n- crime scenes\n- local diner",
            "setting_description": "Urban detective story setting"
        }

        assert result == expected

    def test_map_character_to_prompt_variables_missing_user_relationship(self):
        """Test character mapping with empty relationships."""
        character = Character(
            name="Bob",
            role="Engineer",
            backstory="Software engineer",
            personality="Analytical",
            appearance="Average height",
            relationships={},  # No user relationship
            key_locations=["office"],
            setting_description="Modern office environment"
        )

        result = CharacterPipeline._map_character_to_prompt_variables(character)

        assert result["relationships"] == ""

    def test_map_character_to_prompt_variables_empty_locations(self):
        """Test character mapping with empty key locations."""
        character = Character(
            name="Bob",
            role="Engineer",
            backstory="Software engineer",
            personality="Analytical",
            appearance="Average height",
            relationships={"user": "colleague"},
            key_locations=[],  # Empty locations
            setting_description="Modern office environment"
        )

        result = CharacterPipeline._map_character_to_prompt_variables(character)

        assert result["key_locations"] == ""

