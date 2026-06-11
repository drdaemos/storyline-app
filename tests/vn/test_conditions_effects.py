"""M2: condition evaluation and effect application (domain clamping)."""

import pytest

from src.models.vn import Condition, CounterVar, Effect, EnumVar, FlagVar
from src.vn.conditions import evaluate_condition, evaluate_guard
from src.vn.effects import apply_effect, apply_effects, declarations_by_name, initial_state

DECLS = declarations_by_name(
    [
        FlagVar(name="injured", initial=False),
        CounterVar(name="trust", max=3, initial=1),
        EnumVar(name="town", values=["calm", "alert"], initial="calm"),
    ]
)


class TestInitialState:
    def test_initials(self):
        state = initial_state(list(DECLS.values()))
        assert state == {"injured": False, "trust": 1, "town": "calm"}


class TestConditions:
    @pytest.mark.parametrize(
        ("condition", "expected"),
        [
            (Condition(var="injured", op="==", value=False), True),
            (Condition(var="injured", op="==", value=True), False),
            (Condition(var="trust", op=">=", value=1), True),
            (Condition(var="trust", op=">=", value=2), False),
            (Condition(var="trust", op="<=", value=1), True),
            (Condition(var="town", op="==", value="calm"), True),
        ],
    )
    def test_var_conditions(self, condition, expected):
        state = initial_state(list(DECLS.values()))
        assert evaluate_condition(condition, state, set()) is expected

    def test_visited_condition(self):
        state = initial_state(list(DECLS.values()))
        assert evaluate_condition(Condition(visited="sc_gate"), state, {"sc_gate"}) is True
        assert evaluate_condition(Condition(visited="sc_gate"), state, set()) is False
        assert evaluate_condition(Condition(visited="sc_gate", value=False), state, set()) is True

    def test_guard_and_semantics(self):
        state = initial_state(list(DECLS.values()))
        guard = [Condition(var="trust", op=">=", value=1), Condition(visited="b_x")]
        assert evaluate_guard(guard, state, {"b_x"}) is True
        assert evaluate_guard(guard, state, set()) is False

    def test_empty_guard_always_true(self):
        assert evaluate_guard([], {}, set()) is True


class TestEffects:
    def test_set_flag(self):
        state = initial_state(list(DECLS.values()))
        new = apply_effect(Effect(var="injured", op="set", value=True), state, DECLS)
        assert new["injured"] is True
        assert state["injured"] is False  # original untouched

    def test_counter_inc_clamps_at_max(self):
        state = {"injured": False, "trust": 3, "town": "calm"}
        new = apply_effect(Effect(var="trust", op="inc", value=2), state, DECLS)
        assert new["trust"] == 3

    def test_counter_dec_clamps_at_zero(self):
        state = {"injured": False, "trust": 0, "town": "calm"}
        new = apply_effect(Effect(var="trust", op="dec", value=5), state, DECLS)
        assert new["trust"] == 0

    def test_counter_set_clamps(self):
        state = initial_state(list(DECLS.values()))
        new = apply_effect(Effect(var="trust", op="set", value=99), state, DECLS)
        assert new["trust"] == 3

    def test_enum_set_in_domain(self):
        state = initial_state(list(DECLS.values()))
        new = apply_effect(Effect(var="town", op="set", value="alert"), state, DECLS)
        assert new["town"] == "alert"

    def test_enum_set_out_of_domain_raises(self):
        state = initial_state(list(DECLS.values()))
        with pytest.raises(ValueError, match="not in declared values"):
            apply_effect(Effect(var="town", op="set", value="burning"), state, DECLS)

    def test_flag_inc_raises(self):
        state = initial_state(list(DECLS.values()))
        with pytest.raises(ValueError, match="only supports set"):
            apply_effect(Effect(var="injured", op="inc", value=1), state, DECLS)

    def test_undeclared_var_raises(self):
        with pytest.raises(ValueError, match="undeclared"):
            apply_effect(Effect(var="ghost", op="set", value=True), {}, DECLS)

    def test_apply_effects_sequence(self):
        state = initial_state(list(DECLS.values()))
        new = apply_effects(
            [Effect(var="trust", op="inc", value=1), Effect(var="trust", op="inc", value=1)],
            state,
            DECLS,
        )
        assert new["trust"] == 3
