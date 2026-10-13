#!/bin/bash
# Run the web server (reloading, :8000) and the Vite dev server (:3000, proxies /api and /health) together.
# Open http://localhost:3000. Stop both with Ctrl-C.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d frontend/node_modules ]; then
  npm install --prefix frontend
fi

uv run -m storyline.cli serve --port 8000 --reload &
backend=$!
trap 'kill "$backend" 2>/dev/null || true' EXIT INT TERM

npm run --prefix frontend dev
