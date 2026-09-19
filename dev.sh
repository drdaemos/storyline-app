#!/bin/bash
uv run main.py serve --port 8000 &
cd frontend && npm run dev
