#!/bin/bash
# Check that a deployment can start: the frontend is built and the web server's configuration (.env or environment) works.
# Run after build.sh, before `uv run -m storyline.cli serve --host 0.0.0.0 --port <port>`.
set -euo pipefail
cd "$(dirname "$0")"

uv run --no-sync python - <<'PY'
from dotenv import load_dotenv

from storyline.web.settings import WebSettings

load_dotenv(".env")
settings = WebSettings.from_environment()
index = settings.frontend_dir() / "index.html"
if not index.is_file():
    raise SystemExit(f"No built frontend at {index}: run ./build.sh first.")
settings.authenticator()
settings.user_workspaces()
print(f"OK: auth {'on' if settings.auth_enabled else 'off'}, frontend {index.parent}")
PY
