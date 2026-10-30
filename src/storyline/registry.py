"""The registry of every mechanic Storyline has.

It sits above ``storyline.mechanics`` and ``storyline.agent`` because the review mechanic runs the reviewer agent,
which the agent layer builds. Code below this module takes the registry as an argument; the interfaces, the room and
the evals pass ``MECHANICS``.
"""

from collections.abc import Callable, Mapping

from pydantic_ai.models import Model

from storyline.agent.reviewer import StoryReviewer
from storyline.mechanics import CastMechanic, ClocksMechanic, Mechanic, OracleMechanic, PersonaMechanic, ReviewMechanic, SealedMechanic


def build_mechanics(*, review_model_resolver: Callable[[str], Model | str] | None = None) -> Mapping[str, Mechanic]:
    """Return one instance of every mechanic by id; a new mechanic is added here.

    The reviewer resolves a story's mechanics against the registry it belongs to. ``review_model_resolver`` turns the
    model name in ``STORYLINE_REVIEW_MODEL`` into a model; None resolves it as the writer's models are. Replaced in tests.
    """
    registry: dict[str, Mechanic] = {}
    reviewer = StoryReviewer(registry, review_model_resolver)
    mechanics = (SealedMechanic(), PersonaMechanic(), CastMechanic(), ClocksMechanic(), OracleMechanic(), ReviewMechanic(reviewer))
    registry.update((mechanic.id, mechanic) for mechanic in mechanics)
    return registry


MECHANICS: Mapping[str, Mechanic] = build_mechanics()
"""Every mechanic by id."""

__all__ = ("MECHANICS", "build_mechanics")
