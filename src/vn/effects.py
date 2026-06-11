"""Effect application with domain clamping, and initial-state construction.

State can never leave the declared space: counters clamp to 0..max, flags only
take bools, enums only take in-set values. Out-of-domain *shapes* (inc on a flag,
set enum to an unknown value) are generation-time validation errors; reaching one
here means a validator gap, so it raises rather than guessing.
"""

from src.models.vn.script import CounterVar, Effect, EnumVar, FlagVar, StateVar
from src.vn.conditions import StateMap


def declarations_by_name(state_vars: list[StateVar]) -> dict[str, StateVar]:
    return {var.name: var for var in state_vars}


def initial_state(state_vars: list[StateVar]) -> StateMap:
    return {var.name: var.initial for var in state_vars}


def apply_effect(effect: Effect, state: StateMap, declarations: dict[str, StateVar]) -> StateMap:
    """Return a new state with the effect applied, clamped to the variable's domain."""
    declaration = declarations.get(effect.var)
    if declaration is None:
        raise ValueError(f"effect references undeclared var '{effect.var}'")

    new_state = dict(state)
    if isinstance(declaration, FlagVar):
        if effect.op != "set" or not isinstance(effect.value, bool):
            raise ValueError(f"flag '{effect.var}' only supports set with a bool value")
        new_state[effect.var] = effect.value
    elif isinstance(declaration, CounterVar):
        if not isinstance(effect.value, int) or isinstance(effect.value, bool):
            raise ValueError(f"counter '{effect.var}' requires an int effect value")
        current = state[effect.var]
        assert isinstance(current, int)
        if effect.op == "set":
            result = effect.value
        elif effect.op == "inc":
            result = current + effect.value
        else:
            result = current - effect.value
        new_state[effect.var] = max(0, min(declaration.max, result))
    elif isinstance(declaration, EnumVar):
        if effect.op != "set":
            raise ValueError(f"enum '{effect.var}' only supports set")
        if effect.value not in declaration.values:
            raise ValueError(f"enum '{effect.var}': value '{effect.value}' not in declared values")
        new_state[effect.var] = effect.value
    return new_state


def apply_effects(effects: list[Effect], state: StateMap, declarations: dict[str, StateVar]) -> StateMap:
    for effect in effects:
        state = apply_effect(effect, state, declarations)
    return state
