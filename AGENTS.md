# Storyline Coding Guidelines for Agents

This document defines how coding agents and contributors should work in this repository.

## 1. Communication Rules

- If requirements are unclear, ask concise clarifying questions before implementation.
- If a reasonable assumption exists, state it and proceed; confirm it in the final summary.
- Keep responses factual, concise, and structured.
- State confidence explicitly when confidence is low.
- Explain trade-offs when proposing alternatives.
- Push back if user proposes solutions that introduce performance issues or behave inconsistently with the rest of the application (explain exactly how)

## 2. Architecture

Storyline is a writer room: an AI writer collaborates with the user on stories kept as files in a workspace.

- `src/storyline/agent/` - the writer agent, its tools, prompts and skills.
- `src/storyline/workspace/` - the file workspace: one directory per story.
- `src/storyline/room/` - the room protocol (events and operations) and the story room that both interfaces drive. `protocol.py` is the source of truth.
- `src/storyline/tui/` - the terminal UI (`storyline write`), local to one workspace.
- `src/storyline/web/` - the FastAPI web server (`storyline serve`): auth, per-user workspaces, REST operations, SSE event stream, and serving of the built frontend.
- `frontend/` - the Vue 3 + TypeScript + Vite web UI; it offers the same operations and renders the same events as the terminal UI (see `frontend/README.md`).
- `src/storyline/evals/`, `evals/` - prompt evaluation scenarios and runner.

Web auth is switched by `AUTH_ENABLED`: off, one local user works in `STORYLINE_WORKSPACE` (shared with the terminal UI); on, every request carries a Clerk session token and each user's stories live in `STORYLINE_DATA_DIR/users/<user id>`.

## 3. Development Environment (Command Pointers)

Run commands from the repository root.

- Bootstrap Python dependencies: `uv sync`
- Bootstrap frontend dependencies: `npm install --prefix frontend`
- Start full dev environment (backend on :8000 with reload, Vite on :3000 proxying `/api` and `/health`): `./dev.sh` (`./dev.ps1` on Windows PowerShell); open http://localhost:3000
- Start backend only (hot reload): `uv run -m storyline.cli serve --port 8000 --reload`
- Start frontend only: `npm run --prefix frontend dev`
- Terminal UI: `uv run storyline write [--story NAME]`
- Build for production (locked backend deps, frontend into `static/`): `./build.sh`
- Check a deployment can start (frontend built, auth and workspace configuration valid): `./predeploy.sh`
- Serve a production build: `uv run -m storyline.cli serve --host 0.0.0.0 --port <port>`
- Build the production image locally: `docker build -t storyline .` (Railway builds the same `Dockerfile`, configured by `railway.json`; setup is in `README.md`)
- Regenerate the frontend's `protocol.json` from the Python protocol: `uv run python -m storyline.room.export`
- Evaluate the writer prompt (real LLM calls, costs money; see `evals/README.md`): `uv run storyline eval run [SCENARIO...]`

Environment (set in `.env`, see `.env.default`):

- Model provider keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, and so on; `STORYLINE_MODEL` picks the writer model.
- `STORYLINE_WORKSPACE` - the workspace directory when auth is off (also `--workspace`).
- `AUTH_ENABLED`, `CLERK_SECRET_KEY` (or `CLERK_JWT_KEY`), `CLERK_AUTHORIZED_PARTIES`, `STORYLINE_DATA_DIR` (also `--data-dir`) - hosted multi-user mode.
- `VITE_CLERK_PUBLISHABLE_KEY` - frontend sign-in; read at build/dev time. Without it the frontend sends no token.
- `STORYLINE_STATIC_DIR` - where the built frontend is served from (default: `static/`).

## 4. Quality Gates

Before finishing changes, run relevant checks.

- Backend lint: `uv run ruff check .`
- Backend tests: `uv run pytest`
- Frontend lint: `npm run --prefix frontend lint`
- Frontend type-check: `npm run --prefix frontend type-check`
- Frontend tests: `npm run --prefix frontend test:run`

For small scoped changes, run targeted tests first, then broaden if impact is wider.

A change to the room protocol (events, operations, fields) must keep the web UI in step: regenerate `protocol.json` and add the reducer, client function or type that `frontend/src/protocol/parity.test.ts` asks for.

## 5. Core Engineering Constraints

- Every behavior change must be covered by tests.
- Add explicit Python types where inference is insufficient.
- Avoid `Any`.
- Never add dependencies by manually editing `pyproject.toml`; use `uv add <dependency>`.
- Keep imports at file top; do not import inside business logic.
- Keep domain logic out of API/CLI handlers.
- Use service classes as boundaries between domain logic and interface layers.
- Favor small, single-purpose classes/functions over multi-responsibility units.
- Frontend: components hold no protocol logic and use theme tokens only, never literal colours, fonts or shadows (see `frontend/README.md`).

## 6. Testing Rules

- Use temporary-directory workspaces and clean test data; do not mock the file workspace.
- Always mock prompt processors/LLM SDK calls to avoid outbound LLM requests.
- For prompt-related tests, assert behavior and structure, not exact phrasing.
- Test observable behavior; do not test private implementation details.
- If needed behavior depends on hidden side-effects, stop and confirm the exposure strategy with the user.
