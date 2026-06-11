"""M1: script schema model tests — shape validation and round-trips."""

import pytest
from pydantic import ValidationError

from src.models.vn import (
    CheckBeat,
    ChoiceBeat,
    EndingBeat,
    PlainBeat,
    Script,
    VNInput,
)
from src.models.vn.script import DraftPlainBeat


class TestWorkedExample:
    def test_parses(self, locked_granary: Script):
        assert locked_granary.meta.title == "The Locked Granary"
        assert locked_granary.start_scene == "sc_gate"
        assert len(locked_granary.scenes) == 3
        assert len(locked_granary.state_vars) == 3

    def test_beat_types_resolved(self, locked_granary: Script):
        gate = locked_granary.scenes[0]
        by_id = {b.id: b for b in gate.beats}
        assert isinstance(by_id["b_approach"], PlainBeat)
        assert isinstance(by_id["b_talk"], ChoiceBeat)
        assert isinstance(by_id["b_sneak"], CheckBeat)
        endings = [b for b in locked_granary.scenes[2].beats if isinstance(b, EndingBeat)]
        assert {b.ending_id for b in endings} == {"end_bargain", "end_flight"}

    def test_round_trip(self, locked_granary: Script):
        dumped = locked_granary.model_dump()
        reparsed = Script.model_validate(dumped)
        assert reparsed == locked_granary

    def test_extension_point_marked(self, locked_granary: Script):
        approach = locked_granary.scenes[0].beats[0]
        assert approach.extension is not None
        assert "guard" in approach.extension.deeper_domain

    def test_open_exit_and_exit_edges(self, locked_granary: Script):
        inside = locked_granary.scenes[0].beats[-1]
        assert isinstance(inside, PlainBeat)
        assert inside.exit == "open"
        search = locked_granary.scenes[1].beats[0]
        assert isinstance(search, PlainBeat)
        assert search.exit_edges is not None
        assert [e.priority for e in search.exit_edges] == [2, 1]


class TestStateVarDomains:
    def test_counter_initial_above_max_rejected(self):
        with pytest.raises(ValidationError, match="outside domain"):
            Script.model_validate(_minimal_script(state_vars=[{"name": "x", "type": "counter", "max": 3, "initial": 5}]))

    def test_counter_negative_initial_rejected(self):
        with pytest.raises(ValidationError):
            Script.model_validate(_minimal_script(state_vars=[{"name": "x", "type": "counter", "max": 3, "initial": -1}]))

    def test_enum_initial_not_in_values_rejected(self):
        with pytest.raises(ValidationError, match="not in values"):
            Script.model_validate(_minimal_script(state_vars=[{"name": "x", "type": "enum", "values": ["a", "b"], "initial": "c"}]))

    def test_enum_duplicate_values_rejected(self):
        with pytest.raises(ValidationError, match="duplicate"):
            Script.model_validate(_minimal_script(state_vars=[{"name": "x", "type": "enum", "values": ["a", "a"], "initial": "a"}]))

    def test_unknown_var_type_rejected(self):
        with pytest.raises(ValidationError):
            Script.model_validate(_minimal_script(state_vars=[{"name": "x", "type": "gauge", "initial": 0}]))


