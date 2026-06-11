# VN Engine — Implementation Tracker

> **Auto-update protocol (binding for agents and humans):**
> When you start, finish, or get blocked on any task below, update its row **in the same change set as the code**:
> set `Status` (`todo` → `in-progress` → `done`, or `blocked`), set `Updated` to today's date, and add a short `Notes` entry
> (for `done`: how the milestone gate was verified, e.g. test command output; for `blocked`: what is missing).
> When all tasks of a milestone are `done` and its gate criteria from `vn_implementation_plan.md` are met, set the milestone
> row in the summary table to `done`. Never mark a task `done` with failing tests or ruff errors.
> Record any deviation from the plan or schema draft in "Decisions & deviations" below — do not silently diverge.

Plan: `specs/vn_implementation_plan.md` · Specs: `specs/vn_system_design(1).md`, `specs/vn_script_schema_draft.md`

## Milestone summary

| Milestone | Scope | Status |
|---|---|---|
| M1 | Script schema models | done |
| M2 | Conditions, effects, structural validator | done |
| M3 | Softlock checker | done |
| M4 | Runtime engine | done |
| M5 | Persistence + API router | done |
| M6 | Generation pipeline | done |
| M7 | Narration adapter | done |
| M8 | Frontend screen | done (except in-browser pass VN-8.5) |
| M9 | Judge harness (skeleton, deferred) | done |

## Tasks

### M1 — Script schema models
| ID | Task | Status | Updated | Notes |
|---|---|---|---|---|
| VN-1.1 | `src/models/vn/script.py`: StateVar, Condition, Guard, Effect, CheckSpec, ExitEdge, ChoiceOption, Beat union, Scene, Script | done | 2026-06-11 | Discriminated `Beat` union on `type`; extra="forbid" throughout; routing exclusivity as model validator. `Condition`/`CheckModifier` are single objects (var-xor-visited), not a union, to keep the structured-output grammar small — see deviations |
| VN-1.2 | `src/models/vn/input.py`: VNInput (characters, setting, rules, premise + scope) | done | 2026-06-11 | Exactly-one-protagonist enforced; anchors = minimal list[str] placeholder |
| VN-1.3 | Fixture `tests/vn/fixtures/locked_granary.json` (worked example) + round-trip tests | done | 2026-06-11 | Verbatim worked example; parse + dump + reparse equality |
| VN-1.4 | Model-level validation tests (in-domain initials, routing exclusivity, malformed rejection) | done | 2026-06-11 | Gate met: `uv run pytest tests/vn` 22 passed; ruff clean |

### M2 — Conditions, effects, structural validator
| ID | Task | Status | Updated | Notes |
|---|---|---|---|---|
| VN-2.1 | `src/vn/conditions.py` (guard evaluation incl. `visited`) + tests | done | 2026-06-11 | Single evaluation path shared by validator/softlock/engine |
| VN-2.2 | `src/vn/effects.py` (set/inc/dec with domain clamping) + tests | done | 2026-06-11 | Pure functions returning new state; out-of-domain shapes raise (validator gap signal) |
| VN-2.3 | `src/models/vn/validation.py`: ValidationIssue / ValidationReport | done | 2026-06-11 | Includes optional state witness field for softlock findings |
| VN-2.4 | `src/vn/validator.py`: id resolution, routing exclusivity, beat-type rules, exit-priority uniqueness | done | 2026-06-11 | Routing exclusivity enforced at model level (M1); beat ids globally unique (visited namespace) |
| VN-2.5 | Validator: non-gated entry→exit path invariant per scene | done | 2026-06-11 | Checks treated as non-gates (both outcomes traversed); endings count as exits |
| VN-2.6 | Validator: var/domain checks on guards, effects, modifiers | done | 2026-06-11 | Ordered comparisons restricted to counters; enum effects must be in-set |
| VN-2.7 | Per-gate violation fixtures + tests (valid and violating variant per gate) | done | 2026-06-11 | Gate met: 64 tests pass (`uv run pytest tests/vn`); ruff clean; duplicate forced priority = warning (full check deferred to softlock walk) |

