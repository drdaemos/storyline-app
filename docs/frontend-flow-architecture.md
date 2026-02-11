# Frontend Flow and UX Architecture (Current State)

## Purpose
This document describes the current frontend behavior and inferred architectural patterns to guide cohesive next UI work. It focuses on user flows, state boundaries, interaction contracts, and extension seams.

## Scope and Perspective
- Perspective: product behavior + client architecture.
- Excludes: implementation snippets and low-level code details.
- Includes: route-level journeys, shared state ownership, API interaction patterns, and current coupling points.

## Core Product Shape
The frontend currently models the experience around **character-centric storytelling**:
- Users pick a character.
- Each character has many sessions.
- Sessions can be started from scenarios (saved, generated, or ad-hoc intro seed).
- Persona selection acts as user-side role in session/scenario creation.

This means scenario workflows are currently attached to a selected character context.

## Route-Level Information Architecture
Current top-level app map:
- `/` : character selection hub.
- `/character/:characterId` : character details + sessions + saved scenarios.
- `/chat/:characterId/:sessionId` : session conversation surface.
- `/create` : character creation assistant.
- `/character/:characterId/edit` : character editing.
- `/character/:characterId/create-scenario` : scenario creation assistant bound to one character.

### Header Navigation
Primary nav currently exposes:
- Characters
- Create

Semantically, Create currently points only to character creation.

## Primary User Flows

### 1. Character Discovery and Selection
Entry flow:
1. Load list of character summaries.
2. Select one character to enter its page.
3. Persist last selected character in local settings.

Outcome: user transitions from global catalog to character-specific workspace.

### 2. Character Workspace (Sessions + Scenario Library)
Character page acts as operational hub:
- Shows character identity details.
- Lists sessions filtered to the character.
- Allows session deletion.
- Provides “new session” entry via scenario modal.
- Shows saved scenarios for the character with quick start.
- Supports direct navigation to scenario creation for this character.

This page combines three domains:
- Identity/profile
- Active conversation threads
- Scenario assets

### 3. New Session Decision Flow (Modal)
The scenario modal is a branching pre-chat funnel:
1. Choose start mode:
   - Assisted scenario creation
   - Quick generation (mood-driven)
   - Skip to chat
2. Persona selection step
3. Optional mood selection
4. Generated scenario list and selection
5. Start session

This flow normalizes “how a session starts” into one dialog and keeps persona/model settings in play.

### 4. Chat Flow
Chat route supports:
- Existing session continuation (loads session history).
- New session bootstrap when route uses `sessionId = new`.

For new bootstrap:
- Requires selected persona.
- Creates session with intro seed, selected persona, and per-session model keys.
- Replaces URL with real session id.

Message lifecycle:
1. User submits prompt.
2. Stream starts via SSE-like fetch stream.
3. UI updates thinking/streaming states.
4. Final assistant message appended when stream completes.
5. Error path supports regenerate/retry.

Auxiliary chat tools:
- Session summary modal.
- Persona badge for current session.

### 5. Character Creation Flow
Character creation is a two-pane assistant:
- Left: conversational assistant stream.
- Right: structured character form that updates in-place.

Supports:
- Fresh creation and edit mode.
- Local draft autosave (create mode).
- Save as character or persona.
- Reset behavior differing by create/edit mode.

### 6. Scenario Creation Flow
Scenario creation is similarly two-pane:
- Left: conversational scenario architect stream.
- Right: structured scenario fields.

Supports:
- Persona selection with optional model suggestion.
- Autosave drafts.
- Save scenario to library.
- Save-and-start session.

Current coupling: scenario creation route requires `characterId` context.

## State Ownership Model

### Global-ish Client State
1. Authentication state
- Clerk-controlled.
- Token fetched lazily for API calls.

2. Local settings singleton
- Large model key.
- Small model key.
- Selected persona id.
- Last selected character.
- Stored in browser local storage and shared across views.

### Route/View Local State
- Per-page entity state (character/scenario form data).
- Per-session chat timeline and stream state.
- Modal step states.
- Transient errors and loading flags.

### Data Source Pattern
- Composables coordinate fetch/stream orchestration.
- Views own presentation-specific state and flow transitions.

## API Interaction Patterns

### Pattern A: Request/Response CRUD
Used for:
- Characters list/info/create/update.
- Sessions list/delete/start.
- Scenario save/list/detail/delete.
- Personas list.

### Pattern B: Streaming orchestration
Used for:
- Interact stream.
- Character creation stream.
- Scenario creation stream.
- Scenario generation stream.

The frontend treats these streams as event lines with event-type routing into UI state.

## UX and Interaction Conventions
- Modals for short branching setup (new session flow, settings, summary).
- Two-pane “assistant + editable structured form” for entity authoring.
- Soft resilience model: retries for transient failures (notably 502).
- Persona choice is propagated as a cross-flow context signal.
- Model choice is currently user-configurable and used per-session creation.

## Current Architectural Strengths
- Clear route separation for major workspaces.
- Reusable composables for auth/settings/API/streaming.
- Unified session-start concept across scenario pathways.
- Strong assisted-authoring pattern already established and reusable.

## Current Architectural Constraints / Couplings
1. Scenario UX is character-bound by route design.
- Limits global scenario tooling and multi-entity orchestration.

2. “Create” IA is single-purpose today.
- Does not yet serve as a generalized creation launcher.

3. Rulesets are not represented in frontend IA.
- No dedicated domain objects, management screen, or upload/import flow.

4. Session start still assumes character-first initiation.
- Good for current story flow, constraining for future ruleset/world-first entry.

## Cohesive Extension Principles for Next UI Phase
For new tools (ruleset loading + decoupled scenario generation), maintain these principles:

1. Keep creation UX pattern consistent
- Reuse modal/assistant/form patterns instead of introducing unrelated interaction models.

2. Split “asset creation” from “session launch”
- Treat rulesets/scenarios/world context as reusable assets.
- Let session launch compose assets rather than own their creation.

3. Promote Create to a launcher
- Convert Create nav to a first-class entry to multiple assisted creation dialogs/workspaces.

4. Preserve persona/model settings as cross-cutting context
- Keep per-session model config explicit.
- Keep persona selection available where session-affecting choices are made.

## Suggested Target IA Direction (Flow-Level)
Short-term cohesive direction:
- Create (top nav) becomes “Creation Hub” with options such as:
  - Character
  - Scenario
  - Ruleset
  - (later) World/Lore pack
- Scenario creation available in two modes:
  - Global (not tied to character route)
  - Character-prefilled (from character workspace)
- Ruleset management added as asset workflow:
  - Import from repository files
  - Validate and register
  - Select as session input

## Migration-Safe UI Strategy
To evolve without major UX fracture:
1. Introduce creation hub first.
2. Add global scenario creation route while keeping character-prefilled entry.
3. Add ruleset asset screens and selection controls.
4. Update session start surfaces to optionally include ruleset/world context selectors.

## Open Design Decisions to Resolve Before Build
- Canonical ownership of ruleset assets: user-scoped vs project-scoped.
- Ruleset import UX: file picker vs repository path selector.
- Where ruleset selection is mandatory: at session creation only, or globally defaultable.
- Scenario identity model in decoupled mode: standalone asset vs character-linked asset with optional relation.

## Browser Extension Note
Requested browser-extension validation was attempted conceptually, but no browser-extension integration surface is exposed in this runtime. This analysis is source-driven. Once extension access is available, a follow-up pass should validate:
- step transitions in modals,
- nav discoverability,
- mobile behavior for creation and chat entry paths,
- and perceived cohesion of the upcoming creation hub.
