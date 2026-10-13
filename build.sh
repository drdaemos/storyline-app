#!/bin/bash
# Install backend dependencies and build the web UI into static/, which `storyline serve` serves at /.
# VITE_* values (e.g. VITE_CLERK_PUBLISHABLE_KEY) are baked in at build time: set them in .env or the environment first.
# The package stays editable: the server finds static/ relative to the repository, and a non-editable install would not.
set -euo pipefail
cd "$(dirname "$0")"

uv sync --locked --no-dev
npm ci --prefix frontend
npm run --prefix frontend build
