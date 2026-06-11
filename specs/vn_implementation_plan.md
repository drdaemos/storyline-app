# VN Engine — Implementation Plan

Implements the system described in `specs/vn_system_design(1).md` and `specs/vn_script_schema_draft.md`.
Progress is tracked in `specs/vn_implementation_tracker.md` (see "Tracker protocol" at the end of this document).

## 1. Goals and constraints

- Build the AI-driven VN generator + runtime as a **building block for v2**. It must not depend on, or modify, the existing chat pipeline (CharacterResponder, ConversationMemory, etc.).
- Integration points with the existing app are intentionally minimal and additive:
  - a FastAPI `APIRouter` included in `src/fastapi_server.py` (one `include_router` line),
  - two new DB tables + one Alembic migration,
  - two new frontend routes registered in `frontend/src/main.ts`.
- Everything else lives in a dedicated backend package (`src/vn/`), a dedicated models package (`src/models/vn/`), and dedicated frontend files — deletable/replaceable as a unit.
- Per the design spec: every component testable via automation; deterministic logic separated from LLM calls; narration can never change outcomes, state, or check results.

## 2. Package layout

```
src/models/vn/                  # Pydantic models only, no logic
    __init__.py
    script.py                   # Script, Scene, Beat (4 types), StateVar, Condition, Guard,
                                # Effect, CheckSpec, ExitEdge, ChoiceOption — mirrors schema draft
    input.py                    # VNInput: characters, setting, rules, premise (synopsis,
                                # protagonist_goal, scope)
    runtime.py                  # VNRuntimeState (var values, visited sets, position, log),
                                # engine events (BeatEvent, ChoicePrompt, CheckResult,
                                # SceneTransition, EndingReached, ExtensionOffer)
    api.py                      # request/response models for the API router
    validation.py               # ValidationIssue (code, severity, scene_id, beat_id, message),
                                # ValidationReport

src/vn/                         # All VN logic; depends on src/models/vn and PromptProcessor only
    __init__.py
    conditions.py               # evaluate Condition/Guard against (state, visited); shared by
                                # validator, softlock walker, and engine
    effects.py                  # apply Effect with domain clamping (set/inc/dec)
    validator.py                # structural hard gates (per-scene and whole-script), no LLM
    softlock.py                 # forward reachability walk over (graph x reachable states)
    checks.py                   # RollResolver protocol + PlaceholderRollResolver (d20 + mods
                                # vs difficulty; explicitly non-final, injected for tests)
    engine.py                   # VNEngine: deterministic runtime state machine, no LLM
    narrator.py                 # VNNarrator: prose from skeleton + state + history via
                                # PromptProcessor; strictly read-only w.r.t. state
    registry.py                 # VNScriptRegistry + VNSessionRegistry (SQLAlchemy, reuses
                                # src.memory.database_config.DatabaseConfig)
    api.py                      # fastapi.APIRouter, thin handlers only (per repo conventions)
    pipeline/
        __init__.py
        outline.py              # Stage A: input -> scene outline
        scene_graphs.py         # Stage B: outline -> per-scene beat mini-graphs
        mechanics.py            # Stage C: state vars / checks / effects / guards
        repair.py               # bounded local repair loop driven by ValidationReport
        generator.py            # VNScriptGenerator: orchestrates A->B->C + gates + softlock
        prompts.py              # all pipeline prompt text in one place

frontend/src/
    types/vn.ts                 # TS mirrors of script/runtime/api models
    composables/useVnApi.ts     # VN endpoints only (same fetch/auth pattern as useApi.ts)
    views/VNLibraryView.vue     # route /vn — list scripts, trigger generation, open player
    views/VNPlayerView.vue      # route /vn/play/:sessionId — play a script
    components/vn/              # player sub-components (BeatPanel, ChoiceList, StatePanel,
                                # CheckRollCard, GenerationProgress)

tests/vn/                       # all backend VN tests
frontend: colocated *.test.ts (existing vitest pattern)
```

Two shared files are touched: `src/memory/db_models.py` (add `VNScript`, `VNSession` tables) and `migrations/versions/` (one new migration). This follows the established persistence pattern while keeping all behavior in `src/vn/`.

## 3. Milestones

Milestone order is dependency order; each is independently shippable and fully tested before the next starts. Task IDs match the tracker.

### M1 — Script schema models (VN-1.x)
Pydantic models for the full schema draft, including the worked example as a fixture.

- Discriminated union on `Beat.type` (`plain | check | choice | ending`); routing blocks are mutually exclusive by construction where possible, with model validators for the rest (e.g. plain beat has exactly one of `next` / `exit_edges` / `exit: "open"`).
- `StateVar` as a discriminated union (`flag` / `counter` with `max` / `enum` with `values`); validate `initial` is in-domain.
- `Condition` covers both var conditions (`==`, `>=`, `<=`) and `visited` conditions (default `value: true`). Guard = list of conditions, AND semantics, empty = always true.
- Ship the worked example from the schema draft as `tests/vn/fixtures/locked_granary.json`; it must round-trip parse.
- **Tests:** parse/serialize round-trips, in-domain validation, rejection of malformed routing blocks.
- **Gate:** worked example parses; ruff clean; tests green.

