from src.models.simulation import CharacterProcessingResult, ReflectionResult, StateDiff
from src.pipeline.character_processor import CharacterProcessor
from tests.pipeline_test_utils import FakePromptProcessor


class TestCharacterProcessor:
    def test_processes_state_diffs_and_reflection(self) -> None:
        processor = FakePromptProcessor()
        processor.model_responses.append(
            CharacterProcessingResult(
                state_diffs=[StateDiff(stat="trust", target="Mara", change=1, reasoning="Mara helped.")],
                reflection=ReflectionResult(
                    subject=["Mara"],
                    content="Maybe she's finally being honest.",
                    importance=3,
                    source_observation_ids=["obs-1"],
                ),
            )
        )
        character_processor = CharacterProcessor(processor)

        result = character_processor.execute(
            character_name="Ren",
            character_card_brief="Ren profile",
            reactive_stats_schema="trust 0-10",
            character_reactive_stats="trust (toward Mara): 4",
            this_turn_observations=[{"id": "obs-1", "content": "Mara shielded Ren from the guard."}],
            prior_unreflected_observations=[],
            active_intent_goal="Figure out if Mara is an ally",
        )

        assert len(result.state_diffs) == 1
        assert result.state_diffs[0].stat == "trust"
        assert result.reflection is not None
        assert "honest" in result.reflection.content

    def test_fallback_on_error(self) -> None:
        processor = FakePromptProcessor()
        processor.raise_on_model = RuntimeError("unavailable")
        character_processor = CharacterProcessor(processor)

        result = character_processor.execute(
            character_name="Ren",
            character_card_brief="Ren profile",
            reactive_stats_schema="",
            character_reactive_stats="",
            this_turn_observations=[],
            prior_unreflected_observations=[],
            active_intent_goal="",
        )

        assert result.state_diffs == []
        assert result.reflection is None
