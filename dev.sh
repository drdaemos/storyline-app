#!/bin/bash
uv run main.py serve --port 8000 --reload &
cd frontend && npm run dev