### M2 — Conditions, effects, structural validator (VN-2.x)
The deterministic core that everything else reuses.

- `conditions.evaluate(guard, state, visited) -> bool`; `effects.apply(effect, state) -> state` with clamping (inc past max stays at max; enum set only to in-set values; out-of-set = generation-time validation error, not runtime crash).
- `validator.py` implements the hard gates from the spec, each as a coded `ValidationIssue`:
  - all id references resolve (beats, scenes, vars, start_scene, entry_beat);
  - exit routing and in-scene routing mutually exclusive on one beat;
  - choice beats have ≥1 option; check beats have both outcomes; ending beats are terminal;
  - equal priorities among one exit node's edges = error; equal `forced` priorities checked at softlock time (state-dependent availability);
  - non-gated path invariant: subgraph of non-gated beats/edges connects entry to an exit, per scene;
  - guards/conditions reference declared vars with in-domain values; effects in-domain.
- **Tests:** one fixture per gate (valid + violating variants); table-driven where natural.
- **Gate:** validator flags every seeded violation and passes the worked example.

### M3 — Softlock checker (VN-3.x)
Forward exploration over reachable states only, from the initial state.

- State node = (current beat, var assignment, visited sets). Successors: beat routing, both check outcomes always, all eligible choice options, exit-edge selection by priority, open-exit = all scenes whose prerequisites match (forced preemption applied). Extension micro-loops treated as always-escapable self-loops (skipped).
- Flag any reachable node/state from which no `ending` beat is reachable; report the offending (scene, beat, state witness) for the repair loop.
- Visited bits are monotone, counters bounded → termination by construction; add an explicit explored-states budget with a clear error as a safety net.
- **Tests:** worked example passes; deliberately broken fixtures (gated-only path forward, check failure dead-end, open exit with empty pool, unreachable ending) are caught with correct witnesses.
- **Gate:** all seeded softlocks detected; runtime acceptable on a ~10-scene script.

### M4 — Runtime engine (VN-4.x)
`VNEngine`: pure deterministic state machine. No LLM, no I/O, no persistence — takes a `Script` + `VNRuntimeState`, exposes:

- `view() -> EngineView` — current beat, pending prompt (choice options with eligible guards / open-exit scene intents presented identically / extension offer), visible state.
- `advance(action) -> list[EngineEvent]` — actions: `proceed`, `choose(index)`, `go_deeper`. Applies beat effects (clamped), resolves checks via injected `RollResolver` (seedable RNG), tracks visitedness per scene and beat, handles scene transitions (directed-exit priority selection, open-exit pool query + forced preemption), terminates on ending.
- Open exits and choices are indistinguishable in `EngineView` (spec requirement: scene selection is never exposed as such).
- `VNRuntimeState` is fully serializable → session persistence and replay are trivial; a replay of the same action log + seed must reproduce the same state (determinism test).
- **Tests:** scripted playthroughs of the worked example covering every mechanic (choice loop, gated option unlock, check success/failure via stubbed resolver, effect feeding a later check modifier, open exit, forced scene preemption, both endings); determinism/replay test; clamping at runtime.
- **Gate:** full structural playthrough of the worked example with zero LLM involvement.

### M5 — Persistence + API router (VN-5.x)
- `db_models.py`: `VNScript` (id, user_id, title, script_data JSON, input_data JSON, schema_version, validation_status, timestamps) and `VNSession` (id, user_id, script_id, runtime_state JSON, rng_seed, status, timestamps). Alembic migration.
- `registry.py`: save/load/list/delete for both, following `ScenarioRegistry` patterns (per-user scoping).
- `api.py` (`APIRouter`, prefix `/api/vn`, auth via existing `UserIdDep`):
  - `POST /scripts/validate` — run validator + softlock on a posted script, return `ValidationReport`;
  - `POST /scripts` (import raw JSON), `GET /scripts`, `GET /scripts/{id}`, `DELETE /scripts/{id}`;
  - `POST /sessions` (script_id, optional seed), `GET /sessions`, `GET /sessions/{id}` → `EngineView` + event log;
  - `POST /sessions/{id}/advance` (action) → events + new `EngineView`;
  - `POST /scripts/generate` — added in M6 (SSE stream, same `StreamingResponse` pattern as character generation).
- Handlers stay thin: parse request → registry/engine/generator → response (repo convention).
- **Tests:** FastAPI TestClient suite; sessions survive a save/load round-trip mid-playthrough.
- **Gate:** a script can be imported, validated, and played to an ending entirely over HTTP.

### M6 — Generation pipeline (VN-6.x)
Staged, validated-per-stage, no global generate-then-repair.

