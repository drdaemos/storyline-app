"""Mechanics: the machinery a story can run with, and the registry of every mechanic Storyline has."""

from collections.abc import Iterable, Mapping

from storyline.mechanics.base import Mechanic, MechanicError
from storyline.mechanics.base import resolve_mechanics as _resolve
from storyline.mechanics.sealed import SealedMechanic

_ALL_MECHANICS: tuple[Mechanic, ...] = (SealedMechanic(),)
"""One instance of every mechanic; a new mechanic is added here."""

MECHANICS: Mapping[str, Mechanic] = {mechanic.id: mechanic for mechanic in _ALL_MECHANICS}
"""Every mechanic by id."""


def resolve_mechanics(ids: Iterable[str], registry: Mapping[str, Mechanic] = MECHANICS) -> tuple[Mechanic, ...]:
    """Return the named mechanics and their requirements from the registry; raise ``MechanicError`` for an unknown id."""
    return _resolve(ids, registry)


__all__ = ("MECHANICS", "Mechanic", "MechanicError", "SealedMechanic", "resolve_mechanics")
