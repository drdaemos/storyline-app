# Frontend Vision for the Pipeline-Based Storyline App

## 1. Purpose

This document defines a cohesive frontend vision for the new simulation pipeline described in:

- `docs/interactive-npc-design.md`
- `docs/prompt-templates.md`
- `docs/example-walkthrough.md`
- `docs/migration-plan.md`

It also assesses the current repository state and translates backend changes into a concrete frontend information architecture, screens, and implementation direction.

## 2. Repository and Backend Assessment

### 2.1 What is already aligned with the new architecture

The backend already includes core simulation foundations:

- New domain models for rulesets, world lore, session state, character state, event stream, turn requests.
- New services and pipeline modules (`turn_pipeline`, `ruleset_service`, `event_stream_service`, etc.).
- New persistence tables (`rulesets`, `world_lore`, `sessions`, `character_states`, `events`).
- New API surfaces for rulesets, world lore, session state, and turn execution (`POST /api/turn`).

### 2.2 What is still transitional

- Legacy and new flows coexist in places (for example summary-oriented assumptions in UI and some compatibility models in backend).
- Turn pipeline currently hard-blocks non-action input (`relocation` and `time_skip` paths are still TODO in orchestrator flow).
- SSE payload names currently emitted by backend differ from the “ideal” naming in docs. The frontend should include an event adapter layer instead of hard-coding fragile event names.

### 2.3 Frontend gap

Current frontend is still structured around a single-character chat flow:

- Route model is character-first (`/character/:id`, `/chat/:characterId/:sessionId`), not entity-library-first.
- Types/composables still target legacy `interact` semantics and summary modal behavior.
- No independent management surfaces yet for `rulesets` and `world_lore`.
- Scenario UX is still tied to old assumptions and lacks full composition of ruleset + multiple NPCs + lore set + per-character scenario stat overrides.

## 3. Product Vision

The new UI should feel like a **story simulation studio + runtime play console**, not a chatbot wrapper.

Core product principles:

- **Library-first authoring**: rulesets, characters, lore, scenarios are independent reusable assets.
- **Composition over one-off setup**: scenario is an assembly layer, not a place to recreate entities.
- **Play as turn-driven narrative**: user acts, system resolves, narrator renders, options continue.
- **Dual-mode reading**: immersive narrative first, simulation state accessible on demand.
- **Scale to many worlds**: tag-based lore organization and cross-entity filtering are mandatory, not optional.

## 4. Information Architecture

### 4.1 Top-level navigation

Primary nav:

- `Home`
- `Hub`
- `Sessions`
- `Settings`

Nav intent:

- `Play` is not a root nav destination. It remains session-scoped (`/play/:sessionId`).
- `Home` is the default launch surface and includes recent sessions with Resume actions.
- `Hub` is the single entry point for entity libraries plus creation actions.

### 4.2 Route structure

Proposed route tree:

- `/` -> Home dashboard
- `/hub` -> Creation Hub + entity libraries
- `/library/characters`
- `/library/personas`
- `/library/rulesets`
- `/library/world-lore`
- `/library/scenarios`
- `/characters/new`, `/characters/:id`, `/characters/:id/edit`
- `/personas/new`, `/personas/:id`, `/personas/:id/edit` (can reuse character editor with `is_persona = true`)
- `/rulesets/new`, `/rulesets/:id`, `/rulesets/:id/edit`
- `/world-lore/new`, `/world-lore/:id`, `/world-lore/:id/edit`
- `/scenarios/new`, `/scenarios/:id`, `/scenarios/:id/edit`
- `/play/:sessionId`
- `/sessions`
- `/sessions/:id` (session detail with Resume entry to `/play/:sessionId`)

### 4.3 Home screen

Home should be an operational dashboard, not a generic landing page.

Recommended sections:

- **Continue Playing**: last 3-6 sessions with `Resume` and quick metadata (scenario, turn, location/time, last activity).
- **Start New Session**: scenario picker shortcut.
- **Creation Hub shortcut**: one-click path to create new entities.
- **Recent Assets**: last edited characters, personas, rulesets, lore, scenarios.
- **System alerts** (optional): invalid scenario references, missing ruleset links, etc.

### 4.4 Sessions destination

`Sessions` top nav leads to `/sessions`, a full session management view:

- Filters: active, paused, completed, archived.
- Search by scenario name, character/persona, world tag.
- Actions: resume session, rename, archive/delete, inspect state summary.
- Clicking a session row opens `/sessions/:id` with full context and a primary `Resume` button.

### 4.5 Settings scope

`Settings` should include:

- **Model configuration**: large-model and mini-model defaults, backup behavior.
- **Play display preferences**: immersive/tactical default, show dice, show state panel, text density.
- **Creation defaults**: preferred ruleset preset, default scenario template behaviors.
- **Autosave and drafts**: retention policy and clear-drafts controls.
- **Safety and content preferences**: user-level narrative constraints.

## 5. Creation Hub and Authoring Flows

### 5.1 Creation Hub (`/hub`)

Purpose: one launch point for independent entity creation and entity browsing.

Sections:

- “Start from scratch” cards: Character, Ruleset, Lore Entry, Scenario.
- “Personas” card: dedicated entry to persona list/create flow.
- “Build from template” cards: Ruleset presets, Scenario starter kits.
- “Continue drafts” queue: recover unsaved drafts across all entity types.
- “Recent assets” strip: quick jump to recently edited entities.
- “Entity libraries” tabs: Characters, Personas, Rulesets, World Lore, Scenarios (each tab has list + create CTA).

### 5.2 World Lore surfaces

Required screens:

- Lore list with search + tag chips + group by tag.
- Lore detail page with backlinks to scenarios using this lore.
- Lore editor with tag autocomplete and AI-assisted drafting.

