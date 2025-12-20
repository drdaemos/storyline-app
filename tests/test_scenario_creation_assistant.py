"""Tests for ScenarioCreationAssistant."""

from collections.abc import Iterator

import pytest

from src.models.api_models import ChatMessageModel, PartialScenario, PersonaSummary
from src.models.character import Character
from src.scenario_creation_assistant import ScenarioCreationAssistant


class MockPromptProcessor:
    """Mock prompt processor for testing."""

    def __init__(self, response: str = "") -> None:
        self.response = response
        self.last_prompt = ""
        self.last_user_prompt = ""

    def respond_with_text(
        self,
        prompt: str,
        user_prompt: str,
        conversation_history: list | None = None,
        max_tokens: int | None = None,
    ) -> str:
        self.last_prompt = prompt
        self.last_user_prompt = user_prompt
        return self.response

    def respond_with_stream(
        self,
        prompt: str,
        user_prompt: str,
        conversation_history: list | None = None,
        max_tokens: int | None = None,
        reasoning: bool = False,
    ) -> Iterator[str]:
        self.last_prompt = prompt
        self.last_user_prompt = user_prompt
        # Yield response in chunks
        yield from self.response


class TestScenarioCreationAssistant:
    """Tests for ScenarioCreationAssistant."""

    @pytest.fixture
    def mock_character(self) -> Character:
        """Create a mock character for testing."""
        return Character(
            name="Test Character",
            tagline="A test character",
            backstory="This is a test character with a rich backstory.",
            personality="friendly, helpful",
            appearance="tall, dark hair",
        )

    @pytest.fixture
    def mock_persona(self) -> Character:
        """Create a mock persona for testing."""
        return Character(
            name="Test Persona",
            tagline="A test persona",
            backstory="This is a test persona.",
            is_persona=True,
        )

    def test_process_message_without_streaming(self, mock_character: Character) -> None:
        """Test processing a message without streaming."""
        response_text = "I'll help you create a scenario. Let me suggest something based on the character."
        processor = MockPromptProcessor(response=response_text)
        assistant = ScenarioCreationAssistant(prompt_processor=processor)

        response, updated_scenario = assistant.process_message(
            user_message="I want a dramatic scenario",
            current_scenario=PartialScenario(),
            character=mock_character,
            persona=None,
            available_personas=[],
            conversation_history=[],
        )

        assert response == response_text
        assert isinstance(updated_scenario, PartialScenario)

    def test_process_message_with_streaming(self, mock_character: Character) -> None:
        """Test processing a message with streaming callback."""
        response_text = "Creating a scenario for you."
        processor = MockPromptProcessor(response=response_text)
        assistant = ScenarioCreationAssistant(prompt_processor=processor)

        streamed_chunks: list[str] = []

        def callback(chunk: str) -> None:
            streamed_chunks.append(chunk)

        response, updated_scenario = assistant.process_message(
            user_message="Create a mystery scenario",
            current_scenario=PartialScenario(),
            character=mock_character,
            persona=None,
            available_personas=[],
            conversation_history=[],
            streaming_callback=callback,
        )

        assert "".join(streamed_chunks) == response_text
        assert response == response_text

    def test_extract_scenario_updates(self, mock_character: Character) -> None:
        """Test that scenario updates are extracted from AI response."""
        response_with_update = """I think this scenario would work well.

<scenario_update>
{
  "summary": "The Midnight Encounter",
  "intro_message": "The clock strikes midnight...",
  "narrative_category": "mystery/thriller",
  "location": "Old mansion",
  "stakes": "Life and death"
}
</scenario_update>

What do you think?"""

        processor = MockPromptProcessor(response=response_with_update)
        assistant = ScenarioCreationAssistant(prompt_processor=processor)

        response, updated_scenario = assistant.process_message(
            user_message="Make it mysterious",
            current_scenario=PartialScenario(),
            character=mock_character,
            persona=None,
            available_personas=[],
            conversation_history=[],
        )

        assert updated_scenario.summary == "The Midnight Encounter"
        assert updated_scenario.intro_message == "The clock strikes midnight..."
        assert updated_scenario.narrative_category == "mystery/thriller"
        assert updated_scenario.location == "Old mansion"
        assert updated_scenario.stakes == "Life and death"

    def test_extract_scenario_updates_with_lists(self, mock_character: Character) -> None:
        """Test that list fields are extracted correctly."""
        response_with_lists = """<scenario_update>
{
  "summary": "Test",
  "intro_message": "Test intro",
  "narrative_category": "test",
  "plot_hooks": ["tension 1", "tension 2", "tension 3"],
  "potential_directions": ["direction 1", "direction 2"]
}
</scenario_update>"""

        processor = MockPromptProcessor(response=response_with_lists)
        assistant = ScenarioCreationAssistant(prompt_processor=processor)

        _, updated_scenario = assistant.process_message(
            user_message="Add some plot hooks",
            current_scenario=PartialScenario(),
            character=mock_character,
            persona=None,
            available_personas=[],
            conversation_history=[],
        )

        assert len(updated_scenario.plot_hooks) == 3
        assert "tension 1" in updated_scenario.plot_hooks
        assert len(updated_scenario.potential_directions) == 2

    def test_extract_scenario_updates_with_dict(self, mock_character: Character) -> None:
        """Test that dict fields (character_goals) are extracted correctly."""
        response_with_dict = """<scenario_update>
{
  "summary": "Test",
  "intro_message": "Test intro",
  "narrative_category": "test",
  "character_goals": {"Alice": "Find the truth", "Bob": "Hide the secret"}
}
</scenario_update>"""

        processor = MockPromptProcessor(response=response_with_dict)
        assistant = ScenarioCreationAssistant(prompt_processor=processor)

        _, updated_scenario = assistant.process_message(
            user_message="Add character goals",
            current_scenario=PartialScenario(),
            character=mock_character,
            persona=None,
            available_personas=[],
            conversation_history=[],
        )

        assert updated_scenario.character_goals["Alice"] == "Find the truth"
        assert updated_scenario.character_goals["Bob"] == "Hide the secret"

    def test_no_update_when_no_tags(self, mock_character: Character) -> None:
        """Test that scenario remains unchanged when no update tags present."""
        response_no_update = "Let me think about this scenario idea..."

        processor = MockPromptProcessor(response=response_no_update)
        assistant = ScenarioCreationAssistant(prompt_processor=processor)

        initial_scenario = PartialScenario(summary="Initial Summary")

        _, updated_scenario = assistant.process_message(
            user_message="What do you think?",
            current_scenario=initial_scenario,
            character=mock_character,
            persona=None,
            available_personas=[],
            conversation_history=[],
        )

        assert updated_scenario.summary == "Initial Summary"

    def test_clean_response_text(self, mock_character: Character) -> None:
        """Test that clean_response_text removes update tags."""
        response_with_update = """Here's my suggestion.

<scenario_update>
{"summary": "Test"}
</scenario_update>

What do you think?"""

        processor = MockPromptProcessor(response=response_with_update)
        assistant = ScenarioCreationAssistant(prompt_processor=processor)

        cleaned = assistant.clean_response_text(response_with_update)

        assert "<scenario_update>" not in cleaned
        assert "summary" not in cleaned
        assert "Here's my suggestion." in cleaned
        assert "What do you think?" in cleaned

    def test_conversation_history_included(self, mock_character: Character) -> None:
        """Test that conversation history is passed to the processor."""
        processor = MockPromptProcessor(response="Response")
        assistant = ScenarioCreationAssistant(prompt_processor=processor)

        history = [
            ChatMessageModel(author="User", content="Hello", is_user=True),
            ChatMessageModel(author="AI", content="Hi there!", is_user=False),
        ]

        assistant.process_message(
            user_message="Continue",
            current_scenario=PartialScenario(),
            character=mock_character,
            persona=None,
            available_personas=[],
            conversation_history=history,
        )

        # The processor should have received the prompt with context
        assert "Continue" in processor.last_user_prompt

    def test_character_context_in_prompt(self, mock_character: Character) -> None:
        """Test that character information is included in the prompt."""
        processor = MockPromptProcessor(response="Response")
        assistant = ScenarioCreationAssistant(prompt_processor=processor)

        assistant.process_message(
            user_message="Create a scenario",
            current_scenario=PartialScenario(),
            character=mock_character,
            persona=None,
            available_personas=[],
            conversation_history=[],
        )

        # Character name should appear in the prompt
        assert "Test Character" in processor.last_user_prompt

    def test_persona_context_in_prompt(
        self, mock_character: Character, mock_persona: Character
    ) -> None:
        """Test that persona information is included when provided."""
        processor = MockPromptProcessor(response="Response")
        assistant = ScenarioCreationAssistant(prompt_processor=processor)

        assistant.process_message(
            user_message="Create a scenario",
            current_scenario=PartialScenario(),
            character=mock_character,
            persona=mock_persona,
            available_personas=[],
            conversation_history=[],
        )

        # Both character and persona should appear
        assert "Test Character" in processor.last_user_prompt
        assert "Test Persona" in processor.last_user_prompt

    def test_current_scenario_state_in_prompt(self, mock_character: Character) -> None:
        """Test that current scenario state is included in prompt."""
        processor = MockPromptProcessor(response="Response")
        assistant = ScenarioCreationAssistant(prompt_processor=processor)

        current_scenario = PartialScenario(
            summary="Existing Summary",
            location="Existing Location",
        )

        assistant.process_message(
            user_message="Update the scenario",
            current_scenario=current_scenario,
            character=mock_character,
            persona=None,
            available_personas=[],
            conversation_history=[],
        )

        # Current scenario state should be in the prompt
        assert "Existing Summary" in processor.last_user_prompt
        assert "Existing Location" in processor.last_user_prompt

    def test_malformed_json_in_update_tags(self, mock_character: Character) -> None:
        """Test handling of malformed JSON in update tags."""
        response_malformed = """<scenario_update>
{
  "summary": "Test"
  "intro_message": "Missing comma"
}
</scenario_update>"""

        processor = MockPromptProcessor(response=response_malformed)
        assistant = ScenarioCreationAssistant(prompt_processor=processor)

        initial_scenario = PartialScenario(summary="Original")

        _, updated_scenario = assistant.process_message(
            user_message="Update",
            current_scenario=initial_scenario,
            character=mock_character,
            persona=None,
            available_personas=[],
            conversation_history=[],
        )

        # Should return original scenario unchanged on parse error
        assert updated_scenario.summary == "Original"

    def test_partial_update_merges_with_current(self, mock_character: Character) -> None:
        """Test that partial updates are merged with current scenario."""
        response_partial_update = """<scenario_update>
{
  "location": "New Location"
}
</scenario_update>"""

        processor = MockPromptProcessor(response=response_partial_update)
        assistant = ScenarioCreationAssistant(prompt_processor=processor)

        current_scenario = PartialScenario(
            summary="Existing Summary",
            intro_message="Existing intro",
        )

        _, updated_scenario = assistant.process_message(
            user_message="Change the location",
            current_scenario=current_scenario,
            character=mock_character,
            persona=None,
            available_personas=[],
            conversation_history=[],
        )

        # Original fields should be preserved
        assert updated_scenario.summary == "Existing Summary"
        assert updated_scenario.intro_message == "Existing intro"
        # New field should be added
        assert updated_scenario.location == "New Location"

    def test_available_personas_in_prompt(self, mock_character: Character) -> None:
        """Test that available personas are included in the prompt."""
        processor = MockPromptProcessor(response="Response")
        assistant = ScenarioCreationAssistant(prompt_processor=processor)

        available_personas = [
            PersonaSummary(id="persona-1", name="Detective Jane", tagline="A sharp investigator", personality="analytical, determined"),
            PersonaSummary(id="persona-2", name="Artist Alex", tagline="A creative soul", personality="creative, emotional"),
        ]

        assistant.process_message(
            user_message="Create a scenario",
            current_scenario=PartialScenario(),
            character=mock_character,
            persona=None,
            available_personas=available_personas,
            conversation_history=[],
        )

        # Available personas should appear in the prompt
        assert "Detective Jane" in processor.last_user_prompt
        assert "persona-1" in processor.last_user_prompt
        assert "Artist Alex" in processor.last_user_prompt
        assert "persona-2" in processor.last_user_prompt

    def test_persona_suggestion_extraction(self, mock_character: Character) -> None:
        """Test that suggested persona is extracted from AI response."""
        response_with_suggestion = """I think this dark mystery scenario would work well.

<scenario_update>
{
  "summary": "The Last Clue",
  "intro_message": "The rain pelted the window as the case file lay open...",
  "narrative_category": "mystery/thriller",
  "suggested_persona_id": "persona-1",
  "suggested_persona_reason": "Detective Jane's analytical nature fits perfectly with investigating this mystery"
}
</scenario_update>

What do you think?"""

        processor = MockPromptProcessor(response=response_with_suggestion)
        assistant = ScenarioCreationAssistant(prompt_processor=processor)

        available_personas = [
            PersonaSummary(id="persona-1", name="Detective Jane", tagline="A sharp investigator"),
        ]

        _, updated_scenario = assistant.process_message(
            user_message="Create a mystery scenario",
            current_scenario=PartialScenario(),
            character=mock_character,
            persona=None,
            available_personas=available_personas,
            conversation_history=[],
        )

        assert updated_scenario.suggested_persona_id == "persona-1"
        assert "Detective Jane" in updated_scenario.suggested_persona_reason
        assert updated_scenario.summary == "The Last Clue"

    def test_system_prompt_includes_persona_instructions_when_personas_available(
        self, mock_character: Character
    ) -> None:
        """Test that system prompt includes persona suggestion instructions when personas are available."""
        processor = MockPromptProcessor(response="Response")
        assistant = ScenarioCreationAssistant(prompt_processor=processor)

        available_personas = [
            PersonaSummary(id="persona-1", name="Test Persona"),
        ]

        assistant.process_message(
            user_message="Create a scenario",
            current_scenario=PartialScenario(),
            character=mock_character,
            persona=None,
            available_personas=available_personas,
            conversation_history=[],
        )

        # System prompt should include persona suggestion instructions
        assert "suggested_persona_id" in processor.last_prompt
        assert "Persona Suggestions" in processor.last_prompt

    def test_system_prompt_excludes_persona_instructions_when_no_personas(
        self, mock_character: Character
    ) -> None:
        """Test that system prompt excludes persona instructions when no personas available."""
        processor = MockPromptProcessor(response="Response")
        assistant = ScenarioCreationAssistant(prompt_processor=processor)

        assistant.process_message(
            user_message="Create a scenario",
            current_scenario=PartialScenario(),
            character=mock_character,
            persona=None,
            available_personas=[],
            conversation_history=[],
        )

        # System prompt should NOT include persona suggestion instructions
        assert "Persona Suggestions" not in processor.last_prompt
