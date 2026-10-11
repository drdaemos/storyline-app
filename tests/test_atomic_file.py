"""Tests for crash-safe file writes."""

import os

from storyline.workspace import atomic_file
from storyline.workspace.atomic_file import atomic_write


def test_atomic_write_retries_when_the_target_is_briefly_locked(tmp_path, monkeypatch) -> None:
    target = tmp_path / "agenda.json"
    target.write_text("old", encoding="utf-8")
    real_replace = os.replace
    attempts: list[str] = []

    def flaky_replace(source: str, destination: os.PathLike[str]) -> None:
        attempts.append(source)
        if len(attempts) < 3:
            raise PermissionError(5, "Access is denied")
        real_replace(source, destination)

    monkeypatch.setattr(atomic_file.os, "replace", flaky_replace)

    atomic_write(target, b"new")

    assert target.read_text(encoding="utf-8") == "new"
    assert len(attempts) == 3
    assert [path.name for path in tmp_path.iterdir()] == ["agenda.json"]