### M3 — Softlock checker
| ID | Task | Status | Updated | Notes |
|---|---|---|---|---|
| VN-3.1 | `src/vn/softlock.py`: forward reachable-state walk (beats, checks both-ways, choices, exits, open-exit pool, forced preemption) | done | 2026-06-11 | BFS over (beat, state, visited) nodes + reverse co-reachability from ending nodes; equal forced priorities detected with state |
| VN-3.2 | Witness reporting (scene, beat, state) + explored-states budget | done | 2026-06-11 | One witness per beat to avoid flooding; budget default 100k nodes -> `state_space_budget_exceeded` |
| VN-3.3 | Broken-fixture tests (gated-only path, check dead-end, empty open-exit pool, unreachable ending) + worked-example pass | done | 2026-06-11 | Gate met: 74 tests pass; worked example clean incl. both endings reachable |

### M4 — Runtime engine
| ID | Task | Status | Updated | Notes |
|---|---|---|---|---|
| VN-4.1 | `src/models/vn/runtime.py`: VNRuntimeState (serializable) + engine events/view models | done | 2026-06-11 | Beat lifecycle pre→extension→resolve; full JSON round-trip |
| VN-4.2 | `src/vn/checks.py`: RollResolver protocol + seedable PlaceholderRollResolver | done | 2026-06-11 | d20 placeholder (non-final per spec); `skip` continues a resumed session's roll sequence |
| VN-4.3 | `src/vn/engine.py`: view/advance, effects, visitedness, scene transitions, open-exit-as-choice, extension micro-loop, endings | done | 2026-06-11 | Engine has zero LLM/I/O deps; only eligible options exposed; forced scenes auto-enter |
| VN-4.4 | Scripted playthrough tests of worked example (all mechanics, both endings) | done | 2026-06-11 | Covers gated unlock, clamping, check modifier fed by earlier effect, forced preemption |
| VN-4.5 | Determinism/replay test (same seed + action log ⇒ same state) | done | 2026-06-11 | Gate met: 89 tests pass; resume-mid-session reproduces reference run |

### M5 — Persistence + API router
| ID | Task | Status | Updated | Notes |
|---|---|---|---|---|
| VN-5.1 | `db_models.py`: VNScript + VNSession tables; Alembic migration | done | 2026-06-11 | Migration `f3a9b1c2d4e5` (head after `a1b2c3d4e5f6`); sessions store runtime_state + event_log JSON |
| VN-5.2 | `src/vn/registry.py`: script/session registries (per-user scoping) + tests | done | 2026-06-11 | Strict per-user scoping (no anonymous fallback, unlike ScenarioRegistry) |
| VN-5.3 | `src/vn/api.py` router: scripts CRUD + validate endpoints; include in `fastapi_server.py` | done | 2026-06-11 | One `include_router` line in the server; logic lives in `src/vn/service.py` (VNService); DI via `get_vn_service` override |
| VN-5.4 | Session endpoints (create, get, advance) wiring registry + engine | done | 2026-06-11 | Invalid scripts blocked from sessions (409); engine errors -> 400; import runs validator + softlock and stores status |
| VN-5.5 | TestClient suite incl. mid-playthrough save/load round-trip | done | 2026-06-11 | Gate met: 105 tests pass; full playthrough to ending over HTTP incl. reload mid-game |

