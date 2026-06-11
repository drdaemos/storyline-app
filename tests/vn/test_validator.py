"""M2: structural validator — one violating fixture per hard gate."""


from src.models.vn import Scene, Script
from src.vn.validator import validate_scene_structure, validate_script


def make_script(**overrides) -> Script:
    """A small valid two-scene script; tests mutate pieces of it to seed violations."""
    data = {
        "meta": {"title": "T", "protagonist": "P"},
        "state_vars": [
            {"name": "trust", "type": "counter", "max": 3, "initial": 0},
            {"name": "armed", "type": "flag", "initial": False},
            {"name": "mood", "type": "enum", "values": ["calm", "angry"], "initial": "calm"},
        ],
        "start_scene": "sc_a",
        "scenes": [
            {
                "id": "sc_a",
                "intent": "first scene",
                "entry_beat": "b_one",
                "beats": [
                    {
                        "id": "b_one",
                        "type": "choice",
                        "intent": "pick",
                        "options": [
                            {"intent": "go on", "target": "b_two"},
                            {"intent": "secret", "guard": [{"var": "trust", "op": ">=", "value": 2}], "target": "b_two"},
                        ],
                    },
                    {
                        "id": "b_two",
                        "type": "plain",
                        "intent": "leave",
                        "effects": [{"var": "trust", "op": "inc", "value": 1}],
                        "exit_edges": [
                            {"target_scene": "sc_b", "guard": [{"var": "armed", "op": "==", "value": True}], "priority": 2},
                            {"target_scene": "sc_b", "guard": [], "priority": 1},
                        ],
                    },
                ],
            },
            {
                "id": "sc_b",
                "intent": "final scene",
                "prerequisites": [{"visited": "sc_a"}],
                "entry_beat": "b_end",
                "beats": [{"id": "b_end", "type": "ending", "intent": "done", "ending_id": "end_1"}],
            },
        ],
    }
    data.update(overrides)
    return Script.model_validate(data)


def codes(script: Script) -> set[str]:
    return {issue.code for issue in validate_script(script).errors}


class TestValidScript:
    def test_base_fixture_valid(self):
        report = validate_script(make_script())
        assert report.valid, [issue.message for issue in report.issues]

    def test_worked_example_valid(self, locked_granary: Script):
        report = validate_script(locked_granary)
        assert report.valid, [issue.message for issue in report.issues]


class TestIdResolution:
    def test_unknown_start_scene(self):
        assert "unknown_start_scene" in codes(make_script(start_scene="sc_missing"))

    def test_duplicate_scene_id(self):
        script = make_script()
        data = script.model_dump()
        data["scenes"][1]["id"] = "sc_a"
        # second sc_a now unreferenced by exit edge? edge targets sc_b -> unknown_scene_ref too; both flagged
        report_codes = {i.code for i in validate_script(Script.model_validate(data)).errors}
        assert "duplicate_scene_id" in report_codes

    def test_duplicate_beat_id_across_scenes(self):
        script = make_script()
        data = script.model_dump()
        data["scenes"][1]["beats"][0]["id"] = "b_one"
        data["scenes"][1]["entry_beat"] = "b_one"
        assert "duplicate_beat_id" in {i.code for i in validate_script(Script.model_validate(data)).errors}

    def test_unknown_entry_beat(self):
        data = make_script().model_dump()
        data["scenes"][0]["entry_beat"] = "b_ghost"
        assert "unknown_entry_beat" in {i.code for i in validate_script(Script.model_validate(data)).errors}

    def test_unknown_in_scene_beat_ref(self):
        data = make_script().model_dump()
        data["scenes"][0]["beats"][0]["options"][0]["target"] = "b_ghost"
        assert "unknown_beat_ref" in {i.code for i in validate_script(Script.model_validate(data)).errors}

    def test_unknown_exit_scene_ref(self):
        data = make_script().model_dump()
        data["scenes"][0]["beats"][1]["exit_edges"][1]["target_scene"] = "sc_ghost"
        assert "unknown_scene_ref" in {i.code for i in validate_script(Script.model_validate(data)).errors}

    def test_unknown_visited_ref(self):
        data = make_script().model_dump()
        data["scenes"][1]["prerequisites"] = [{"visited": "sc_ghost"}]
        assert "unknown_visited_ref" in {i.code for i in validate_script(Script.model_validate(data)).errors}


class TestRoutingRules:
    def test_equal_exit_priorities(self):
        data = make_script().model_dump()
        data["scenes"][0]["beats"][1]["exit_edges"][1]["priority"] = 2
        assert "equal_exit_priorities" in {i.code for i in validate_script(Script.model_validate(data)).errors}

    def test_duplicate_forced_priority_is_warning(self):
        data = make_script().model_dump()
        data["scenes"][0]["forced"] = 1
        data["scenes"][1]["forced"] = 1
        report = validate_script(Script.model_validate(data))
        assert report.valid  # warning, not error
        assert "duplicate_forced_priority" in {i.code for i in report.issues}


