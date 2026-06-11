"""M3: softlock checker — seeded softlocks must be caught with correct witnesses."""

from src.models.vn import Script
from src.vn.softlock import check_softlocks


def make(scenes: list[dict], state_vars: list[dict] | None = None, start: str | None = None) -> Script:
    return Script.model_validate(
        {
            "meta": {"title": "T", "protagonist": "P"},
            "state_vars": state_vars or [],
            "start_scene": start or scenes[0]["id"],
            "scenes": scenes,
        }
    )


class TestWorkedExample:
    def test_no_errors(self, locked_granary: Script):
        report = check_softlocks(locked_granary)
        assert report.valid, [issue.message for issue in report.errors]

    def test_both_endings_reachable(self, locked_granary: Script):
        report = check_softlocks(locked_granary)
        assert "unreached_ending" not in {issue.code for issue in report.issues}


class TestSoftlockDetection:
    def test_endless_cycle_flagged(self):
        script = make(
            [
                {
                    "id": "sc_a",
                    "intent": "x",
                    "entry_beat": "b1",
                    "beats": [
                        {"id": "b1", "type": "plain", "intent": "x", "next": "b2"},
                        {"id": "b2", "type": "plain", "intent": "x", "next": "b1"},
                    ],
                }
            ]
        )
        report = check_softlocks(script)
        flagged = {issue.beat_id for issue in report.errors if issue.code == "softlock"}
        assert flagged == {"b1", "b2"}

    def test_check_failure_branch_dead_cycle(self):
        """Both check outcomes are explored; the failure branch loops forever -> softlock there only."""
        script = make(
            [
                {
                    "id": "sc_a",
                    "intent": "x",
                    "entry_beat": "b_check",
                    "beats": [
                        {
                            "id": "b_check",
                            "type": "check",
                            "intent": "x",
                            "check": {"difficulty": 10, "on_success": "b_end", "on_failure": "b_loop"},
                        },
                        {"id": "b_loop", "type": "plain", "intent": "x", "next": "b_loop"},
                        {"id": "b_end", "type": "ending", "intent": "x", "ending_id": "end_ok"},
                    ],
                }
            ]
        )
        report = check_softlocks(script)
        softlocked = {issue.beat_id for issue in report.errors if issue.code == "softlock"}
        assert softlocked == {"b_loop"}

    def test_all_options_gated_dead_end_with_state_witness(self):
        script = make(
            [
                {
                    "id": "sc_a",
                    "intent": "x",
                    "entry_beat": "b1",
                    "beats": [
                        {
                            "id": "b1",
                            "type": "choice",
                            "intent": "x",
                            "options": [{"intent": "locked", "guard": [{"var": "key", "op": "==", "value": True}], "target": "b_end"}],
                        },
                        {"id": "b_end", "type": "ending", "intent": "x", "ending_id": "end_ok"},
                    ],
                }
            ],
            state_vars=[{"name": "key", "type": "flag", "initial": False}],
        )
        report = check_softlocks(script)
        dead_ends = [issue for issue in report.errors if issue.code == "dead_end"]
        assert len(dead_ends) == 1
        assert dead_ends[0].beat_id == "b1"
        assert dead_ends[0].state == {"key": False}
        assert "unreached_ending" in {issue.code for issue in report.issues}

    def test_empty_open_exit_pool(self):
        """Once-only: the only scene is already visited when its open exit fires."""
        script = make(
            [
                {
                    "id": "sc_a",
                    "intent": "x",
                    "entry_beat": "b1",
                    "beats": [{"id": "b1", "type": "plain", "intent": "x", "exit": "open"}],
                }
            ]
        )
        report = check_softlocks(script)
        dead_ends = [issue for issue in report.errors if issue.code == "dead_end"]
        assert len(dead_ends) == 1
        assert "empty scene pool" in dead_ends[0].message

    def test_no_eligible_exit_edge(self):
        script = make(
            [
                {
                    "id": "sc_a",
                    "intent": "x",
                    "entry_beat": "b1",
                    "beats": [
                        {
                            "id": "b1",
                            "type": "plain",
                            "intent": "x",
                            "exit_edges": [{"target_scene": "sc_b", "guard": [{"var": "key", "op": "==", "value": True}], "priority": 1}],
                        }
                    ],
                },
                {
                    "id": "sc_b",
                    "intent": "x",
                    "entry_beat": "b_end",
                    "beats": [{"id": "b_end", "type": "ending", "intent": "x", "ending_id": "end_ok"}],
                },
            ],
            state_vars=[{"name": "key", "type": "flag", "initial": False}],
        )
        report = check_softlocks(script)
        assert "dead_end" in {issue.code for issue in report.errors}