- **Stage A `outline.py`:** `VNInput` → scene outline (ids, intents, prerequisites sketch, open/directed exit plan, intended endings). Hard gate: scope counts match `premise.scope`, ids unique, ending count satisfied, start scene exists.
- **Stage B `scene_graphs.py`:** per scene (one LLM call per scene, failures stay local) → beat mini-graph with routing, choice options, check placements, extension annotations. Hard gate: per-scene structural validation (M2 validator scoped to one scene).
- **Stage C `mechanics.py`:** declare `state_vars`, attach effects to beats, guards to options/edges/prerequisites, difficulties + state-conditional modifiers to checks. Hard gate: full structural validation.
- **Final gate:** softlock walk (M3). Failures produce localized repair requests (`repair.py`): re-prompt only the offending scene/stage with the validation issues, bounded retries (default 3), then surface a structured generation failure.
- All stages take a `PromptProcessor` (constructor-injected); `prompts.py` holds prompt text. Pipeline emits progress events (stage started/passed/repairing) for the SSE endpoint.
- **Tests:** every stage with mocked `PromptProcessor` (per CLAUDE.md: mock all LLM calls, never assert on prompt text) — valid mocked output flows through; invalid mocked output triggers repair then bounded failure. One end-to-end pipeline test with fully mocked stage outputs producing a playable script.
- **Gate:** pipeline produces a validated, softlock-free script from mocked LLM outputs; manual smoke run with a real processor documented in tracker notes.

### M7 — Narration adapter (VN-7.x)
The spec defers narration details; this milestone fixes only the boundary.

- `VNNarrator.narrate(event, state_view, history) -> Iterator[str]` (streaming). Input: beat/scene intents, structural event, current state snapshot, recent narration history. Output: prose only — it cannot touch the engine (enforced by API shape: narrator receives copies, returns text).
- `go_deeper` narration constrained to the beat's `deeper_domain`.
- API: `POST /sessions/{id}/narrate` streams prose for the latest events (kept separate from `advance` so the engine stays LLM-free and the player works in structural mode without it).
- **Tests:** mocked processor; assert narration calls never mutate session state; streaming shape.
- **Gate:** play with narration on/off toggles cleanly; identical structural outcomes either way.

### M8 — Frontend screen (VN-8.x)
- Routes `/vn` (library) and `/vn/play/:sessionId` (player) added to `main.ts`; a single entry link from the start view (one-line touch).
- **VNLibraryView:** list scripts with validation status; import-JSON box; generation form (characters/setting/rules/premise + scope knobs) with SSE progress display; start-session button.
- **VNPlayerView:** narration/intent text pane (structural mode when narration off), unified choice list (choices and open exits identical, per spec), check result display, collapsible debug state panel (vars + visited — dev aid for this building-block phase), ending screen.
- Reuse `useEventStream`/`useAuth` patterns; no changes to existing views beyond the entry link.
- **Tests:** vitest component tests for the player view (choice rendering incl. gated options, advance flow with mocked composable, ending state) following `ChatView.test.ts` patterns.
- **Gate:** worked example playable in the browser end-to-end against the real backend.

### M9 — Quality targets / judge harness (VN-9.x) — deferred, design-first
Blocked on rewriting the spec's quality targets as objectively detectable properties (open gap in the design doc). Scope here: a `judge.py` skeleton with a `JudgeTarget` protocol + one worked target, wired as an optional post-generation pass. Full target set is v2 work.

## 4. Cross-cutting rules

- All Python code fully typed, `ruff` clean (`uv run ruff check src/vn src/models/vn tests/vn`); no `Any` where avoidable.
- Tests: `uv run pytest tests/vn -q`. Frontend: `npm run test` in `frontend/`.
- No imports inside function bodies; thin interface classes; logic in small composable units (repo conventions).
- LLM SDKs / prompt processors always mocked in tests; never assert exact prompt text.
- Schema-draft open decisions [D1]–[D8] are adopted as-is for this iteration; if implementation reveals a problem with one, record it in the tracker's "Decisions & deviations" section rather than silently diverging. Same for the placeholder roll model (explicitly non-final).

## 5. Risks / open questions (from spec, owned here)

| Risk | Mitigation in this plan |
|---|---|
| Open-exit narrative coherence (any available scene must read sensibly after any open exit) | Flagged as the first thing to stress in manual demo runs (M6 gate note); no structural mitigation yet, matches spec |
| Softlock walk blow-up on counter-heavy scripts | Reachable-states-only walk + explored-states budget (M3) |
| Generation cost of unplayed branches | Accepted per spec (no offline prose) |
| Roll model is a placeholder | Isolated behind `RollResolver` protocol (M4) so the v2 redesign is a drop-in |

## 6. Tracker protocol

`specs/vn_implementation_tracker.md` is the single source of truth for implementation status. It is **auto-maintained during implementation**: any agent or developer completing, starting, or blocking a VN task must update the corresponding row (status, date, notes) in the same change set as the code. The AGENTS.md rule enforces this for agent sessions. A milestone is only `done` when its gate criteria (above) are met and recorded in the tracker notes.
