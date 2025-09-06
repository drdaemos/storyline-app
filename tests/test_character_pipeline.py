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

    def __init__(self, response: str | Iterator[str] = "Mock response"):
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
        raise NotImplementedError("Model response not implemented")

    def respond_with_text(
        self,
        prompt: str,
        user_prompt: str,
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None
    ) -> str:
        # Record the call for verification
        self.call_history.append({
            "prompt": prompt,
            "user_prompt": user_prompt,
            "conversation_history": conversation_history,
            "max_tokens": max_tokens
        })
        return self.response # type: ignore

    def respond_with_stream(
        self,
        prompt: str,
        user_prompt: str,
        conversation_history: list[GenericMessage] | None = None,
        max_tokens: int | None = None
    ) -> Iterator[str]:
        # Record the call for verification
        self.call_history.append({
            "prompt": prompt,
            "user_prompt": user_prompt,
            "conversation_history": conversation_history,
            "max_tokens": max_tokens
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
        # Mock processor response with required XML tags
        evaluation_response = """
        Time skip: morning meeting scheduled
        Setting: office conference room
        Character drinking coffee, reviewing case files

        Importance Level: MEDIUM
        Response Needed: Yes
        Emotional Shift: Focus +1, Curiosity +2

        <option A>
        Character action: Review case files thoroughly - "Let me check these details again."
        Consequence: Better understanding of case
        </option A>

        <option B>
        Character action: Ask direct questions - "What aren't you telling me?"
        Consequence: Confrontational approach
        </option B>

        <option C>
        Character action: Suggest meeting postponement - "We should reschedule this."
        Consequence: Delay investigation
        </option C>

        Internal State: Something feels off about this case. Need more information.

        <continuation>
        option A
        </continuation>

        <status_update>
        User State: Sitting across desk, nervous fidgeting
        Character Emotional State: Focused, slightly suspicious
        Character Physical State: Leaning forward, hands clasped
        State of the surroundings: Office environment, morning light
        </status_update>
        """

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

        # Verify processor was called with correct arguments
        assert len(mock_processor.call_history) == 1
        call = mock_processor.call_history[0]

        # Check that prompt contains character information
        assert "Alice" in call['prompt']
        assert "Former police officer" in call['prompt']

        # Check that user prompt was passed
        assert call['user_prompt'] == "I need your help with something important"

        # Check conversation history was included
        assert len(call['conversation_history']) >= 2

    def test_get_evaluation_missing_continuation_tag(self):
        """Test evaluation fails when <continuation> tag is missing."""
        evaluation_response = """
        Basic evaluation without continuation tag.

        Importance Level: MEDIUM
        Response Needed: Yes
        """

        mock_processor = MockPromptProcessor(evaluation_response)

        input_data: EvaluationInput = {
            "summary": "",
            "plans": "",
            "user_message": "Test message",
            "character": self.test_character
        }

        result = CharacterPipeline.get_evaluation(mock_processor, input_data, [])

        assert result is None

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

        # Check character name in prompt
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
        character_response = """
        <character_response>
        *Alice looks up from the case files, her green eyes sharp with focus*

        "I've reviewed what you've given me, and there are definitely some inconsistencies here. The timeline doesn't add up, and there are gaps in the witness statements."

        *She leans back in her chair, tapping her pen against the desk*

        "Before we proceed, I need you to be completely honest with me. Is there anything else you haven't told me about this case?"
        </character_response>
        """

        mock_processor = MockPromptProcessor(character_response)

        input_data: CharacterResponseInput = {
            "summary": "Discussion about missing person case",
            "previous_response": "I understand you need help",
            "character_name": "Alice",
            "user_name": "John",
            "user_message": "Here are the case files",
            "continuation_option": "Review case files thoroughly",
            "scenario_state": "Office meeting, files on desk"
        }

        result = CharacterPipeline.get_character_response(mock_processor, input_data)

        # Just check that result is not None and collect the content from the generator
        assert result is not None
        content = "".join(result)
        assert "*Alice looks up from the case files" in content
        assert "timeline doesn't add up" in content
        assert "completely honest with me" in content

        # Verify processor was called
        assert len(mock_processor.call_history) == 1
        call = mock_processor.call_history[0]

        # Check character information in prompt
        assert "Alice" in call['prompt']
        assert "John" in call['prompt']

    def test_get_character_response_missing_character_response_tag(self):
        """Test character response fails when <character_response> tag is missing."""
        response_text = "Just some response without character response tags."

        mock_processor = MockPromptProcessor(response_text)

        input_data: CharacterResponseInput = {
            "summary": "Discussion about missing person case",
            "previous_response": "",
            "character_name": "Alice",
            "user_name": "John",
            "user_message": "Test message",
            "continuation_option": "Test option",
            "scenario_state": "Test state"
        }

        result = CharacterPipeline.get_character_response(mock_processor, input_data)

        assert result is None

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
            "relationship_status": "professional acquaintance",
            "key_locations": "downtown office; crime scenes; local diner",
            "setting_description": "Urban detective story setting"
        }

        assert result == expected

    def test_map_character_to_prompt_variables_missing_user_relationship(self):
        """Test character mapping with missing user relationship."""
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

        assert result["relationship_status"] == "unknown"

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

