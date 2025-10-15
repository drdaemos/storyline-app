#!/bin/bash
alembic upgrade head
uv run main.py sync-characters