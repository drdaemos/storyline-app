"""M4: runtime engine — scripted playthroughs of the worked example, determinism, replay."""

import pytest

from src.models.vn import (
    CheckResolved,
    EndingReached,
    SceneEntered,
    Script,
    VNAction,
    VNRuntimeState,
    WentDeeper,
)
from src.vn.engine import VNEngine, VNRuntimeError


class StubResolver:
    """Returns scripted rolls in order."""

    def __init__(self, rolls: list[int]) -> None:
        self.rolls = list(rolls)

    def roll(self) -> int:
        return self.rolls.pop(0)


def proceed() -> VNAction:
    return VNAction(type="proceed")


def choose(index: int) -> VNAction:
    return VNAction(type="choose", option_index=index)


def go_deeper() -> VNAction:
    return VNAction(type="go_deeper")


def option_intents(engine: VNEngine) -> list[str]:
    view = engine.view()
    assert view.pending is not None and view.pending.kind == "choice"
    return [option.intent for option in view.pending.options]


class TestStartAndExtension:
    def test_start_runs_to_extension_offer(self, locked_granary: Script):
        engine = VNEngine.new(locked_granary)
        events = engine.start()
        assert isinstance(events[0], SceneEntered) and events[0].scene_id == "sc_gate"
        view = engine.view()
        assert view.beat_id == "b_approach"
        assert view.pending is not None and view.pending.kind == "extension"
        assert "guard" in view.pending.deeper_domain

    def test_go_deeper_is_outcome_neutral_micro_loop(self, locked_granary: Script):
        engine = VNEngine.new(locked_granary)
        engine.start()
        state_before = dict(engine.state.vars)
        events = engine.advance(go_deeper())
        assert len(events) == 1 and isinstance(events[0], WentDeeper)
        assert engine.state.vars == state_before
        assert engine.view().beat_id == "b_approach"  # still at the same beat
        events = engine.advance(go_deeper())  # may loop again
        assert isinstance(events[0], WentDeeper)

    def test_start_twice_rejected(self, locked_granary: Script):
        engine = VNEngine.new(locked_granary)
        engine.start()
        with pytest.raises(VNRuntimeError, match="already started"):
            engine.start()


class TestChoicesAndGating:
    def test_gated_option_hidden_until_unlocked(self, locked_granary: Script):
        engine = VNEngine.new(locked_granary)
        engine.start()
        engine.advance(proceed())
        assert option_intents(engine) == ["Persuade him", "Slip past while he is distracted"]
        engine.advance(choose(0))  # persuade: trust +1, loops back to the choice
        assert engine.state.vars["guard_trust"] == 1
        assert option_intents(engine) == [
            "Persuade him",
            "Slip past while he is distracted",
            "Mention his sister vouched for you",
        ]

    def test_effects_clamp_at_counter_max(self, locked_granary: Script):
        engine = VNEngine.new(locked_granary)
        engine.start()
        engine.advance(proceed())
        for _ in range(5):  # persuade loop: max 3
            engine.advance(choose(0))
        assert engine.state.vars["guard_trust"] == 3

    def test_invalid_option_index_rejected(self, locked_granary: Script):
        engine = VNEngine.new(locked_granary)
        engine.start()
        engine.advance(proceed())
        with pytest.raises(VNRuntimeError, match="out of range"):
            engine.advance(choose(7))


class TestChecks:
    def test_failure_then_modified_retry(self, locked_granary: Script):
        """Failed sneak sets injured; injured applies -2 on the retry (effect feeds a later check)."""
        engine = VNEngine.new(locked_granary, roll_resolver=StubResolver([5, 20]))
        engine.start()
        engine.advance(proceed())
        events = engine.advance(choose(1))  # sneak: roll 5 vs 12 -> fail -> caught (injured) -> back to talk
        check = next(e for e in events if isinstance(e, CheckResolved))
        assert (check.roll, check.modifier_total, check.success) == (5, 0, False)
        assert engine.state.vars["injured"] is True
        assert engine.view().beat_id == "b_talk"

        events = engine.advance(choose(1))  # retry: roll 20 - 2 = 18 vs 12 -> success
        check = next(e for e in events if isinstance(e, CheckResolved))
        assert (check.roll, check.modifier_total, check.success) == (20, -2, True)


