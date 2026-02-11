from src.simulation.contracts import StateOp
from src.simulation.dice import roll_dice
from src.simulation.schema_validation import SchemaValidationError, validate_schema
from src.simulation.state_ops import StateOpError, apply_state_ops


def test_roll_dice_is_deterministic_with_seed() -> None:
    first = roll_dice("2d6+3", seed=12345)
    second = roll_dice("2d6+3", seed=12345)
    assert first.total == second.total
    assert first.rolls == second.rolls


def test_schema_validation_rejects_missing_required_field() -> None:
    schema = {
        "type": "object",
        "required": ["minutes_left"],
        "properties": {
            "minutes_left": {"type": "integer", "min": 0, "max": 7},
        },
    }
    try:
        validate_schema({}, schema)
        raise AssertionError("Expected SchemaValidationError")
    except SchemaValidationError:
        pass


def test_apply_state_ops_supports_increment_and_set() -> None:
    state = {"minutes_left": 7, "pressure": "steady"}
    ops = [
        StateOp(op="decrement", path="minutes_left", value=1),
        StateOp(op="set", path="pressure", value="rising"),
    ]
    next_state = apply_state_ops(state, ops)
    assert next_state["minutes_left"] == 6
    assert next_state["pressure"] == "rising"


def test_apply_state_ops_rejects_increment_on_non_numeric() -> None:
    state = {"pressure": "steady"}
    try:
        apply_state_ops(state, [StateOp(op="increment", path="pressure", value=1)])
        raise AssertionError("Expected StateOpError")
    except StateOpError:
        pass
