#!/bin/bash
alembic upgrade head
uv run -m storyline.cli sync-characters