class TestSceneTransitions:
    def test_forced_scene_preempts_open_exit(self, locked_granary: Script):
        """b_inside's open exit: sc_reckoning (forced, prereq visited(sc_gate)) wins over sc_granary."""
        engine = VNEngine.new(locked_granary, roll_resolver=StubResolver([20]))
        engine.start()
        engine.advance(proceed())
        events = engine.advance(choose(1))  # sneak succeeds -> b_inside -> open exit
        scene_entries = [e for e in events if isinstance(e, SceneEntered)]
        assert [e.scene_id for e in scene_entries] == ["sc_reckoning"]
        assert engine.view().beat_id == "b_confront"

    def test_playthrough_to_each_ending(self, locked_granary: Script):
        for option, expected_ending in [(0, "end_bargain"), (1, "end_flight")]:
            engine = VNEngine.new(locked_granary, roll_resolver=StubResolver([20]))
            engine.start()
            engine.advance(proceed())
            engine.advance(choose(1))  # sneak success -> forced sc_reckoning -> confront choice
            events = engine.advance(choose(option))
            ending = next(e for e in events if isinstance(e, EndingReached))
            assert ending.ending_id == expected_ending
            assert engine.view().status == "ended"
            assert engine.view().ending_id == expected_ending

    def test_vouched_path_sets_key_and_skips_check(self, locked_granary: Script):
        engine = VNEngine.new(locked_granary)
        engine.start()
        engine.advance(proceed())
        engine.advance(choose(0))  # persuade -> trust 1
        engine.advance(choose(2))  # vouched -> has_key -> b_inside -> forced sc_reckoning
        assert engine.state.vars["has_key"] is True
        assert engine.state.roll_count == 0  # no check on this path
        assert engine.view().beat_id == "b_confront"

    def test_advance_after_ending_rejected(self, locked_granary: Script):
        engine = VNEngine.new(locked_granary, roll_resolver=StubResolver([20]))
        engine.start()
        engine.advance(proceed())
        engine.advance(choose(1))
        engine.advance(choose(0))
        with pytest.raises(VNRuntimeError, match="ended"):
            engine.advance(choose(0))


class TestVisitedness:
    def test_visited_tracked_per_scene_and_beat(self, locked_granary: Script):
        engine = VNEngine.new(locked_granary)
        engine.start()
        visited = set(engine.view().visited)
        assert {"sc_gate", "b_approach"} <= visited
        assert "b_talk" not in visited


class TestDeterminismAndReplay:
    ACTIONS = [proceed(), choose(1)]  # sneak with the seeded resolver

    def play(self, script: Script, seed: int) -> VNEngine:
        engine = VNEngine.new(script, seed=seed)
        engine.start()
        for action in self.ACTIONS:
            engine.advance(action)
        return engine

    def test_same_seed_same_outcome(self, locked_granary: Script):
        first = self.play(locked_granary, seed=42)
        second = self.play(locked_granary, seed=42)
        assert first.state == second.state

    def test_resume_mid_session_continues_roll_sequence(self, locked_granary: Script):
        reference = self.play(locked_granary, seed=7)

        engine = VNEngine.new(locked_granary, seed=7)
        engine.start()
        engine.advance(proceed())
        snapshot = VNRuntimeState.model_validate(engine.state.model_dump())  # serialize + reload
        resumed = VNEngine(locked_granary, snapshot)  # resolver rebuilt from seed + roll_count
        resumed.advance(choose(1))
        assert resumed.state.vars == reference.state.vars
        assert resumed.state.current_beat == reference.state.current_beat

    def test_runtime_state_round_trips_through_json(self, locked_granary: Script):
        engine = self.play(locked_granary, seed=3)
        raw = engine.state.model_dump_json()
        restored = VNRuntimeState.model_validate_json(raw)
        assert restored == engine.state
