from src.models.simulation import ActionWithReasoning, CharacterAction, Ruleset
from src.pipeline.action_generator import ActionGenerator
from tests.pipeline_test_utils import FakePromptProcessor

_RULESET = Ruleset(name="test", rules_text="No special rules.")


class TestActionGenerator:
    def test_generates_action(self) -> None:
        processor = FakePromptProcessor()
        processor.model_responses.append(
            ActionWithReasoning(
                reasoning="Ren wants to pressure Mara.",
                action=CharacterAction(
                    type="dialogue",
                    target="Mara",
                    description="Ren says, 'Tell me what you saw.'",
                ),
            )
        )
        generator = ActionGenerator(processor)

        result = generator.execute(
            character_name="Ren",
            character_card="Ren profile",
            intent_goal="Get answers from Mara",
            drives_summary="energy: 6",
            emotional_state_summary="composure: 4",
            assembled_memory="[OBS t2 | Mara] Mara avoided eye contact",
            location="Bar",
            time="22:00",
            characters_present=["Ren", "Mara"],
            user_action_description="You ask what happened.",
            ruleset=_RULESET,
        )

        assert result.action.type == "dialogue"
        assert result.action.target == "Mara"
        assert "Character Authenticity" in processor.last_prompt

    def test_fallback_action_on_error(self) -> None:
        processor = FakePromptProcessor()
        processor.raise_on_model = RuntimeError("bad json")
        generator = ActionGenerator(processor)

        result = generator.execute(
            character_name="Ren",
            character_card="Ren profile",
            intent_goal="",
            drives_summary="",
            emotional_state_summary="",
            assembled_memory="",
            location="Bar",
            time="22:00",
            characters_present=["Ren"],
            user_action_description="You wait.",
            ruleset=_RULESET,
        )

        assert result.action.type == "action"
        assert "pauses, considering what to do" in result.action.description
