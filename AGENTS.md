# AGENTS.md

## Purpose
Contributor runbook for local development, validation, and regression checks for Storyline (backend + frontend), with emphasis on multi-character scenarios and suggested-action chat flow.

## Workspace
- Repo root: `/Users/eugenedementjev/repos/storyline-app`
- Run commands from repo root unless a command explicitly uses `cd frontend`.

## Prerequisites
- Python `>=3.12`
- Node.js `>=24`
- `uv` installed
- Frontend deps installed: `cd frontend && npm install`

## Runtime Profiles

### Profile A: Local auth bypass (recommended for UI/manual QA)
- Backend:
  - `DEV_AUTH_BYPASS=true uv run main.py serve --host 127.0.0.1 --port 8000 --reload`
- Frontend:
  - `cd frontend && VITE_DEV_AUTH_BYPASS=true npm run dev -- --host 127.0.0.1 --port 4173`
- Identity used by API/UI: `dev-local-user`

### Profile B: Auth disabled (test-like behavior)
- Backend:
  - `AUTH_ENABLED=false uv run main.py serve --host 127.0.0.1 --port 8000 --reload`
- User ID defaults to: `anonymous`

## Command Reference

### Backend CLI
- Serve API:
  - `uv run main.py serve --host 127.0.0.1 --port 8000 --reload`
- Character sync status:
  - `uv run main.py sync-characters --check`
- Sync character files into DB:
  - `uv run main.py sync-characters`
- Text analyzer:
  - `uv run main.py analyze <file_path> [--output <file>]`
- Interactive chat (legacy CLI):
  - `uv run main.py chat`

### Dev data bootstrap
- Seed scenario/persona/NPC/world-lore data:
  - `uv run main.py dev bootstrap --user-id <user_id> --overwrite`
- Remove seed data:
  - `uv run main.py dev reset-bootstrap --user-id <user_id>`
- Seed IDs:
  - Persona: `dev_user_persona`
  - NPCs: `dev_npc_kara`, `dev_npc_miles`
  - World lore: `dev_world_neon_harbor`
  - Scenario: `dev_scenario_neon_harbor`

### Important user-id rule
- If using `DEV_AUTH_BYPASS=true`, bootstrap with:
  - `--user-id dev-local-user`
- If using `AUTH_ENABLED=false`, bootstrap with:
  - `--user-id anonymous`
- Reason: seeded data must match the runtime auth identity to be visible in UI/API queries.

### Database/migration/deploy helpers
- Apply migrations + sync character YAML to DB:
  - `./predeploy.sh`
- Script runs:
  - `alembic upgrade head`
  - `uv run main.py sync-characters`

### Convenience scripts
- Local dev (backend + frontend):
  - `./dev.sh`
- Production-like build:
  - `./build.sh`

## Required Validation Commands

### Fast pre-commit sanity
- Backend compile sanity:
  - `uv run python -m py_compile src/fastapi_server.py src/simulation/service.py`
- Backend focused runtime tests:
  - `uv run pytest tests/test_simulation_service.py -q`
- Frontend type-check:
  - `cd frontend && npm run type-check`
- Frontend unit tests:
  - `cd frontend && npm run test:run`
- Frontend production build:
  - `cd frontend && npm run build`

### Full backend regression (when touching shared runtime/API/memory)
- `uv run pytest -q`

### Suggested scope-based minimum
- Backend-only change:
  - backend compile sanity + related `pytest` targets
- Frontend-only change:
  - `npm run type-check` + `npm run test:run` + `npm run build`
- End-to-end flow change:
  - backend tests + frontend checks + API smoke + UI smoke flows below

## API Smoke Flow
Assumes backend running at `http://127.0.0.1:8000`.

### Health and index
- `curl -sS http://127.0.0.1:8000/health`
- `curl -sS http://127.0.0.1:8000/api`

### Seed verification
- `curl -sS http://127.0.0.1:8000/api/personas`
- `curl -sS http://127.0.0.1:8000/api/world-lore`
- `curl -sS http://127.0.0.1:8000/api/scenarios/list`

### Expected
- Personas include `dev_user_persona`
- World lore includes `dev_world_neon_harbor`
- Scenarios include `dev_scenario_neon_harbor` with `character_ids` and `world_lore_id`

## UI Smoke Flows
Assumes frontend running at `http://127.0.0.1:4173`.

### Route map to validate
- `/`
- `/create`
- `/create/scenario`
- `/library/scenarios`
- `/library/world-lore`
- `/chat/:characterId/:sessionId` (navigated via UI)

### Flow A: World lore lifecycle
1. Open `/library/world-lore`.
2. Create a world lore entry.
3. Edit it.
4. Delete it (`default-world` is protected).

### Flow B: Multi-character scenario creation
1. Open `/create/scenario` (or enter from `/create`).
2. Select 2+ characters in cast.
3. Select world lore.
4. Set summary + intro scene.
5. Save to library.
6. Verify in `/library/scenarios`:
   - multiple cast members are shown,
   - world lore badge renders.

### Flow C: Session runtime + suggested actions
1. In `/library/scenarios`, click `Start Session` on a multi-character scenario.
2. Send the first user action in chat.
3. Wait for assistant completion event.
4. Verify 2-3 suggested action buttons above input.
5. Click one suggestion and verify it posts as a user turn.
6. Send a custom free-form action and verify normal processing.

