from src.models.simulation import GMActionEvaluation, GMEvaluationResult
from src.pipeline.gm_evaluator import GMEvaluator
from tests.pipeline_test_utils import FakePromptProcessor


class TestGMEvaluator:
    def test_evaluates_actions(self) -> None:
        processor = FakePromptProcessor()
        processor.model_responses.append(
            GMEvaluationResult(
                evaluations=[
                    GMActionEvaluation(
                        character="Ren",
                        action_summary="Ren climbs the fence",
                        reasoning="Athletic uncertainty",
                        result_override=None,
                        check_required=True,
                        skill="athletics",
                        dc=14,
                    )
                ]
            )
        )
        evaluator = GMEvaluator(processor)

        result = evaluator.execute(
            actions=[{"character": "Ren", "type": "action", "description": "Ren climbs the fence"}],
            rules_text="Use checks for risky feats.",
            location="Yard",
            time="Night",
            characters_present=["Ren"],
            skills_by_character={"Ren": {"athletics": 5}},
            drive_schema_summary="energy: 0-10",
        )

        assert len(result.evaluations) == 1
        assert result.evaluations[0].check_required is True
        assert result.evaluations[0].result_override is None
        assert "Actions this turn" in processor.last_user_prompt

    def test_auto_fail_override(self) -> None:
        processor = FakePromptProcessor()
        processor.model_responses.append(
            GMEvaluationResult(
                evaluations=[
                    GMActionEvaluation(
                        character="Ren",
                        action_summary="Ren tries to fly",
                        reasoning="Physically impossible.",
                        result_override="auto_fail",
                        check_required=False,
                        departure=False,
                    )
                ]
            )
        )
        evaluator = GMEvaluator(processor)

        result = evaluator.execute(
            actions=[{"character": "Ren", "type": "action", "description": "Ren tries to fly"}],
            rules_text="Grounded realism.",
            location="Yard",
            time="Day",
            characters_present=["Ren"],
            skills_by_character={"Ren": {}},
            drive_schema_summary="",
        )

        assert len(result.evaluations) == 1
        assert result.evaluations[0].result_override == "auto_fail"
        assert result.evaluations[0].check_required is False

    def test_fallback_auto_success_when_model_fails(self) -> None:
        processor = FakePromptProcessor()
        processor.raise_on_model = RuntimeError("timeout")
        evaluator = GMEvaluator(processor)

        result = evaluator.execute(
            actions=[{"character": "Ren", "type": "action", "description": "Ren waves"}],
            rules_text="",
            location="Bar",
            time="22:00",
            characters_present=["Ren"],
            skills_by_character={"Ren": {}},
            drive_schema_summary="",
        )

        assert len(result.evaluations) == 1
        assert result.evaluations[0].check_required is False
        assert result.evaluations[0].result_override == "auto_succeed"
        assert result.evaluations[0].reasoning.startswith("Auto-success fallback")
