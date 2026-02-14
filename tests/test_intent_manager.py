from src.models.simulation import Intent, IntentCompletionCheck, IntentReevaluation, SuccessCondition
from src.pipeline.intent_manager import IntentManager
from tests.pipeline_test_utils import FakePromptProcessor


class TestIntentManager:
    def test_reevaluate_generate_and_completion(self) -> None:
        processor = FakePromptProcessor()
        processor.model_responses.append(IntentReevaluation(reasoning="Reflection changes priority.", keep=False))
        processor.model_responses.append(
            Intent(
                goal="Confront Mara privately",
                success_condition=SuccessCondition(
                    type="narrative",
                    description="Mara answers directly about the ledger.",
                ),
                source_refs=["ref-1"],
            )
        )
        processor.model_responses.append(IntentCompletionCheck(reasoning="Goal clearly achieved.", complete=True))
        manager = IntentManager(processor)

        reeval = manager.reevaluate(
            character_name="Ren",
            character_card_brief="Ren profile",
            active_intent_goal="Trust Mara",
            active_intent_success_condition="Mara proves loyalty",
            reflection_content="She hid evidence.",
            drives_summary="energy: 6",
            emotional_state_summary="composure: 3",
        )
        generated = manager.generate(
            character_name="Ren",
            character_card="Ren profile",
            drives_summary="energy: 6",
            emotional_state_summary="composure: 3",
            assembled_memory="[REF] She hid evidence",
            location="Bar",
            time="22:00",
            characters_present=["Ren", "Mara"],
        )
        complete = manager.check_completion(
            active_intent_goal=generated.goal,
            success_condition_description=generated.success_condition.description or "",
            recent_events="Mara finally admits what she took.",
        )

        assert reeval.keep is False
        assert generated.goal == "Confront Mara privately"
        assert complete.complete is True

    def test_fallbacks_when_model_errors(self) -> None:
        processor = FakePromptProcessor()
        manager = IntentManager(processor)

        processor.raise_on_model = RuntimeError("LLM error")
        reeval = manager.reevaluate(
            character_name="Ren",
            character_card_brief="",
            active_intent_goal="x",
            active_intent_success_condition="y",
            reflection_content="z",
            drives_summary="",
            emotional_state_summary="",
        )
        generated = manager.generate(
            character_name="Ren",
            character_card="",
            drives_summary="",
            emotional_state_summary="",
            assembled_memory="",
            location="Bar",
            time="22:00",
            characters_present=[],
        )
        complete = manager.check_completion(
            active_intent_goal="Goal",
            success_condition_description="Done",
            recent_events="Nothing",
        )

        assert reeval.keep is True
        assert "Observe the situation" in generated.goal
        assert complete.complete is False
