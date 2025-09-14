#!/bin/bash
uv sync --locked --no-dev --no-editable
cd frontend
npm install
npm run build