"""Web application."""

import uvicorn
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
async def health() -> dict[str, str]:
    """Return a minimal service health response."""
    return {"status": "ok"}


def run_server(*, port: int, reload: bool) -> None:
    """Serve the app, importing it by path so uvicorn's reloader can restart it."""
    uvicorn.run(f"{__name__}:app", host="127.0.0.1", port=port, reload=reload)
