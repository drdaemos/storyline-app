"""Mechanics: the machinery a story can run with. The registry of every mechanic Storyline has is ``storyline.registry``."""

from storyline.mechanics.base import Mechanic, MechanicError, resolve_mechanics
from storyline.mechanics.cast import CastMechanic
from storyline.mechanics.clocks import ClocksMechanic
from storyline.mechanics.oracle import OracleMechanic
from storyline.mechanics.persona import PersonaMechanic
from storyline.mechanics.review import ReviewMechanic
from storyline.mechanics.sealed import SealedMechanic

__all__ = (
    "CastMechanic",
    "ClocksMechanic",
    "Mechanic",
    "MechanicError",
    "OracleMechanic",
    "PersonaMechanic",
    "ReviewMechanic",
    "SealedMechanic",
    "resolve_mechanics",
)
