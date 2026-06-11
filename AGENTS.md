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
- Sync character YAML files to DB: `uv run main.py sync-characters`

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
- For frontend/product work, treat UI/UX and stylistic direction as a maintained artifact:
  - Track user-confirmed direction decisions in this file.
  - Apply those decisions consistently to new and migrated screens.
  - When direction changes, update this file in the same task so future work inherits the latest baseline.

## 5. Testing Rules

- Do not mock the database; use a test harness and clean test data.
- Always mock prompt processors/LLM SDK calls to avoid outbound LLM requests.
- For prompt-related tests, assert behavior and structure, not exact phrasing.
- Test observable behavior; do not test private implementation details.
- If needed behavior depends on hidden side-effects, stop and confirm the exposure strategy with the user.

## 6. Common Interaction Flows

### 6.1. Feature Work

1. Clarify scope and assumptions.
2. Implement through domain/service layer first, then wire API/CLI/UI.
3. Add or update tests that verify user-visible behavior.
4. Run lint and relevant test suites.
5. Summarize assumptions, changes, and validation results.

### 6.2. Bug Fix

1. Reproduce with a failing test when feasible.
2. Fix root cause, not only symptom.
3. Add regression test.
4. Run targeted checks, then broader checks for impacted modules.
5. Document the generalized learning in this file (see section 7).

### 6.3. Review Requests

1. Prioritize findings: correctness, regressions, security, data integrity.
2. Provide file/line references and concrete impact.
3. Keep summary secondary to findings.

### 6.4. Dependency or Infra Changes

1. Use managed commands (`uv add`, npm commands, alembic migration flow).
2. Verify lockfiles and compatibility checks.
3. Include rollback/compatibility notes in summary.

## 7. Feedback Learning Log

When user feedback reveals a missed issue after delivery, append a short learning note to this file:

- Problem pattern (generalized, not task-specific timeline)
- What change prevented recurrence

Keep notes concise and reusable.

- Problem pattern: Assistant structured updates may use alias field names (`skills`, `drives`, `emotional_state`) that are dropped by strict canonical parsing, causing visible mismatch between assistant reply and form state.
- What change prevented recurrence: Normalize assistant payload aliases to canonical `starting_*` fields in backend extraction and keep frontend schema-based key normalization + regression tests for alias updates.

## 8. Product Vision and UI/UX Preferences (User-Confirmed)

Track explicit UI/UX preferences here and apply them to new screens by default.

- Navigation on tiles: avoid single CTA buttons whose only purpose is navigation (not just literal `Open` labels). Use clickable tile headings with clear affordance (e.g., underline on hover/focus) for navigation targets. If a tile has no other action besides navigation, make the whole tile clickable.
- Navigation button styling: emphasis is allowed when it communicates real priority, but do not force emphasis by default. In peer action blocks (like "Create New"), keep navigation buttons visually equal.
- Keep language product-facing. Avoid enterprise wording like `workspace`.
- Creation surface should use a two-panel layout with AI assistance chat on one side.
- Scenario creation supports multi-character selection via searchable tag-like multi-select. Do not use a lead-character field.
- Play continuation options should be differentiated visually by icon and color; avoid extra type labels or legend blocks.
- Typography baseline defaults: `Unbounded` for major headings, `Source Serif 4` for narrative text, and `Work Sans` for UI text.