class TestBeatRouting:
    def test_plain_beat_with_two_routings_rejected(self):
        beat = {"id": "b1", "type": "plain", "intent": "x", "next": "b2", "exit": "open"}
        with pytest.raises(ValidationError, match="exactly one"):
            Script.model_validate(_minimal_script(beats=[beat]))

    def test_plain_beat_with_no_routing_rejected(self):
        beat = {"id": "b1", "type": "plain", "intent": "x"}
        with pytest.raises(ValidationError, match="exactly one"):
            Script.model_validate(_minimal_script(beats=[beat]))

    def test_plain_beat_with_empty_exit_edges_rejected(self):
        beat = {"id": "b1", "type": "plain", "intent": "x", "exit_edges": []}
        with pytest.raises(ValidationError, match="must not be empty"):
            Script.model_validate(_minimal_script(beats=[beat]))

    def test_choice_beat_without_options_rejected(self):
        beat = {"id": "b1", "type": "choice", "intent": "x", "options": []}
        with pytest.raises(ValidationError):
            Script.model_validate(_minimal_script(beats=[beat]))

    def test_check_beat_requires_both_outcomes(self):
        beat = {"id": "b1", "type": "check", "intent": "x", "check": {"difficulty": 10, "on_success": "b2"}}
        with pytest.raises(ValidationError):
            Script.model_validate(_minimal_script(beats=[beat]))

    def test_ending_beat_with_routing_rejected(self):
        beat = {"id": "b1", "type": "ending", "intent": "x", "ending_id": "end", "next": "b2"}
        with pytest.raises(ValidationError):
            Script.model_validate(_minimal_script(beats=[beat]))

    def test_unknown_field_rejected(self):
        beat = {"id": "b1", "type": "plain", "intent": "x", "next": "b2", "prose": "hello"}
        with pytest.raises(ValidationError):
            Script.model_validate(_minimal_script(beats=[beat]))

    def test_draft_plain_beat_with_no_routing_rejected(self):
        # The slim DraftPlainBeat must mirror PlainBeat's routing contract so a
        # malformed draft fails at parse time (caught by request_model → repair loop)
        # rather than later when lifted into a canonical Scene, where it would escape.
        with pytest.raises(ValidationError, match="exactly one"):
            DraftPlainBeat.model_validate({"id": "b1", "type": "plain", "intent": "x"})

    def test_draft_plain_beat_with_two_routings_rejected(self):
        with pytest.raises(ValidationError, match="exactly one"):
            DraftPlainBeat.model_validate({"id": "b1", "type": "plain", "intent": "x", "next": "b2", "exit": "open"})

    def test_draft_plain_beat_with_empty_exit_edges_rejected(self):
        with pytest.raises(ValidationError, match="must not be empty"):
            DraftPlainBeat.model_validate({"id": "b1", "type": "plain", "intent": "x", "exit_edges": []})

    def test_draft_plain_beat_single_routing_accepted(self):
        beat = DraftPlainBeat.model_validate({"id": "b1", "type": "plain", "intent": "x", "next": "b2"})
        assert beat.next == "b2"


