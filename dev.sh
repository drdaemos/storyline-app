#!/bin/bash
uv run -m storyline.cli serve --port 8000 &
cd frontend && npm run dev