### M6 — Generation pipeline
| ID | Task | Status | Updated | Notes |
|---|---|---|---|---|
| VN-6.1 | Stage A `pipeline/outline.py` + scope/ids/endings hard gate + tests (mocked processor) | done | 2026-06-11 | Outline = ScriptOutline model (`src/models/vn/pipeline.py`); gate checks scope counts, id uniqueness, exit-mode/ending consistency |
| VN-6.2 | Stage B `pipeline/scene_graphs.py` (per-scene mini-graphs) + per-scene gate + tests | done | 2026-06-11 | One LLM call per scene; gate = validate_scene_structure + outline conformance (id, endings, exit mode) |
| VN-6.3 | Stage C `pipeline/mechanics.py` (vars/effects/guards/checks) + full structural gate + tests | done | 2026-06-11 | Single full-script call; gate = validate_script + scope re-check |
| VN-6.4 | `pipeline/repair.py`: localized bounded repair loop from ValidationReport + tests | done | 2026-06-11 | Generic run_with_repair; previous report fed back as prompt feedback; VNGenerationError carries last report |
| VN-6.5 | `pipeline/generator.py`: orchestration + softlock final gate + progress events; end-to-end mocked test | done | 2026-06-11 | Softlock walk runs inside mechanics' repair loop (final gate); softlocking script test caught with dead_end witness |
| VN-6.6 | `POST /api/vn/scripts/generate` SSE endpoint + tests | done | 2026-06-11 | Worker thread + queue relays progress as SSE; result revalidated and persisted with input_data. Gate met: 121 tests pass |
| VN-6.7 | Manual smoke run with a real processor; record findings (esp. open-exit coherence) in Notes | done | 2026-06-12 | Real Claude smoke run passed with Anthropic-friendly request models: `uv run main.py vn-generate examples/vn/keeper_of_the_last_light.json --user-id smoke-keeper-anthropic --output runs/keeper-of-the-last-light-anthropic-smoke/script.json` produced a valid script (`cc71fc6a-7471-4dd5-96da-08d17a338f2c`). Follow-up real judge run also passed (`vn-review ... --target-score 4.0`), overall 3.8/5; reports saved under `runs/keeper-of-the-last-light-anthropic-smoke/evals/`. Prompt-tuning loop on keeper input found invalid guard DSL, inert checks, duplicate choice targets, and write-only vars; prompts now avoid beat-count guidance and generation gates reject those structural false promises. Final real smoke run: `uv run main.py vn-generate examples/vn/keeper_of_the_last_light.json --user-id loop-keeper-prompt-final --output runs/keeper-of-the-last-light-prompt-tune-final/iter-1.script.json` produced a valid 5-scene/52-beat script with no same-target checks, duplicate choice targets, or unread/unwritten state vars. Focused tests: `uv run pytest tests/vn -q` (182 passed); changed-path ruff clean |

### M7 — Narration adapter
| ID | Task | Status | Updated | Notes |
|---|---|---|---|---|
| VN-7.1 | `src/vn/narrator.py`: streaming narrate() over events/state/history; deeper_domain constraint | done | 2026-06-11 | Read-only by construction (snapshots in, text out); narration_log {event_index, text} added to vn_sessions (migration amended pre-release) |
| VN-7.2 | `POST /sessions/{id}/narrate` streaming endpoint | done | 2026-06-11 | text/plain stream; narrates only events since last narration; 409 when nothing new |
| VN-7.3 | Tests: mocked processor, no state mutation, structural outcomes identical with narration on/off | done | 2026-06-11 | Gate met: 127 tests pass; same seed + actions give identical state with/without narration |

### M8 — Frontend screen
| ID | Task | Status | Updated | Notes |
|---|---|---|---|---|
| VN-8.1 | `types/vn.ts` + `composables/useVnApi.ts` | done | 2026-06-11 | TS mirrors of backend models; fetch + Clerk bearer auth; SSE line parser for generate, reader stream for narrate |
| VN-8.2 | `VNLibraryView.vue` (list/import/generate with SSE progress/start session) + routes in `main.ts` | done | 2026-06-11 | Routes `/vn` + `/vn/play/:sessionId`; entry button on character selection; Play disabled unless script valid |
| VN-8.3 | `VNPlayerView.vue` + `components/vn/*` (text pane, unified choices, check results, debug state panel, ending) | done | 2026-06-11 | Narration optional via toggle (`vnDisplay.buildDisplayBlocks` interleaves narration with structural events); choices and open exits rendered identically (VnChoiceList) |
| VN-8.4 | Vitest component tests for player view | done | 2026-06-11 | Gate met: `npm run test:run` — VnChoiceList (5) + vnDisplay (6) pass; only pre-existing failures remain (useLocalSettings node-localStorage, useChatHighlight) |
| VN-8.5 | Browser end-to-end pass of worked example against real backend | todo | — | Manual step: run backend + frontend, import `tests/vn/fixtures/locked_granary.json`, play to an ending |
| VN-8.6 | Human-readable generated script preview for complete and in-progress jobs | done | 2026-06-11 | Job summaries now expose checkpointed scenes; library Preview modal renders complete scripts and partial jobs. Verified: `uv run pytest tests\vn\test_api.py -q` (12 passed), `uv run ruff check src\models\vn\api.py src\vn\service.py tests\vn\test_api.py`, `npm.cmd run test:run -- src/utils/vnDisplay.test.ts` (8 passed), `npm.cmd run build` |