## Current Runtime Notes
- Scenario session start materializes all `character_ids` into simulation NPC cast.
- Turn completion payload includes `suggested_actions`.
- Chat UI supports both quick suggested actions and normal manual input.

## Development Approach
- Prefer additive, non-destructive dev tooling over ad-hoc DB edits.
- Keep `main.py dev ...` commands idempotent where practical.
- Validate with targeted tests first, then broader regression for shared-path changes.
- For new dev/test workflows, document commands and expected outcomes in this file.
- When an unexpected bug appears during development and the lesson is generalizable to other areas, append a short entry to `## Past Solved Problems`:
  - do not log routine or expected changes,
  - include symptom/root cause in one line,
  - include the concrete fix in one line.

## Safety Notes
- Do not edit DB rows manually unless no CLI/API path exists.
- Keep migrations and DB schema changes compatible with existing data when possible.
- If a change affects session runtime, include at least one manual end-to-end chat verification.

## Past Solved Problems
- 2026-02: `405 Method Not Allowed` on world lore assistant stream POST.
  - Cause: frontend/backend stream route conventions diverged (`create/stream` vs `create-stream`), so proxied POSTs hit non-existent endpoints on the running backend.
  - Fix: standardized all assistant stream endpoints and callers on one canonical path style (`/api/*/create-stream`), and validate route availability via `/openapi.json` during smoke checks.
- 2026-02: scenario-based session start failed with `404` while frontend sent redundant `character_name`.
  - Cause: start-session contract mixed two modes (scenario-based vs raw-intro) and frontend payload was over-coupled to single-character assumptions.
  - Fix: made `character_name` optional for scenario-based starts (required only for raw intro mode), removed it from scenario-start payloads in UI flows, and added an integration test for `scenario_id`-only start.
- 2026-02: API routes drifted into transport + persistence coupling during session runtime migration.
  - Cause: FastAPI handlers directly orchestrated repository/store details, creating mixed responsibilities and fragile behavior when data access changed.
  - Fix: introduced a dedicated `SessionApplicationService` boundary for session start/interact/read/configure/delete; handlers now map HTTP only and delegate domain/application orchestration.
- 2026-02: turns failed on model-emitted dice expressions containing stat tokens (for example `1d20 + warmth`).
  - Cause: dice parser accepted numeric modifiers only, while LLM output could include symbolic stat references and spacing.
  - Fix: added pre-roll expression normalization in simulation service (resolve known stat tokens from stat blocks, normalize whitespace/operators, safe-fallback unresolved identifiers), with regression coverage.
- 2026-02: scenario persistence drifted between legacy and simulation tables, causing inconsistent behavior across save/list/start session flows.
  - Cause: write/read paths used different table families (`scenarios` vs `sim_scenarios`), so contracts looked correct but runtime fetched different sources.
  - Fix: standardized scenario persistence on `sim_scenarios` + `sim_scenario_characters` with a canonical payload shape (`ruleset_id`, `scene_seed`, tag selections), and routed API access through an application service boundary.
- 2026-02: mutable collaborators captured at module import made endpoint behavior diverge under test/runtime patching.
  - Cause: application services were instantiated once with concrete dependencies; later monkey-patching module globals (for tests or hot replacements) no longer affected route behavior.
  - Fix: switched to lightweight service factory accessors in FastAPI handlers so current collaborators are resolved per-request while keeping separation-of-concerns boundaries.
- 2026-02: session start silently created ad-hoc scenarios instead of reusing selected scenario IDs.
  - Cause: `scenario_id` was parsed in application service but not forwarded into simulation service input, so repository treated starts as ad-hoc and generated new `sim_scenarios` rows.
  - Fix: threaded `scenario_id` through `SessionApplicationService -> SimulationService -> StartSimulationSessionInput`, and added a regression test that asserts scenario-based start forwards the ID.
- 2026-02: Claude structured-output calls failed intermittently with `No structured output received` and broke session turns.
  - Cause: structured schema had weakly-typed fields rejected by Anthropic JSON schema validation, and fallback parsing expected `tool_use` only (missing valid JSON text responses).
  - Fix: tightened contract schema types for structured fields, added explicit JSON shape instructions for narrator step, and implemented resilient Claude fallback parsing from text JSON/code fences/embedded JSON.
- 2026-02: over-aggressive runtime quality gates collapsed NPC behavior into repetitive canned lines.
  - Cause: semantic post-filters replaced model actions/suggestions too often, introducing deterministic fallback phrasing that bypassed character intent.
  - Fix: removed semantic quality gates from runtime action/suggestion paths; keep only minimal sanitization and model-failure safety fallback.
- 2026-02: simulation step contract drifted after adding persona-aware suggestion generation.
  - Cause: `LlmStepRunner` step signatures evolved, but service call-sites were not updated in lockstep, causing runtime fallback and lost context.
  - Fix: pass persona/actor context explicitly through all relevant step calls (`ruleset_resolution`, `action_suggestions`) and add regression tests that assert required args are propagated.
- 2026-02: legacy schema constraints in persisted rulesets caused runtime validation failures (`pressure_clock <= 6`) and fragile startup writes.
  - Cause: strict bounds remained in stored JSON schema while LLM-generated state updates could exceed them; mutating seeded rows during startup was also sensitive to SQLite file locks.
  - Fix: remove the persisted upper bound from the canonical ruleset row, and normalize ruleset schema on repository read-path so runtime validation uses coherent mechanics even if legacy rows exist.