Key UX:

- Tag-based filtering is first-class and persistent in URL query params.
- Grouping modes: by tag, by type-hint tag (`location`, `faction`, `history`, etc.), by recently updated.
- Multi-select for scenario composition directly from filtered lore set.

### 5.3 Ruleset surfaces

Required screens:

- Ruleset list/detail/edit/create.
- Schema builder for drives, skills, emotional dimensions.
- Rules text editor with preset starter snippets.

Key UX:

- Live schema sanity checks (range/default/decay validation).
- Preview pane showing how character stat blocks will be generated.
- Warning states for schema changes that could invalidate existing scenarios.

### 5.4 Character surfaces

Required screens:

- Character list/detail/edit/create.
- Persona toggle and labeling.

Persona placement:

- Keep personas as a first-class list (`/library/personas`) for discoverability.
- Reuse character editor and detail components, but present persona-specific labels and filters.

Ruleset stat block integration:

- Base character identity is ruleset-agnostic.
- Scenario assignment layer attaches ruleset-specific starting drives/skills/emotions.
- Character detail page should still show “Known stat profiles by ruleset” where available for reuse.

### 5.5 Scenario Composer

Required capabilities:

- Select one ruleset.
- Select multiple NPCs.
- Select one persona.
- Select lore entries (with tag-filter picker).
- Configure starting world state.
- Set per-character scenario stat overrides based on selected ruleset schema.

UX structure:

- Top: entity selectors.
- Middle: scenario narrative scaffolding (intro, atmosphere, hooks, stakes, goals).
- Bottom: validation + “Save” / “Save & Start Session”.

## 6. Play Experience (Visual Novel + MUD Hybrid)

### 6.1 Interaction model

Play screen should center on a turn log, not chat bubbles.

Turn block format:

- User action line (compact).
- Narration passage (primary text, streamed).
- Optional mechanical strip (dice/check outcomes).
- Continuation options row (cards/buttons).

Input model (two lanes):

- Lane A: click options for fast continuation (short curated set).
- Lane B: command line/freeform input for custom actions.
- Support slash commands (`/regenerate`, `/rewind`) via command palette semantics.
- Include a persistent command guide/help entry point.

Choice clarity:

- Each continuation option should be visually typed by action category (`action`, `dialogue`, `relocation`, `time_skip`).
- Use both icon and color coding (for example, time skip has a distinct clock icon + accent color) so users can parse options quickly.
- Do not rely on color alone; keep text labels for accessibility.

### 6.2 Layout

Main layout:

- Center: Story Feed (dominant column).
- Bottom dock: continuation options + command input.
- Right drawer/panel: world state, present characters, and key drive bars.

Display modes:

- Immersive mode: hides mechanical strip and minimizes state panel.
- Tactical mode: shows dice and state deltas by default.

### 6.3 SSE/event handling

Frontend should implement a normalization layer:

- Accept current backend event names.
- Map them into UI-internal event primitives (`stage`, `dice`, `narrationChunk`, `options`, `state`, `complete`, `error`).
- Isolate naming differences so backend event payload evolution does not force component rewrites.

### 6.4 Control affordances

The play screen should expose recovery controls in-context:

- Undo last turn.
- Regenerate last turn output.
- Quick access to command help and keyboard shortcuts.

These controls should be available without leaving the play screen.

### 6.5 Accessibility baseline

Play UI is text-heavy and should ship with accessibility defaults:

- Adjustable text size and contrast.
- Dyslexia-friendly font option.
- Screen-reader-friendly live region handling for streamed narration.
- Persistent context panel access without requiring pointer precision.

## 7. UI System and Component Architecture

### 7.1 Shared component families

- Entity list grid + card shell.
- Entity selector (single/multi-select, create-inline action).
- Tag input and tag filter bar.
- Schema builder blocks.
- Turn feed blocks (user action, narration, dice strip).
- World state panel + character state cards.

### 7.2 State/composable boundaries

Recommended stores/composables:

- `useEntityLibrary` (rulesets, lore, characters, scenarios).
- `useScenarioComposer`.
- `usePlaySessionState`.
- `useTurnStream`.
- `useDisplaySettings`.

Keep play runtime state isolated from creation/library state to avoid reactive coupling and accidental cache invalidation.

## 8. Migration Plan (Frontend)

### Phase 1: Foundation

- Add new route skeleton and nav shell.
- Introduce typed API client updates for rulesets/lore/scenarios/session state/turn.
- Build SSE normalization adapter.

### Phase 2: Entity library and creation hub

- Implement Creation Hub.
- Implement ruleset and world lore list/detail/create/edit screens.
- Update character screens for new model fields and relationship semantics.

### Phase 3: Scenario composer

- Replace legacy scenario flow with composition-first Scenario Composer.
- Add ruleset-driven per-character stat override UI.
- Wire `Save & Start Session` flow.

### Phase 4: Play view rewrite

- Replace chat UI with turn-feed Play view.
- Implement continuation options + freeform command input.
- Add world state drawer and immersive/tactical display modes.

### Phase 5: Cleanup

- Remove legacy chat-only components and summary modal flow.
- Remove obsolete frontend types/composables tied to old interact contract.

## 9. Key Trade-offs

- Scenario-level stat overrides increase setup complexity, but preserve character reusability across rulesets.
- Dual immersive/tactical modes add UI surface area, but solve split user preferences (story-first vs system-first).
- SSE event normalization is extra work upfront, but prevents brittle coupling while backend contracts settle.

## 10. Assumptions

- `docs/` design docs are the product source of truth.
- Backend endpoint/model evolution will continue during frontend rewrite; adapter-based integration is preferred over direct event-shape coupling.
- Visual language can diverge from current chat UI as long as streaming responsiveness and creation-assistant strengths are preserved.