### M9 — Judge harness (deferred skeleton)
| ID | Task | Status | Updated | Notes |
|---|---|---|---|---|
| VN-9.1 | Rewrite quality targets as objectively detectable properties (design task, spec gap) | done | 2026-06-11 | Resolved as 10 anchored dimensions across two lenses (playwright: premise_fidelity, dramatic_structure, scene_craft, character_utilization, tone_consistency; director: choice_meaningfulness, branch_divergence, consequence_payoff, ending_differentiation, player_agency), each with 1/3/5 anchors + binary craft checks; structural facts (branching, var usage, endings) computed deterministically in `src/vn/judge/rendering.py` (`build_digest`) and handed to the judge as ground truth |
| VN-9.2 | `src/vn/judge.py`: JudgeTarget protocol + one worked target + optional pipeline hook | done | 2026-06-11 | Built as `src/vn/judge/` package (models in `src/models/vn/judge.py`), not the planned protocol skeleton — see deviation. Two-lens `VNScriptJudge` (2 LLM calls, gated via `run_with_repair`: dimension-set/citation/finding-count checks), deterministic assembly (overall score, verdict, severity×effort priorities, regeneration guidance), `compare_evaluations` numeric progress rule, markdown report + file persistence. CLI: `vn-generate` (persisting, resumable, `--guidance`) / `vn-review` (file or script id, `--baseline`, `--target-score`). Verified: `uv run pytest tests/vn -q` (180 passed incl. new test_judge/test_cli_vn), ruff clean |

## Decisions & deviations

