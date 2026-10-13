"""Serving the built frontend as a single-page app."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

INDEX_FILENAME = "index.html"
API_PREFIX = "api"


def default_static_dir() -> Path:
    """Return ``static/`` at the repository root, where the frontend build is written."""
    return Path(__file__).resolve().parents[3] / "static"


def mount_frontend(app: FastAPI, static_dir: Path) -> bool:
    """Serve ``static_dir`` at ``/``, answering paths that are not files with ``index.html``; ``/api`` paths stay API errors.

    Register this after every other route. Returns whether there was a frontend to serve.
    """
    root = static_dir.resolve()
    index = root / INDEX_FILENAME
    if not index.is_file():
        return False

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str) -> FileResponse:
        if path == API_PREFIX or path.startswith(f"{API_PREFIX}/"):
            raise HTTPException(status_code=404, detail="Not Found")
        requested = (root / path).resolve()
        if requested.is_relative_to(root) and requested.is_file():
            return FileResponse(requested)
        return FileResponse(index)

    return True