class TestPoolSemantics:
    def test_visited_prereq_and_forced_preemption(self):
        """Open exit pool honors prerequisites, once-only exclusion, and forced preemption."""
        script = make(
            [
                {
                    "id": "sc_a",
                    "intent": "x",
                    "entry_beat": "b1",
                    "beats": [{"id": "b1", "type": "plain", "intent": "x", "exit": "open"}],
                },
                {
                    "id": "sc_b",
                    "intent": "x",
                    "entry_beat": "b2",
                    "beats": [{"id": "b2", "type": "plain", "intent": "x", "exit": "open"}],
                },
                {
                    "id": "sc_end",
                    "intent": "x",
                    "prerequisites": [{"visited": "sc_b"}],
                    "forced": 1,
                    "entry_beat": "b_end",
                    "beats": [{"id": "b_end", "type": "ending", "intent": "x", "ending_id": "end_ok"}],
                },
            ]
        )
        report = check_softlocks(script)
        assert report.valid, [issue.message for issue in report.errors]

    def test_equal_forced_priorities_flagged(self):
        script = make(
            [
                {
                    "id": "sc_a",
                    "intent": "x",
                    "entry_beat": "b1",
                    "beats": [{"id": "b1", "type": "plain", "intent": "x", "exit": "open"}],
                },
                {
                    "id": "sc_f1",
                    "intent": "x",
                    "forced": 1,
                    "entry_beat": "b_e1",
                    "beats": [{"id": "b_e1", "type": "ending", "intent": "x", "ending_id": "end_1"}],
                },
                {
                    "id": "sc_f2",
                    "intent": "x",
                    "forced": 1,
                    "entry_beat": "b_e2",
                    "beats": [{"id": "b_e2", "type": "ending", "intent": "x", "ending_id": "end_2"}],
                },
            ]
        )
        report = check_softlocks(script)
        ties = [issue for issue in report.errors if issue.code == "equal_forced_priorities"]
        assert len(ties) == 1
        assert ties[0].beat_id == "b1"


class TestBudget:
    def test_budget_exceeded_is_a_warning_not_an_error(self, locked_granary: Script):
        """Running out of budget means 'unverified', not 'broken' — it must not fail a gate."""
        report = check_softlocks(locked_granary, max_nodes=2)
        assert "state_space_budget_exceeded" in {issue.code for issue in report.issues}
        assert "state_space_budget_exceeded" not in {issue.code for issue in report.errors}
        assert report.valid

    def test_unreferenced_beats_do_not_blow_up_the_state_space(self):
        """Reconverging branches over beats no condition references must not multiply node
        identities: 12 chained diamonds have 4096 paths but only ~50 distinct routing states."""
        beats = []
        for i in range(12):
            beats.append({"id": f"b_choice_{i}", "type": "choice", "intent": "x", "options": [{"intent": "a", "target": f"b_left_{i}"}, {"intent": "b", "target": f"b_right_{i}"}]})
            beats.append({"id": f"b_left_{i}", "type": "plain", "intent": "x", "next": f"b_choice_{i + 1}" if i < 11 else "b_end"})
            beats.append({"id": f"b_right_{i}", "type": "plain", "intent": "x", "next": f"b_choice_{i + 1}" if i < 11 else "b_end"})
        beats.append({"id": "b_end", "type": "ending", "intent": "x", "ending_id": "end_1"})
        script = Script.model_validate(
            {
                "meta": {"title": "T", "protagonist": "P"},
                "state_vars": [],
                "start_scene": "sc_a",
                "scenes": [{"id": "sc_a", "intent": "x", "entry_beat": "b_choice_0", "beats": beats}],
            }
        )
        report = check_softlocks(script, max_nodes=200)
        assert report.valid, [issue.message for issue in report.errors]
        assert "state_space_budget_exceeded" not in {issue.code for issue in report.issues}
