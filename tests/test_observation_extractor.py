from src.models.simulation import Observation, ObservationExtractionResult
from src.pipeline.observation_extractor import ObservationExtractor
from tests.pipeline_test_utils import FakePromptProcessor


class TestObservationExtractor:
    def test_extracts_observations(self) -> None:
        processor = FakePromptProcessor()
        processor.model_responses.append(
            ObservationExtractionResult(
                observations=[
                    Observation(
                        subject="Mara",
                        content="Mara blocks Ren's path.",
                        importance=4,
                        visibility="public",
                    )
                ]
            )
        )
        extractor = ObservationExtractor(processor)

        result = extractor.execute(
            narration="Mara steps into Ren's way and squares her shoulders.",
            outcomes=[{"character": "Mara", "action_summary": "blocks Ren", "result": "success"}],
            characters_present=["Mara", "Ren"],
        )

        assert len(result.observations) == 1
        assert result.observations[0].subject == "Mara"

    def test_fallback_empty_on_error(self) -> None:
        processor = FakePromptProcessor()
        processor.raise_on_model = RuntimeError("parse failure")
        extractor = ObservationExtractor(processor)

        result = extractor.execute(
            narration="Quiet room.",
            outcomes=[],
            characters_present=[],
        )

        assert result.observations == []