| Date | What | Why |
|---|---|---|
| 2026-06-11 | Schema-draft choices [D1]–[D8] adopted as-is; placeholder roll model isolated behind RollResolver | Per spec; revisit in v2 |
| 2026-06-11 | Beat ids globally unique across the script (not just per scene) | `visited(id)` shares one namespace for scenes and beats; per-scene uniqueness would make visited-conditions ambiguous |
| 2026-06-11 | Visited marked on beat/scene entry, then effects applied, then routing evaluated | Single well-defined evaluation order shared verbatim by engine and softlock walk; guards on the same beat can rely on its own effects |
| 2026-06-11 | Directed exit edges respect only their own guard — they bypass target prerequisites and once-only | Author explicitly drew the edge; prerequisites gate only the open-exit pool. Softlock walk mirrors this |
| 2026-06-11 | Open-exit scene selection presented to the player identically to a choice beat | Spec requires open exits to feel like in-fiction decisions; one `Pending` model covers both |
| 2026-06-11 | Checks are not gates for the non-gated-path invariant | Both outcomes always traversable; only guards can dead-end a path, checks merely branch |
| 2026-06-11 | Narration is opt-in per action in the player UI and persisted as `{event_index, text}` after the stream completes | Keeps engine/narration boundary observable; replay shows exactly which events each narration covered |
| 2026-06-11 | `scope_scene_count_mismatch` gate removed (outline + mechanics); `target_scenes` is guidance only, ending count stays exact | User decision: the model may add scenes when the story needs them |
| 2026-06-11 | Pipeline stages no longer use strict structured outputs (`respond_with_model`); they call `respond_with_text` with the JSON Schema embedded in the prompt and parse/validate locally (`pipeline/parsing.py`). Parse failures (`output_parse_error`) feed the same bounded repair loop as gate failures | Real run failed: Scene/Script schemas exceed the provider's structured-output grammar size limit ("compiled grammar is too large") |
| 2026-06-11 | VN generation form persists its input to localStorage (`useFormDraft`, key `vn-generation-draft`); draft is kept after generation so it can be tweaked and re-run | Parity with character/scenario creation screens, per user request |
| 2026-06-11 | Pipeline stage calls stream (`respond_with_stream`, joined) instead of blocking | Real run failed: SDKs reject non-streaming requests that may exceed 10 minutes (large mechanics output) |
| 2026-06-11 | Generation runs as a persistent job (`vn_generation_jobs` table, migration `b7c8d9e0f1a2`): outline and each scene are checkpointed as they pass; on failure the job stays with its checkpoint + error and can be resumed (skipping completed artifacts); on success the job row is deleted. UI lists unfinished jobs with per-scene progress and Resume/Discard | User requirement: long generations must be resumable and partial results visible |
| 2026-06-11 | Softlock walk tracks only routing-relevant visited ids (scene ids + visited() guard refs); `state_space_budget_exceeded` demoted to warning | Real script blew the 100k budget: unreferenced beat ids multiplied node identities exponentially on reconverging paths. Budget exhaustion means "unverified", not "broken" — as a hard error it burned repair attempts on feedback the LLM cannot act on |
| 2026-06-11 | Parse failures from truncated output get an explicit `output_truncated` issue; output-format prompt asks for minified JSON | Mechanics output hit the token limit mid-list (pretty-printed JSON wastes ~2-3x tokens) |
| 2026-06-11 | Stage C redesigned: the LLM emits a `MechanicsPatch` (state_vars + id-referenced deltas for effects, option/edge guards, scene prerequisites/repeatable/forced, check modifiers); the final Script is assembled in code (`pipeline/patching.py`). Bad id references raise `patch_application_error` into the repair loop. Supersedes whole-script re-emission | Whole-script output was the token/runtime sink and a drift risk; patch output is ~10x smaller and the drafted structure cannot change |
| 2026-06-11 | Pipeline back on structured outputs (`respond_with_model`); JSON schema removed from prompts; SDK parse failures convert to `VNParseError` for the repair loop. Supersedes the text+parse deviation (minified-JSON/`output_truncated` handling removed with it) | User decision: schema-in-prompt wastes tokens and is weaker than provider-enforced structured outputs. Watch: Claude previously rejected the Scene schema ("compiled grammar is too large") — if stage B hits that again on Claude it needs a schema simplification or fallback |
| 2026-06-11 | M9 built as a full two-lens LLM-as-a-judge (`src/vn/judge/` package), not the planned "JudgeTarget protocol + one worked target" skeleton; no pipeline hook — review is a separate CLI step | User goal explicitly asked for a sophisticated playwright/director judge producing improvement feedback, superseding the skeleton scope. Judge-as-separate-tool keeps generation cost unchanged and lets review run on imported scripts too |
| 2026-06-11 | Judge evaluations persist to files (`evaluations/<slug>.json|.md|.guidance.txt`), not the DB | CLI self-improvement loop needs human-readable diffable reports and a `--baseline` file to load; a DB table + migration adds no value until the web UI consumes evaluations |
| 2026-06-11 | `Condition` and `CheckModifier` are each a single object (`var`/`op` xor `visited`, with a `value`; `mod` on the modifier) instead of a `VarCondition`/`VisitedCondition` union. Discriminator on the value form via `is_var`/`is_visited`; a model validator enforces exactly one form. Consumers (`conditions`, `softlock`, `validator`, `judge/rendering`) check the fields, not `isinstance`. Resolves the watch item from the previous row | Stage B's `Scene` structured output still hit Claude's "compiled grammar is too large": per-array-element object unions inside guard/modifier arrays multiply through the `Beat` union. The SDK's `transform_schema` strips discriminators/`const` before sending, so a tag-based discriminator does nothing — only collapsing the union into one object removes the branch point. Legacy persisted scripts (`{var,op,value}` / `{visited,value}`) validate unchanged, so no data migration. The remaining (non-nested) top-level `Beat` union is within the grammar limit |
| 2026-06-11 | Improvement loop closes via `vn-review` guidance file → `vn-generate --guidance`, which appends director's notes to `vn_input.rules` | `rules` already reaches every pipeline stage prompt via `_input_block`; threading a new parameter through 3 stages would duplicate that channel |
| 2026-06-11 | Numeric progress rule: `compare_evaluations(current, baseline, target_score, epsilon)` → improved/plateaued/regressed + stop_target_reached/stop_plateaued/continue/rollback | User requirement: an objective stop condition so an improvement loop cannot flip back and forth indefinitely |
| 2026-06-11 | `load_dotenv()` moved from `src/cli.py` import time into `main()`; `tests/conftest.py` (autouse) scrubs `DATABASE_URL`/`DB_*` and injects dummy API keys; `test_scenario_integration` gets a class-level autouse temp-DB fixture | Importing the CLI from tests loaded `.env`, and `DATABASE_URL` takes precedence over per-test `memory_dir` — test rows leaked into the real dev DB. Env isolation also fixed 19 pre-existing order-dependent test failures. The scenario tests built registries with no `memory_dir`, sharing the repo's stale `./memory/conversations.db` whose `scenarios` table predated `character_id` (`create_all` adds tables, never columns) — a fresh per-test DB matches the current ORM |
| 2026-06-11 | Stage B requests a slim `DraftScene`/`DraftBeat` (id/intent/routing/extension only; no effects/guards/check-modifiers/prerequisites) and lifts it to `Scene` in code via `draft_scene_to_scene` (empty mechanics). Mechanics are authored by stage C's `MechanicsPatch` regardless, so the draft loses nothing. Supersedes the single-object-Condition fix being sufficient on its own | Collapsing the `Condition`/`CheckModifier` unions still left `Scene` at 31 optional / 17 union params — over Claude's combinatorial grammar budget. The draft drops it to 13 optional / 7 union. Field descriptions are carried on the draft models so the model still knows the routing contract. See AGENTS.md "compiled grammar is too large" for the general budget heuristic |
| 2026-06-12 | `DraftPlainBeat` mirrors `PlainBeat`'s "exactly one of next / exit_edges / exit" (and non-empty exit_edges) validator; `SceneGraphStage.run` also wraps `draft_scene_to_scene` so any canonical-validator failure becomes a `VNParseError` | The draft model omitted that validator, so an LLM draft with a routing-less plain beat parsed fine, then raised a hard pydantic `ValidationError` inside `draft_scene_to_scene` — outside `request_model`'s catch — crashing the job (`b_final_entry`, `b_amber_convergence` in the keeper run) instead of feeding the bounded repair loop. Validators are post-parse Python, so neither change touches the compiled-grammar budget |
| 2026-06-12 | All structured VN LLM calls now use request-only Anthropic-friendly models and convert into canonical models afterward: Stage B requests flat `LLMScene`/`LLMBeat`; Stage C requests `LLMMechanicsPatch` with DSL strings for state vars, guards, effects, and check modifiers; judge calls request `LLMLensReview` with string dimensions and empty-string citations. Canonical `Script`, `MechanicsPatch`, and `LensReview` remain the validation/storage models | Anthropic grammar compilation is sensitive to repeated unions, nullables, and nested arrays. Moving those constraints into deterministic conversion plus the existing validator/softlock/judge gates preserves validation while reducing the provider schemas for the major calls to 0 `anyOf`, 0 `oneOf`, and 0 optional fields. Real keeper generation and review smoke runs passed on Claude |
| 2026-06-12 | Generation prompts no longer guide beat counts. Stage B conversion rejects LLM checks whose success/failure target the same beat and choices whose options target the same beat; Stage C gate rejects declared state vars that are never written or never read | The self-improvement loop showed those shapes create false mechanical promises: checks that cannot affect outcome, choices that cannot change content/state, and variables whose fictional setup never pays off. Beat count should be story-shaped, while each beat/choice/check/state var must carry observable structural work |

