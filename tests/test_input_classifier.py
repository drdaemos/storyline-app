from src.models.simulation import InputClassification
from src.pipeline.input_classifier import InputClassifier
from tests.pipeline_test_utils import FakePromptProcessor


class TestInputClassifier:
    def test_classifies_input(self) -> None:
        processor = FakePromptProcessor()
        processor.model_responses.append(
            InputClassification(type="relocation", parsed_target="Docks", action_text="Go to the docks")
        )
        classifier = InputClassifier(processor)

        result = classifier.execute(
            user_input="Let's head to the docks",
            known_locations=["Bar", "Docks"],
            current_location="Bar",
            current_time="22:00",
        )

        assert result.type == "relocation"
        assert result.parsed_target == "Docks"
        assert "Available locations" in processor.last_user_prompt

    def test_fallback_to_action_on_error(self) -> None:
        processor = FakePromptProcessor()
        processor.raise_on_model = RuntimeError("LLM unavailable")
        classifier = InputClassifier(processor)

        result = classifier.execute(
            user_input="I wait",
            known_locations=[],
            current_location="Bar",
            current_time="22:00",
        )

        assert result.type == "action"
        assert result.action_text == "I wait"
