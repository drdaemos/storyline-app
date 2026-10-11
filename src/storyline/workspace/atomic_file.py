"""Crash-safe file writes shared by the filesystem adapters."""

import os
import tempfile
import time
from pathlib import Path

REPLACE_ATTEMPTS = 10
REPLACE_BACKOFF_SECONDS = 0.02


def atomic_write(path: Path, data: bytes) -> None:
    """Write through a sibling temp file so a crash never leaves a truncated file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as file:
        file.write(data)
        file.flush()
        os.fsync(file.fileno())
    try:
        _replace_with_retry(file.name, path)
    except BaseException:
        Path(file.name).unlink(missing_ok=True)
        raise


def _replace_with_retry(source: str, destination: Path) -> None:
    """Rename over the destination, retrying briefly while another process holds it open.

    On Windows a rename onto a file that someone else has open (an indexer, antivirus, an editor) fails with
    "Access is denied" until they let go, usually within milliseconds.
    """
    for attempt in range(1, REPLACE_ATTEMPTS + 1):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt == REPLACE_ATTEMPTS:
                raise
            time.sleep(REPLACE_BACKOFF_SECONDS * attempt)