class TestConditions:
    def test_visited_condition_default_true(self, locked_granary: Script):
        prereq = locked_granary.scenes[2].prerequisites[0]
        assert prereq.value is True

    def test_invalid_op_rejected(self):
        beat = {
            "id": "b1",
            "type": "choice",
            "intent": "x",
            "options": [{"intent": "go", "guard": [{"var": "v", "op": "!=", "value": 1}], "target": "b1"}],
        }
        with pytest.raises(ValidationError):
            Script.model_validate(_minimal_script(beats=[beat]))

    def test_var_and_visited_conditions_in_one_guard(self):
        """The two guard forms are one object type distinguished by which field is set."""
        beat = {
            "id": "b1",
            "type": "choice",
            "intent": "x",
            "options": [
                {
                    "intent": "go",
                    "guard": [{"var": "v", "op": "==", "value": 1}, {"visited": "b1", "value": False}],
                    "target": "b1",
                }
            ],
        }
        scene = Script.model_validate(_minimal_script(state_vars=[{"name": "v", "type": "counter", "max": 3}], beats=[beat])).scenes[0]
        guard = scene.beats[0].options[0].guard
        assert guard[0].is_var and guard[0].var == "v" and guard[0].op == "=="
        assert guard[1].is_visited and guard[1].visited == "b1" and guard[1].value is False

    def test_condition_with_neither_form_rejected(self):
        beat = {"id": "b1", "type": "choice", "intent": "x", "options": [{"intent": "go", "guard": [{"value": 1}], "target": "b1"}]}
        with pytest.raises(ValidationError, match="exactly one of 'var' or 'visited'"):
            Script.model_validate(_minimal_script(beats=[beat]))

    def test_condition_with_both_forms_rejected(self):
        guard = [{"var": "v", "op": "==", "value": 1, "visited": "b1"}]
        beat = {"id": "b1", "type": "choice", "intent": "x", "options": [{"intent": "go", "guard": guard, "target": "b1"}]}
        with pytest.raises(ValidationError, match="exactly one of 'var' or 'visited'"):
            Script.model_validate(_minimal_script(state_vars=[{"name": "v", "type": "counter", "max": 3}], beats=[beat]))

    def test_var_condition_without_op_rejected(self):
        guard = [{"var": "v", "value": 1}]
        beat = {"id": "b1", "type": "choice", "intent": "x", "options": [{"intent": "go", "guard": guard, "target": "b1"}]}
        with pytest.raises(ValidationError, match="requires an 'op'"):
            Script.model_validate(_minimal_script(state_vars=[{"name": "v", "type": "counter", "max": 3}], beats=[beat]))

    def test_check_modifiers_are_conditions_with_mod(self):
        beat = {
            "id": "b1",
            "type": "check",
            "intent": "x",
            "check": {
                "difficulty": 10,
                "modifiers": [{"var": "v", "op": "==", "value": 1, "mod": -2}, {"visited": "b1", "mod": 1}],
                "on_success": "b1",
                "on_failure": "b1",
            },
        }
        scene = Script.model_validate(_minimal_script(state_vars=[{"name": "v", "type": "counter", "max": 3}], beats=[beat])).scenes[0]
        modifiers = scene.beats[0].check.modifiers
        assert modifiers[0].is_var and modifiers[0].mod == -2
        assert modifiers[1].is_visited and modifiers[1].mod == 1

    def test_guard_arrays_carry_no_object_union(self):
        """The grammar fix: guard arrays must reference a single Condition object, not an
        object union per element — an array-element object union is what overflowed Anthropic's
        compiled structured-output grammar ("compiled grammar is too large")."""
        schema = Script.model_json_schema()
        guard_items = schema["$defs"]["ExitEdge"]["properties"]["guard"]["items"]
        assert guard_items == {"$ref": "#/$defs/Condition"}
        modifier_items = schema["$defs"]["CheckSpec"]["properties"]["modifiers"]["items"]
        assert modifier_items == {"$ref": "#/$defs/CheckModifier"}


class TestVNInput:
    def test_valid_input(self):
        vn_input = VNInput.model_validate(_minimal_input())
        assert vn_input.premise.scope.target_scenes == 8

    def test_no_protagonist_rejected(self):
        data = _minimal_input()
        data["characters"][0]["protagonist"] = False
        with pytest.raises(ValidationError, match="protagonist"):
            VNInput.model_validate(data)

    def test_two_protagonists_rejected(self):
        data = _minimal_input()
        data["characters"].append({"name": "Bob", "protagonist": True})
        with pytest.raises(ValidationError, match="protagonist"):
            VNInput.model_validate(data)


def _minimal_script(state_vars: list | None = None, beats: list | None = None) -> dict:
    if beats is None:
        beats = [{"id": "b1", "type": "ending", "intent": "the end", "ending_id": "end_1"}]
    return {
        "meta": {"title": "T", "protagonist": "P"},
        "state_vars": state_vars or [],
        "start_scene": "sc_1",
        "scenes": [
            {
                "id": "sc_1",
                "intent": "scene intent",
                "entry_beat": beats[0]["id"],
                "beats": beats,
            }
        ],
    }


def _minimal_input() -> dict:
    return {
        "characters": [{"name": "Mara", "background": "a thief", "protagonist": True}],
        "setting": {"world_description": "a small town"},
        "rules": "low fantasy, no gore",
        "premise": {
            "synopsis": "steal the ledger",
            "protagonist_goal": "clear her name",
            "scope": {"target_scenes": 8, "target_endings": 3},
        },
    }
