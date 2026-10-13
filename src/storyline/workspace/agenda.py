"""Pure agenda operations shared by the agent tools, the storage adapter and the interface."""

from collections import Counter
from collections.abc import Sequence

from storyline.workspace.contracts import AgendaError, AgendaItem, AgendaStatus

EMPTY_AGENDA_TEXT = "The agenda is empty."


def replace_agenda(items: Sequence[AgendaItem]) -> tuple[AgendaItem, ...]:
    """Validate a complete replacement agenda: ids must be unique and settled items need an outcome."""
    duplicates = sorted(item_id for item_id, count in Counter(item.id for item in items).items() if count > 1)
    if duplicates:
        raise AgendaError(f"Agenda ids must be unique; repeated: {', '.join(duplicates)}.")
    for item in items:
        _require_outcome_when_settled(item)
    return tuple(items)


def update_agenda_item(
    items: Sequence[AgendaItem],
    item_id: str,
    *,
    status: AgendaStatus | None = None,
    outcome: str | None = None,
    title: str | None = None,
) -> tuple[AgendaItem, ...]:
    """Return the agenda with one item changed; fields left as None keep their value."""
    current = next((item for item in items if item.id == item_id), None)
    if current is None:
        known = ", ".join(item.id for item in items) or "none, the agenda is empty"
        raise AgendaError(f"No agenda item has the id {item_id!r}. Valid ids: {known}.")
    if title is not None and not title.strip():
        raise AgendaError("An agenda item needs a title.")

    changed = current.model_copy(
        update={
            "status": current.status if status is None else status,
            "outcome": current.outcome if outcome is None else outcome.strip(),
            "title": current.title if title is None else title.strip(),
        }
    )
    _require_outcome_when_settled(changed)
    return tuple(changed if item.id == item_id else item for item in items)


def render_agenda(items: Sequence[AgendaItem]) -> str:
    """Render the agenda as plain text lines such as ``[settled] 3f2a9c1d The city — Buffalo``."""
    if not items:
        return EMPTY_AGENDA_TEXT
    return "\n".join(_render_item(item) for item in items)


def _render_item(item: AgendaItem) -> str:
    line = f"[{item.status}] {item.id} {item.title}"
    return f"{line} — {item.outcome}" if item.outcome else line


def _require_outcome_when_settled(item: AgendaItem) -> None:
    if item.status == "settled" and not item.outcome.strip():
        raise AgendaError(f"Item {item.id!r} cannot be settled without an outcome: state the decision in a few words.")
