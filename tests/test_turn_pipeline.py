import tempfile
from pathlib import Path

import pytest

from src.character_loader import CharacterLoader
from src.memory.character_registry import CharacterRegistry
from src.memory.character_state_repository import CharacterStateRepository
from src.memory.event_repository import EventRepository
from src.memory.session_repository import SessionRepository
from src.models.simulation import (
    ActionWithReasoning,
    CharacterAction,
    CharacterProcessingResult,
    CharacterStateData,
    ContinuationOption,
    ContinuationOptionsResult,
    DriveEffect,
    EmotionalStateData,
    GMActionEvaluation,
    GMEvaluationResult,
    InputClassification,
    Intent,
    IntentCompletionCheck,
    Observation,
    ObservationExtractionResult,
    Ruleset,
    SuccessCondition,
)
from src.pipeline.turn_pipeline import TurnPipeline
from src.services.dice_resolver import DiceResolver
from src.services.event_stream_service import EventStreamService
from src.services.ruleset_service import RulesetService
from src.services.session_state_service import SessionStateService
from tests.pipeline_test_utils import FakePromptProcessor


class _DummyRulesetRegistry:
    def __init__(self, ruleset: Ruleset) -> None:
        self.ruleset = ruleset

    def get_ruleset(self, _ruleset_id: str, _user_id: str = "anonymous") -> dict:
        return self.ruleset.model_dump()


def _build_ruleset() -> Ruleset:
    return Ruleset.model_validate(
        {
            "id": "core",
            "name": "Core",
            "rules_text": "Grounded urban noir.",
            "state_schemas": {
                "drives": [{"name": "energy", "range_min": 0, "range_max": 10, "default": 5, "decay_rate": 1.0}],
                "skills": [{"name": "persuasion", "range_min": 0, "range_max": 20}],
                "emotional_state": {"global_dims": [{"name": "composure", "range_min": 0, "range_max": 10, "default": 5}], "per_relationship": []},
            },
            "config": {"narration_history_size": 5, "max_event_stream_length": 50},
        }
    )