## Log

- 2026-06-11 — Tracker created alongside `vn_implementation_plan.md`. All milestones `todo`; implementation not started.
- 2026-06-11 — M1–M8 implemented. Backend: 127 tests green (`uv run pytest tests/vn -q`), ruff clean. Frontend: VN component/util tests green (`npm run test:run`). Open items: VN-6.7 (real-LLM smoke run), VN-8.5 (manual browser pass), M9 (deferred by design — VN-9.1 is a spec-gap design task that should precede any judge code).
- 2026-06-11 — Post-smoke-run fixes: scene-count gate dropped, pipeline moved off strict structured outputs to text+parse with repair-loop feedback, generation form input persisted to localStorage. Backend 128 tests green; frontend useFormDraft tests green.
- 2026-06-11 — Second smoke-run round: stage calls now stream (10-minute SDK limit hit on mechanics); generation became a checkpointed, resumable job (new `vn_generation_jobs` table + `/api/vn/generation-jobs` endpoints + library UI section showing partial outline/scenes with Resume). Backend 132 tests green, ruff clean; frontend VN tests green (15).
- 2026-06-11 — Smoke run found a latent shared-processor bug: `self.logger` was only set via `set_logger`, so streaming on a fresh processor (as the VN pipeline does) raised AttributeError in OpenRouter/Claude processors. Fixed by initializing `logger = None` in both constructors; regression test `tests/test_processor_streaming_logger.py` (mocked SDKs). 135 tests green.
- 2026-06-11 — M9 implemented (VN-9.1/VN-9.2 done, beyond the planned skeleton — see deviations): two-lens LLM judge (`src/vn/judge/`, models in `src/models/vn/judge.py`), deterministic script digest, numeric progress/stop rule, markdown+JSON+guidance file reports, CLI `vn-generate`/`vn-review` closing a self-improvement loop. Side fix: CLI import-time `load_dotenv` removed + hermetic test env (`tests/conftest.py`). Verified: `tests/vn` 180 passed; full suite 14 failed/497 passed/19 errors vs 33/455/19 on main — zero new failure names, 19 pre-existing env-dependent failures fixed; ruff clean on changed paths.
- 2026-06-11 — Softlock walk fixed (routing-relevant visited tracking; budget exhaustion now a warning) after a real script blew the node budget and burned repair attempts.
- 2026-06-11 — Mechanics stage redesigned to patch-based output (`MechanicsPatch` + `pipeline/patching.py` + `tests/vn/test_patching.py`); all stages back on structured outputs with no schema in prompts. 140 tests green, ruff clean.
- 2026-06-11 — VN library gained a human-readable Preview modal for saved scripts and unfinished generation jobs; generation job API now returns checkpointed scene details, so in-progress previews show completed scenes plus planned outline scenes. Focused backend/frontend tests and Vite build passed; `vue-tsc --noEmit` remains blocked by the installed vue-tsc/TypeScript compatibility error before project checking.
- 2026-06-11 — Stage B re-hit Claude's "compiled grammar is too large". Verified the cause via the SDK's own `transform_schema`: per-array-element object unions (`Condition`/`CheckModifier`) multiply through the `Beat` union, and the transform strips discriminators/`const` so a tag-based fix is inert. Folded each into a single object (`is_var`/`is_visited` + validator); updated `conditions`/`softlock`/`validator`/`judge.rendering` off `isinstance`. Legacy scripts validate unchanged (no migration). Only the non-nested top-level `Beat` union survives the transform. `tests/vn` 166 passed, ruff clean on changed paths; non-VN suite unchanged vs main (same pre-existing failures). VN-6.7 re-run still pending.
- 2026-06-12 — Reworked VN structured-output request models for Anthropic: flattened scene graph, mechanics DSL patch, and judge request model with post-conversion validation. Verified with schema-budget tests, `uv run pytest tests/vn -q` (177 passed), changed-path ruff, real `keeper_of_the_last_light` generation smoke run (valid script), and real `vn-review` judge smoke run (3.8/5, reports saved).
- 2026-06-12 — Prompt-tuning loop on `examples/vn/keeper_of_the_last_light.json`: initial generation failed on invalid guard DSL (`not flag`), prior smoke review flagged recap beats, inert same-target checks, weak state payoff, and false choices. Updated generation/judge prompts to emphasize structural work without beat-count guidance; added repair-loop gates for same-target checks, duplicate choice targets, and unread/unwritten state vars. Verified: focused tests, `uv run pytest tests/vn -q` (182 passed), changed-path ruff, and a final real keeper generation smoke run producing a valid script with clean deterministic digest checks.
