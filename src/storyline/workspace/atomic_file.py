"""Crash-safe file writes shared by the filesystem adapters."""

import os
import tempfile
from pathlib import Path


def atomic_write(path: Path, data: bytes) -> None:
    """Write through a sibling temp file so a crash never leaves a truncated file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as file:
        file.write(data)
        file.flush()
        os.fsync(file.fileno())
    try:
        os.replace(file.name, path)
    except BaseException:
        Path(file.name).unlink(missing_ok=True)
        raise
