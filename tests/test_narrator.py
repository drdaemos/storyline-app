from src.pipeline.narrator import Narrator
from tests.pipeline_test_utils import FakePromptProcessor


class TestNarrator:
    def test_execute_stream_returns_chunks(self) -> None:
        processor = FakePromptProcessor()
        processor.stream_responses.append(["A door creaks. ", "Ren steps inside."])
        narrator = Narrator(processor)

        chunks = list(
            narrator.execute_stream(
                outcomes=[{"character": "Ren", "action_summary": "opens the door", "result": "success", "roll_details": ""}],
                rules_text="Noir tone.",
                world_lore_brief="Old district with narrow alleys.",
                location="Warehouse",
                time="Late night",
                characters_present=["Ren"],
                narration_history=[],
            )
        )

        assert chunks == ["A door creaks. ", "Ren steps inside."]
        assert "Hard constraints" in processor.last_prompt
        assert "Action outcomes" in processor.last_user_prompt

    def test_execute_joins_stream_chunks(self) -> None:
        processor = FakePromptProcessor()
        processor.stream_responses.append(["One. ", "Two. ", "Three."])
        narrator = Narrator(processor)

        result = narrator.execute(
            outcomes=[{"character": "Ren", "action_summary": "waits", "result": "success", "roll_details": ""}],
            rules_text="",
            world_lore_brief="",
            location="Bar",
            time="22:00",
            characters_present=["Ren"],
            narration_history=["Previous narration"],
        )

        assert result == "One. Two. Three."
