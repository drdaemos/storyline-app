from src.models.simulation import ContinuationOption, ContinuationOptionsResult
from src.pipeline.continuation_generator import ContinuationGenerator
from tests.pipeline_test_utils import FakePromptProcessor


class TestContinuationGenerator:
    def test_generates_continuation_options(self) -> None:
        processor = FakePromptProcessor()
        processor.model_responses.append(
            ContinuationOptionsResult(
                options=[
                    ContinuationOption(type="dialogue", description="Ask Mara why she hesitated.", target="Mara"),
                    ContinuationOption(type="relocation", description="Go to the back alley.", target="Back Alley"),
                ]
            )
        )
        generator = ContinuationGenerator(processor)

        result = generator.execute(
            location="Bar",
            time="22:00",
            characters_present=["Mara"],
            narration_summary="Mara blocks the exit and waits.",
            user_character_brief="You are cautious.",
            user_drives_summary="energy: 6",
            user_emotional_state_summary="composure: 4",
            known_locations=["Bar", "Back Alley"],
        )

        assert len(result.options) == 2
        assert result.options[0].type == "dialogue"
        assert "Available locations" in processor.last_prompt

    def test_fallback_empty_on_error(self) -> None:
        processor = FakePromptProcessor()
        processor.raise_on_model = RuntimeError("LLM down")
        generator = ContinuationGenerator(processor)

        result = generator.execute(
            location="Bar",
            time="22:00",
            characters_present=[],
            narration_summary="Quiet room.",
            user_character_brief="",
            user_drives_summary="",
            user_emotional_state_summary="",
            known_locations=[],
        )

        assert result.options == []