class TestNonGatedPathInvariant:
    def test_gated_only_path_flagged(self):
        """Sole route forward sits behind a guard -> invariant violation."""
        data = make_script().model_dump()
        data["scenes"][0]["beats"][0]["options"] = [
            {"intent": "secret", "guard": [{"var": "trust", "op": ">=", "value": 2}], "target": "b_two"},
        ]
        assert "no_non_gated_path" in {i.code for i in validate_script(Script.model_validate(data)).errors}

    def test_check_is_not_a_gate(self):
        """Both check outcomes count as non-gated; a scene whose only path runs through a check passes."""
        data = make_script().model_dump()
        data["scenes"][0]["beats"][0] = {
            "id": "b_one",
            "type": "check",
            "intent": "try it",
            "check": {"difficulty": 10, "on_success": "b_two", "on_failure": "b_two"},
        }
        report = validate_script(Script.model_validate(data))
        assert report.valid, [issue.message for issue in report.issues]

    def test_scene_local_validation_entry_point(self):
        scene = Scene.model_validate(
            {
                "id": "sc_x",
                "intent": "x",
                "entry_beat": "b_1",
                "beats": [
                    {
                        "id": "b_1",
                        "type": "choice",
                        "intent": "x",
                        "options": [{"intent": "locked", "guard": [{"var": "v", "op": "==", "value": True}], "target": "b_2"}],
                    },
                    {"id": "b_2", "type": "ending", "intent": "x", "ending_id": "e"},
                ],
            }
        )
        report = validate_scene_structure(scene)
        assert "no_non_gated_path" in {i.code for i in report.errors}


class TestVarDomains:
    def test_undeclared_var_in_guard(self):
        data = make_script().model_dump()
        data["scenes"][0]["beats"][0]["options"][1]["guard"] = [{"var": "ghost", "op": "==", "value": 1}]
        assert "unknown_var_ref" in {i.code for i in validate_script(Script.model_validate(data)).errors}

    def test_undeclared_var_in_effect(self):
        data = make_script().model_dump()
        data["scenes"][0]["beats"][1]["effects"] = [{"var": "ghost", "op": "set", "value": True}]
        assert "unknown_var_ref" in {i.code for i in validate_script(Script.model_validate(data)).errors}

    def test_ordered_comparison_on_flag(self):
        data = make_script().model_dump()
        data["scenes"][0]["beats"][0]["options"][1]["guard"] = [{"var": "armed", "op": ">=", "value": True}]
        assert "invalid_condition_op" in {i.code for i in validate_script(Script.model_validate(data)).errors}

    def test_condition_value_out_of_domain(self):
        data = make_script().model_dump()
        data["scenes"][0]["beats"][0]["options"][1]["guard"] = [{"var": "mood", "op": "==", "value": "ecstatic"}]
        assert "condition_value_out_of_domain" in {i.code for i in validate_script(Script.model_validate(data)).errors}

    def test_counter_condition_above_max(self):
        data = make_script().model_dump()
        data["scenes"][0]["beats"][0]["options"][1]["guard"] = [{"var": "trust", "op": "==", "value": 99}]
        assert "condition_value_out_of_domain" in {i.code for i in validate_script(Script.model_validate(data)).errors}

    def test_inc_on_enum(self):
        data = make_script().model_dump()
        data["scenes"][0]["beats"][1]["effects"] = [{"var": "mood", "op": "inc", "value": 1}]
        assert "invalid_effect" in {i.code for i in validate_script(Script.model_validate(data)).errors}

    def test_enum_effect_out_of_domain(self):
        data = make_script().model_dump()
        data["scenes"][0]["beats"][1]["effects"] = [{"var": "mood", "op": "set", "value": "ecstatic"}]
        assert "invalid_effect" in {i.code for i in validate_script(Script.model_validate(data)).errors}

    def test_check_modifier_undeclared_var(self):
        data = make_script().model_dump()
        data["scenes"][0]["beats"][0] = {
            "id": "b_one",
            "type": "check",
            "intent": "try",
            "check": {
                "difficulty": 10,
                "modifiers": [{"var": "ghost", "op": "==", "value": True, "mod": -2}],
                "on_success": "b_two",
                "on_failure": "b_two",
            },
        }
        assert "unknown_var_ref" in {i.code for i in validate_script(Script.model_validate(data)).errors}


class TestDuplicateStateVar:
    def test_duplicate_state_var(self):
        data = make_script().model_dump()
        data["state_vars"].append({"name": "trust", "type": "flag", "initial": False})
        assert "duplicate_state_var" in {i.code for i in validate_script(Script.model_validate(data)).errors}

