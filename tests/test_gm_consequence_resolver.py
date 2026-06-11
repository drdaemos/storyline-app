from src.models.simulation import (
    DriveEffect,
    GMConsequenceAction,
    GMConsequenceResult,
    ReactiveEffect,
)
from src.pipeline.gm_consequence_resolver import GMConsequenceResolver
from tests.pipeline_test_utils import FakePromptProcessor


class TestGMConsequenceResolver:
    def test_resolves_consequences(self) -> None:
        processor = FakePromptProcessor()
        processor.model_responses.append(
            GMConsequenceResult(
                consequences=[
                    GMConsequenceAction(
                        character="Marta",
                        action_ref="Cook eggs",
                        drive_effects=[DriveEffect(drive="satiation", change=2)],
                        reactive_effects=[],
                        reasoning="Cooking produces food.",
                    ),
                    GMConsequenceAction(
                        character="Ren",
                        action_ref="Intimidate target",
                        drive_effects=[],
                        reactive_effects=[
                            ReactiveEffect(character="Alex", drive="composure", change=-1)
                        ],
                        reasoning="Successful intimidation shakes the target.",
                    ),
                ]
            )
        )
        resolver = GMConsequenceResolver(processor)

        result = resolver.execute(
            outcomes=[
                {"character": "Marta", "action_summary": "Cook eggs", "result": "auto_succeed"},
                {"character": "Ren", "action_summary": "Intimidate target", "result": "success", "roll_details": "14 vs DC 12"},
            ],
            rules_text="Grounded realism.",
            location="Kitchen",
            time="Morning",
            characters_present=["Marta", "Ren", "Alex"],
            drive_schema_summary="satiation: 0-10, energy: 0-10",
        )

        assert len(result.consequences) == 2
        assert result.consequences[0].drive_effects[0].drive == "satiation"
        assert result.consequences[1].reactive_effects[0].character == "Alex"
        assert "Action outcomes" in processor.last_user_prompt

    def test_fallback_on_failure(self) -> None:
        processor = FakePromptProcessor()
        processor.raise_on_model = RuntimeError("timeout")
        resolver = GMConsequenceResolver(processor)

        result = resolver.execute(
            outcomes=[
                {"character": "Ren", "action_summary": "Run", "result": "failure"},
            ],
            rules_text="",
            location="Park",
            time="Night",
            characters_present=["Ren"],
            drive_schema_summary="",
        )

        assert len(result.consequences) == 1
        assert result.consequences[0].drive_effects == []
        assert result.consequences[0].reactive_effects == []
