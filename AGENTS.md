# Storyline Coding Guidelines for Agents

This document defines how coding agents and contributors should work in this repository.

## 1. Communication Rules

- If requirements are unclear, ask concise clarifying questions before implementation.
- If a reasonable assumption exists, state it and proceed; confirm it in the final summary.
- Keep responses factual, concise, and structured.
- State confidence explicitly when confidence is low.
- Explain trade-offs when proposing alternatives.
- Push back if user proposes solutions that introduce performance issues or behave inconsistently with the rest of the application (explain exactly how)

## 2. Development Environment (Command Pointers)

Run commands from repository root: `/Users/eugenedementjev/repos/storyline-app`.

- Bootstrap Python dependencies: `uv sync`
- Bootstrap frontend dependencies: `npm install --prefix frontend`
- Start full dev environment (backend + frontend): `./dev.sh`
- Start backend only (hot reload): `uv run main.py serve --port 8000 --reload`
- Start frontend only: `npm run --prefix frontend dev`
- Build production assets/deps: `./build.sh`
- Run DB migrations: `uv run alembic upgrade head`

Useful env pointers:

- Use `.env` for local secrets/config.
- `DATABASE_URL` overrides DB config.
- If `DATABASE_URL` is unset, DB settings can be composed with `DB_TYPE`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`.

## 3. Quality Gates

Before finishing changes, run relevant checks.

- Backend lint: `uv run ruff check .`
- Backend tests: `uv run pytest`
- Frontend lint: `npm run --prefix frontend lint`
- Frontend type-check: `npm run --prefix frontend type-check`
- Frontend tests: `npm run --prefix frontend test:run`

For small scoped changes, run targeted tests first, then broaden if impact is wider.

## 4. Core Engineering Constraints

- Every behavior change must be covered by tests.
- Add explicit Python types where inference is insufficient.
- Avoid `Any`.
- Never add dependencies by manually editing `pyproject.toml`; use `uv add <dependency>`.
- Keep imports at file top; do not import inside business logic.
- Keep domain logic out of API/CLI handlers.
- Use service classes as boundaries between domain logic and interface layers.
- Favor small, single-purpose classes/functions over multi-responsibility units.

## 5. Testing Rules

- Do not mock the database; use a test harness and clean test data.
- Always mock prompt processors/LLM SDK calls to avoid outbound LLM requests.
- For prompt-related tests, assert behavior and structure, not exact phrasing.
- Test observable behavior; do not test private implementation details.
- If needed behavior depends on hidden side-effects, stop and confirm the exposure strategy with the user.