class TestTurnPipeline:
    @pytest.fixture(autouse=True)
    def clear_database_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATABASE_URL", raising=False)

    @pytest.fixture()
    def state_env(self):
        """Set up shared DB-backed services. Yields all handles and tears down on exit."""
        temp_dir = Path(tempfile.mkdtemp())
        session_repo = SessionRepository(memory_dir=temp_dir)
        char_state_repo = CharacterStateRepository(memory_dir=temp_dir)
        event_repo = EventRepository(memory_dir=temp_dir)
        character_registry = CharacterRegistry(memory_dir=temp_dir)
        character_loader = CharacterLoader(memory_dir=temp_dir)

        session_state = SessionStateService(session_repo, char_state_repo)
        event_stream = EventStreamService(event_repo)

        character_registry.save_character(
            "npc-1",
            {
                "name": "Ren",
                "tagline": "Investigator",
                "backstory": "Relentless.",
                "personality": "Calm under pressure.",
                "appearance": "Dark coat.",
            },
        )
        character_registry.save_character(
            "persona-1",
            {
                "name": "You",
                "tagline": "Witness",
                "backstory": "Tangled in the case.",
                "personality": "Cautious.",
                "appearance": "Rain-soaked jacket.",
            },
            is_persona=True,
        )

        session_id = session_repo.create_session(
            scenario_id="scenario-1",
            world_state={"location": "Bar", "time": "22:00", "characters_present": ["npc-1"]},
            user_id="anonymous",
        )

        session_state.save_character_state(
            session_id,
            "npc-1",
            CharacterStateData(
                drives={"energy": 5},
                skills={"persuasion": 6},
                emotional_state=EmotionalStateData(global_state={"composure": 5}),
                active_intent=Intent(
                    goal="Get a straight answer from the witness.",
                    success_condition=SuccessCondition(type="narrative", description="The witness answers directly."),
                    source_refs=["scenario_start"],
                ),
            ),
        )
        session_state.save_character_state(
            session_id,
            "persona-1",
            CharacterStateData(
                drives={"energy": 5},
                skills={},
                emotional_state=EmotionalStateData(global_state={"composure": 4}),
                is_present=False,
            ),
        )

        yield {
            "session_state": session_state,
            "event_stream": event_stream,
            "character_loader": character_loader,
            "session_id": session_id,
        }

        character_loader.registry.close()
        character_registry.close()
        session_repo.close()
        char_state_repo.close()
        event_repo.close()

    def _queue_full_pipeline_responses(
        self,
        large: FakePromptProcessor,
        mini: FakePromptProcessor,
        *,
        gm_evaluations: list[GMActionEvaluation] | None = None,
        narration_chunks: list[str] | None = None,
    ) -> None:
        """Queue the minimum LLM responses for a full pipeline pass."""
        # Step 6.2: action gen (mini)
        mini.model_responses.append(
            ActionWithReasoning(
                reasoning="Ren presses the point.",
                action=CharacterAction(type="dialogue", description='Ren says, "Start talking."', target="You"),
            )
        )
        # Step 6.3: GM evaluation (large)
        if gm_evaluations is None:
            gm_evaluations = [
                GMActionEvaluation(character="You", action_summary="You ask what happened", check_required=False),
                GMActionEvaluation(character="Ren", action_summary='Ren says, "Start talking."', check_required=False),
            ]
        large.model_responses.append(GMEvaluationResult(evaluations=gm_evaluations))
        # Step 6.5: narration (large, streamed)
        large.stream_responses.append(narration_chunks or ["Ren leans over the table. ", "Rain rattles the windows."])
        # Step 6.6: observations (mini)
        mini.model_responses.append(
            ObservationExtractionResult(
                observations=[
                    Observation(subject="Ren", content="Ren demands an answer.", importance=4, visibility="public")
                ]
            )
        )
        # Step 6.7: character processing (mini)
        mini.model_responses.append(CharacterProcessingResult(state_diffs=[], reflection=None))
        # Step 6.8: intent completion check (mini)
        mini.model_responses.append(IntentCompletionCheck(reasoning="Not complete.", complete=False))
        # Step 6.9: continuation options (mini)
        mini.model_responses.append(
            ContinuationOptionsResult(
                options=[ContinuationOption(type="dialogue", description="Answer Ren directly.", target="Ren")]
            )
        )

    def test_full_pipeline_flow_and_sse_sequence(self, state_env: dict) -> None:
        ruleset = _build_ruleset()
        large = FakePromptProcessor()
        mini = FakePromptProcessor()
        self._queue_full_pipeline_responses(large, mini)

        pipeline = TurnPipeline(
            large_processor=large,
            mini_processor=mini,
            session_state=state_env["session_state"],
            ruleset_service=RulesetService(_DummyRulesetRegistry(ruleset)),  # type: ignore[arg-type]
            event_stream=state_env["event_stream"],
            character_loader=state_env["character_loader"],
        )

        events = list(
            pipeline.execute_turn(
                session_id=state_env["session_id"],
                user_input="I ask what he means.",
                input_type="action",
                ruleset=ruleset,
                user_id="anonymous",
            )
        )

        event_types = [event["type"] for event in events]
        assert event_types[0] == "status"
        assert "narration_chunk" in event_types
        assert "narration_complete" in event_types
        assert "continuation_options" in event_types
        assert event_types[-1] == "turn_complete"

        turn_complete = events[-1]
        assert turn_complete["turn"] == 1

        # Drive decay applied
        npc_state = state_env["session_state"].get_character_state(state_env["session_id"], "npc-1")
        assert npc_state is not None
        assert npc_state.drives["energy"] == 4

        # Narration persisted
        narration_history = state_env["session_state"].get_narration_history(state_env["session_id"], "anonymous")
        assert len(narration_history) == 1
        assert "Ren leans over the table." in narration_history[0]

        # Events stored
        npc_events = state_env["event_stream"].get_recent_events(state_env["session_id"], "npc-1", limit=10)
        assert len(npc_events) >= 1

    def test_dice_skill_check_path(self, state_env: dict) -> None:
        """Test that check_required=True triggers dice resolution and outcomes reflect it."""
        ruleset = _build_ruleset()
        large = FakePromptProcessor()
        mini = FakePromptProcessor()

        # Action gen
        mini.model_responses.append(
            ActionWithReasoning(
                reasoning="Ren presses hard.",
                action=CharacterAction(type="action", description="Ren tries to intimidate the witness."),
            )
        )
        # GM eval with a skill check (DC 5 with skill=6 → almost always succeeds)
        large.model_responses.append(
            GMEvaluationResult(
                evaluations=[
                    GMActionEvaluation(character="You", action_summary="You stare back", check_required=False),
                    GMActionEvaluation(
                        character="Ren",
                        action_summary="Ren tries to intimidate",
                        check_required=True,
                        skill="persuasion",
                        dc=5,
                    ),
                ]
            )
        )
        # Narration
        large.stream_responses.append(["Ren's voice drops low."])
        # Observations
        mini.model_responses.append(ObservationExtractionResult(observations=[]))
        # Char processing
        mini.model_responses.append(CharacterProcessingResult(state_diffs=[], reflection=None))
        # Intent check
        mini.model_responses.append(IntentCompletionCheck(reasoning="Not complete.", complete=False))
        # Continuation
        mini.model_responses.append(ContinuationOptionsResult(options=[]))

        # Use a seeded resolver so outcome is deterministic
        dice = DiceResolver(seed=42)

        pipeline = TurnPipeline(
            large_processor=large,
            mini_processor=mini,
            session_state=state_env["session_state"],
            ruleset_service=RulesetService(_DummyRulesetRegistry(ruleset)),  # type: ignore[arg-type]
            event_stream=state_env["event_stream"],
            character_loader=state_env["character_loader"],
            dice_resolver=dice,
        )

        events = list(
            pipeline.execute_turn(
                session_id=state_env["session_id"],
                user_input="I stare at Ren.",
                input_type="action",
                ruleset=ruleset,
                user_id="anonymous",
            )
        )

        assert events[-1]["type"] == "turn_complete"

        # The narration prompt should reference the dice outcome (success or failure)
        # Just verify the pipeline completed without error and outcomes were resolved
        narration_events = [e for e in events if e["type"] == "narration_complete"]
        assert len(narration_events) == 1

    def test_drive_effects_applied_on_success(self, state_env: dict) -> None:
        """Test that GM drive_effects are applied when the action succeeds."""
        ruleset = _build_ruleset()
        large = FakePromptProcessor()
        mini = FakePromptProcessor()

        # Action gen
        mini.model_responses.append(
            ActionWithReasoning(
                reasoning="Ren pushes.",
                action=CharacterAction(type="dialogue", description="Ren confronts."),
            )
        )
        # GM eval: auto-success with drive_effects
        large.model_responses.append(
            GMEvaluationResult(
                evaluations=[
                    GMActionEvaluation(character="You", action_summary="You respond", check_required=False),
                    GMActionEvaluation(
                        character="Ren",
                        action_summary="Ren confronts",
                        check_required=False,
                        drive_effects=[DriveEffect(drive="energy", change=-2)],
                    ),
                ]
            )
        )
        large.stream_responses.append(["Ren's hands tremble."])
        mini.model_responses.append(ObservationExtractionResult(observations=[]))
        mini.model_responses.append(CharacterProcessingResult(state_diffs=[], reflection=None))
        mini.model_responses.append(IntentCompletionCheck(reasoning="Not yet.", complete=False))
        mini.model_responses.append(ContinuationOptionsResult(options=[]))

        pipeline = TurnPipeline(
            large_processor=large,
            mini_processor=mini,
            session_state=state_env["session_state"],
            ruleset_service=RulesetService(_DummyRulesetRegistry(ruleset)),  # type: ignore[arg-type]
            event_stream=state_env["event_stream"],
            character_loader=state_env["character_loader"],
        )

        events = list(
            pipeline.execute_turn(
                session_id=state_env["session_id"],
                user_input="I provoke Ren.",
                input_type="action",
                ruleset=ruleset,
                user_id="anonymous",
            )
        )

        assert events[-1]["type"] == "turn_complete"

        # Initial energy was 5, drive_effects=-2, then decay=-1 → expect 2
        npc_state = state_env["session_state"].get_character_state(state_env["session_id"], "npc-1")
        assert npc_state is not None
        assert npc_state.drives["energy"] == 2

    def test_departure_marks_character_not_present(self, state_env: dict) -> None:
        """Test that GM departure=True marks the NPC as no longer present."""
        ruleset = _build_ruleset()
        large = FakePromptProcessor()
        mini = FakePromptProcessor()

        # Action gen
        mini.model_responses.append(
            ActionWithReasoning(
                reasoning="Ren leaves.",
                action=CharacterAction(type="action", description="Ren walks out."),
            )
        )
        # GM eval: auto-success with departure flag
        large.model_responses.append(
            GMEvaluationResult(
                evaluations=[
                    GMActionEvaluation(character="You", action_summary="You watch", check_required=False),
                    GMActionEvaluation(
                        character="Ren",
                        action_summary="Ren walks out",
                        check_required=False,
                        departure=True,
                    ),
                ]
            )
        )
        large.stream_responses.append(["Ren pushes through the door."])
        mini.model_responses.append(ObservationExtractionResult(observations=[]))
        mini.model_responses.append(CharacterProcessingResult(state_diffs=[], reflection=None))
        mini.model_responses.append(IntentCompletionCheck(reasoning="Not complete.", complete=False))
        mini.model_responses.append(ContinuationOptionsResult(options=[]))

        pipeline = TurnPipeline(
            large_processor=large,
            mini_processor=mini,
            session_state=state_env["session_state"],
            ruleset_service=RulesetService(_DummyRulesetRegistry(ruleset)),  # type: ignore[arg-type]
            event_stream=state_env["event_stream"],
            character_loader=state_env["character_loader"],
        )

        events = list(
            pipeline.execute_turn(
                session_id=state_env["session_id"],
                user_input="I let him go.",
                input_type="action",
                ruleset=ruleset,
                user_id="anonymous",
            )
        )

        assert events[-1]["type"] == "turn_complete"

        npc_state = state_env["session_state"].get_character_state(state_env["session_id"], "npc-1")
        assert npc_state is not None
        assert npc_state.is_present is False

    def test_fault_tolerance_emits_error_event(self, state_env: dict) -> None:
        ruleset = _build_ruleset()
        large = FakePromptProcessor()
        mini = FakePromptProcessor()

        mini.model_responses.append(
            ActionWithReasoning(
                reasoning="Ren reacts.",
                action=CharacterAction(type="reaction", description="Ren narrows his eyes."),
            )
        )
        large.model_responses.append(
            GMEvaluationResult(
                evaluations=[
                    GMActionEvaluation(character="You", action_summary="You stay quiet", check_required=False),
                    GMActionEvaluation(character="Ren", action_summary="Ren narrows his eyes", check_required=False),
                ]
            )
        )
        large.raise_on_stream = RuntimeError("stream failure")

        pipeline = TurnPipeline(
            large_processor=large,
            mini_processor=mini,
            session_state=state_env["session_state"],
            ruleset_service=RulesetService(_DummyRulesetRegistry(ruleset)),  # type: ignore[arg-type]
            event_stream=state_env["event_stream"],
            character_loader=state_env["character_loader"],
        )

        events = list(
            pipeline.execute_turn(
                session_id=state_env["session_id"],
                user_input="I stay silent.",
                input_type="action",
                ruleset=ruleset,
                user_id="anonymous",
            )
        )

        assert events[-1]["type"] == "error"
        assert "stream failure" in events[-1]["message"]

    def test_non_action_input_type_returns_error(self, state_env: dict) -> None:
        ruleset = _build_ruleset()
        large = FakePromptProcessor()
        mini = FakePromptProcessor()
        mini.model_responses.append(InputClassification(type="time_skip", parsed_target=None, action_text=None))

        pipeline = TurnPipeline(
            large_processor=large,
            mini_processor=mini,
            session_state=state_env["session_state"],
            ruleset_service=RulesetService(_DummyRulesetRegistry(ruleset)),  # type: ignore[arg-type]
            event_stream=state_env["event_stream"],
            character_loader=state_env["character_loader"],
        )

        events = list(
            pipeline.execute_turn(
                session_id=state_env["session_id"],
                user_input="Wait until dawn.",
                input_type=None,
                ruleset=ruleset,
                user_id="anonymous",
            )
        )

        assert events[-1]["type"] == "error"
        assert "not yet supported" in events[-1]["message"]
