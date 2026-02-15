# Frontend Migration Execution Plan (Incremental)

## Goal

Migrate frontend UI in controlled phases:

1. Shadcn foundation and styling system.
2. Art direction approval page.
3. Screen-by-screen overhaul aligned with product vision.
4. Validation gates after each phase (tests, visual QA, flow checks).

## Baseline Assumptions

- Existing heading font (`BBH Sans Bogle`) remains in use.
- Auth bypass remains available for local FE inspection (`VITE_AUTH_BYPASS=true`).
- Legacy screens continue to function during migration to avoid a risky big-bang rewrite.

## Phase Plan

## Phase 1: Foundation (Current)

Scope:
- Initialize `shadcn-vue` and add core UI primitives.
- Introduce global theme tokens, typography, and utility surfaces.
- Keep existing Nuxt UI screens working while starting migration.

Deliverables:
- `frontend/components.json`
- `frontend/src/components/ui/*`
- `frontend/src/lib/utils.ts`
- Updated global styles and fonts.
- Preview route (`/style-lab`).

Quality gate:
- `npm run --prefix frontend type-check`
- `npm run --prefix frontend lint`
- `npm run --prefix frontend test:run`
- Desktop + mobile visual checks on `/style-lab`

Exit criteria:
- Preview page approved for art direction before screen rewrites.

## Phase 2: App Shell Migration

Scope:
- Replace shell-level Nuxt UI components (`UHeader`, nav, global alerts) with shadcn-based app components.
- Introduce route groups and stable app layout wrappers.

Deliverables:
- New shell components: `AppHeader`, `PrimaryNav`, `GlobalErrorBanner`.
- Preserve auth flows and bypass mode.

Quality gate:
- Type/lint/tests.
- Keyboard nav and responsive checks for shell.

## Phase 3: Home/Hub/Sessions/Settings

Scope:
- Implement new IA root:
  - Home dashboard
  - Hub (creation + entity launch)
  - Sessions list/detail
  - Settings panels

Deliverables:
- New routes and composables for dashboard/session summaries.
- Existing character-first entrypoints redirected or de-emphasized.

Quality gate:
- Flow validation:
  - Home -> resume session -> play
  - Hub -> entity list -> create/edit
  - Sessions -> detail -> resume

## Phase 4: Libraries + Creation Flows

Scope:
- Implement independent entity libraries and editors:
  - Characters
  - Personas
  - Rulesets
  - World Lore (tag search/grouping)
  - Scenarios

Deliverables:
- Shared entity list/table/card primitives.
- Ruleset stat-block support in character/scenario surfaces.
- Draft/autosave behavior standardized.

Quality gate:
- Tests for create/edit/list behaviors.
- Visual consistency checks across entity screens.

## Phase 5: Play Screen Overhaul

Scope:
- Replace chat-centric play UI with turn-feed interface.
- Introduce continuation markers, command lane, state rail, and recovery controls.

Deliverables:
- Play layout components (`TurnFeed`, `ContinuationBar`, `StateRail`, `CommandDock`).
- SSE event normalization adapter usage.

Quality gate:
- Streamed turn rendering tests.
- Recovery controls test coverage (`undo`, `regenerate`).
- Desktop/mobile visual checks, readability/accessibility pass.

## Phase 6: Cleanup and Stabilization

Scope:
- Remove obsolete Nuxt UI dependencies and dead UI code.
- Final pass on tokens, spacing, typography, empty/loading/error states.

Deliverables:
- Reduced dependency surface.
- Updated docs and test fixtures.

Quality gate:
- Full FE checks green.
- Smoke tests across all major flows.

## Visual QA Checklist (Each Phase)

- Desktop: 1280-1440 width.
- Tablet: ~768 width.
- Mobile: 390-430 width.
- Focus visibility with keyboard navigation.
- State coverage: loading, empty, error, success.

## Test Strategy

- Add unit tests for new view-level structure and interaction states.
- Add composable tests where domain behavior moved from views.
- Keep backend calls mocked in FE unit tests.
- Run targeted tests first, then full `test:run` for phase completion.

## Rollout Strategy

- Use incremental route-level migrations.
- Keep existing routes functional until replacements are production-ready.
- Maintain feature flags or temporary routes (`/style-lab`) during design validation.
