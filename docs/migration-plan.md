# Migration Plan: Current System to Interactive NPC Design

This document maps every concept from the new design (docs/interactive-npc-design.md, docs/prompt-templates.md) to the existing codebase and specifies exactly what must change.

## 1. Conceptual Shift

The current system is a **1-on-1 chat** between a user and a single AI character, with LLM-generated prose responses, periodic summarization, and a simple evaluation step. The new system is a **multi-character simulation** with a structured turn pipeline, per-NPC state machines, a GM/dice resolution layer, and observation-driven memory.

Key differences:

| Aspect | Current | New |
|--------|---------|-----|
| Characters per session | 1 AI + 1 user | N NPCs + 1 user persona |
| Response generation | Single LLM call produces prose | 8-step pipeline (action gen, GM eval, dice, narration, observations, state update, intent lifecycle, continuation options) |
| Memory | Message log + periodic StorySummary compression | Per-NPC event streams (observations + reflections) with decay |
| State tracking | StorySummary (relationship, plot, physical/emotional state) | Per-character drives, skills, emotional state (defined by ruleset schema) |
| Character behavior | LLM reads full character card + summary + recent messages, writes freeform | LLM generates structured action toward active intent, GM evaluates, narrator writes prose |
| World model | Implicit (embedded in conversation text) | Explicit world state (location, time, characters present) |
| Narration | Character speaks in first person as the response | Third-person narrator produces prose from mechanical outcomes |

---

## 2. New Static Entities

### 2.1 Ruleset (new entity)

No current equivalent. Must be created from scratch.

**DB model**: new `Ruleset` table.

```
Ruleset:
  id: str (primary key)
  name: str
  rules_text: str          # freeform genre/tone/mechanics description
  state_schemas: JSON      # { drives: [...], skills: [...], emotional_state: { global: [...], per_relationship: [...] } }
  config: JSON             # { time_per_turn, importance_threshold, max_event_stream_length, ... }
  user_id: str
  created_at, updated_at
```

**Pydantic models**: `Ruleset`, `DriveSchema`, `SkillSchema`, `EmotionalStateSchema`.

**What it replaces**: The hardcoded `StorySummary` model (`summary.py`) currently defines fixed relationship dimensions (trust, attraction, emotional_intimacy, conflict, power_balance) and fixed emotional/physical state structures. In the new design, all of these are defined per-ruleset as schemas. `StorySummary`, `RelationshipState`, `PhysicalState`, `EmotionalState`, `QualityIssue`, `TimeState`, `PlotTracking` are all removed.

### 2.2 World Lore (new entity)

No current equivalent. The existing `Character.setting_description` and `Character.key_locations` partially serve this role.

World lore is not limited to locations — it can be anything that grounds the narrative: locations, cultural norms, organizations, historical events, technologies, supernatural rules, political factions, notable objects, etc. A tagging system lets users organize and filter lore entries, and lets the engine select relevant lore for prompts based on context.

**DB model**: new `WorldLore` table. Each entry is a single lore article (not a container of many things).

```
WorldLore:
  id: str (UUID)
  name: str                # short title: "Duke's Bar", "The Silence Pact", "Riftstone Technology"
  content: str             # freeform description — as long as needed
  tags: JSON               # list of strings: ["location", "bar", "downtown"], ["faction", "political"], ["history", "war"], etc.
  user_id: str
  created_at, updated_at
```

**Tags** are freeform strings, user-defined. The UI shows existing tags as suggestions (autocomplete from all tags the user has used before). Some tags have engine significance:

- `location` — entries tagged `location` are treated as navigable places. The engine uses these to populate known locations for relocation options (step 6.9) and world state. Location entries should include a `connections` field in their content or as structured metadata (list of other location names reachable from here).
- All other tags are purely organizational. The engine includes lore entries in prompts based on tag relevance to the current context (e.g., if the user is at "Duke's Bar", lore tagged `downtown` or `bar` may be included in the narrator prompt for atmospheric detail).

**Lore selection for prompts**: when assembling context for a step (especially 6.5 Narration), the engine selects lore entries whose tags overlap with: the current location name, the current location's tags, character names, or scenario-level tags. This keeps prompt context relevant without including all lore. A budget limit applies (see design doc section on context budget).

**Scenarios reference lore by selection**: a scenario includes a `lore_ids: list[str]` field — the set of world lore entries relevant to this scenario. Not all of a user's lore needs to be included. The scenario creation screen lets the user pick from their lore library.

**Migration**: `Character.key_locations` and `Character.setting_description` move to WorldLore entries (one entry per location, one for the setting description). These fields are removed from the Character model.

### 2.3 Character Card (revised)

**Existing entity**: `Character` model and `characters` DB table.

**What changes**:

| Field | Current | New |
|-------|---------|-----|
| `name` | kept | kept |
| `tagline` | kept | kept |
| `backstory` | kept | kept |
| `personality` | kept | kept |
| `appearance` | kept | kept |
| `relationships` | `dict[str, str]` freeform | remove (replaced by per-relationship emotional state at runtime) |
| `key_locations` | `list[str]` | remove (moves to WorldLore) |
| `setting_description` | `str` | remove (moves to WorldLore/Scenario) |
| `interests` | kept | kept |
| `dislikes` | kept | kept |
| `desires` | kept | kept |
| `kinks` | `list[str]` | remove or keep as optional flavor text (not mechanically used) |
| `is_persona` | `bool` | kept |
| NEW `starting_drives` | - | `dict[str, number]` — initial drive values per ruleset schema |
| NEW `starting_skills` | - | `dict[str, number]` — skill values per ruleset schema |
| NEW `starting_emotional_state` | - | JSON matching ruleset emotional_state schema |

The character card is now **ruleset-aware**: its starting drives/skills/emotional state must conform to whatever ruleset the scenario references. Validation at scenario-creation time, not at character-creation time (a character can be used across different rulesets).

**`PartialCharacter`**: same changes (all new fields optional).

### 2.4 Scenario (revised)

**Existing entity**: `Scenario` in `api_models.py` and `scenarios` DB table.

**What changes**:

| Field | Current | New |
|-------|---------|-----|
| `summary` | kept | kept (scenario title/name) |
| `intro_message` | kept | kept |
| `narrative_category` | kept | remove (subsumed by ruleset's rules_text) |
| `character_id` | single character ID | remove — replaced by `character_ids: list[str]` |
| `persona_id` | user persona ID | kept |
| `location` | `str` | kept (starting location) |
| `time_context` | `str` | kept (starting time) |
| `atmosphere` | `str` | kept |
| `plot_hooks` | kept | kept |
| `stakes` | kept | kept |
| `character_goals` | `dict[str, str]` | kept (maps character name to starting goal text) |
| `potential_directions` | kept | kept |
| NEW `ruleset_id` | - | references a Ruleset |
| NEW `character_ids` | - | `list[str]` — all NPC characters in this scenario |
| NEW `lore_ids` | - | `list[str]` — references selected WorldLore entries for this scenario |
| NEW `starting_world_state` | - | `{ location, time, characters_present }` |

---

## 3. Dynamic Entities (Runtime State)

### 3.1 Session (revised)

**Existing entity**: Session is currently implicit — it's a `session_id` string used as a key across `messages` and `summaries` tables. There is no Session table.

**New**: Create an explicit `Session` DB table.

```
Session:
  id: str (UUID)
  scenario_id: str
  user_id: str
  world_state: JSON        # { location, time, characters_present: [...] }
  turn_counter: int        # global tick
  narration_history: JSON  # last K narrator outputs
  location_history: JSON   # ordered log of location changes
  status: str              # 'active', 'paused', 'completed'
  snapshot: JSON           # full state snapshot at last turn boundary (for regeneration)
  created_at, updated_at
```

**What it replaces**: The current pattern of using `session_id` as a foreign key in `messages` and `summaries`. The new Session table owns the world state and turn counter.

### 3.2 Character State (new, per-character per-session)

No current equivalent at this granularity. The current `StorySummary` tracks some state globally; the new design tracks it per character.

**DB model**: new `CharacterState` table.

```
CharacterState:
  id: int (auto)
  session_id: str
  character_id: str
  drives: JSON             # { drive_name: current_value, ... }
  skills: JSON             # { skill_name: current_value, ... }
  emotional_state: JSON    # { global: { dim: value }, per_relationship: { target: { dim: value } } }
  active_intent: JSON | null  # { goal, success_condition, source_refs }
  is_present: bool         # whether at user's current location
  intended_destination: str | null  # if offscreen, where they were heading
  last_departure_tick: int | null
```

**What it replaces**: `RelationshipState`, `EmotionalState`, `PhysicalState` from `summary.py`. The current fixed-schema relationship tracking (trust/attraction/emotional_intimacy/conflict/power_balance) is replaced by ruleset-defined per-relationship emotional dimensions.

### 3.3 Event Stream (new, per-character per-session)

No current equivalent. This replaces the Message + Summary memory system for NPC behavior.

**DB model**: new `Event` table.

```
Event:
  id: str (e.g., "obs-50", "ref-10")
  session_id: str
  character_id: str        # which NPC's stream this belongs to
  type: str                # 'observation' or 'reflection'
  tick: int                # turn number when created
  subject: JSON            # list of character/entity names this concerns
  content: str             # natural language description
  importance: int          # 1-5
  decay_rate: float        # observations decay faster than reflections
  initial_decay: float     # starting decay value
  source_refs: JSON        # list of event IDs this was derived from
  visibility: str | null   # 'public' or 'actor_only' (observations only)
  created_at
```

**What it replaces**:
- **`messages` table**: no longer used for NPC memory. The `messages` table can be repurposed or retained solely for storing raw narration history (the user-facing story text), but it is no longer the memory substrate for character behavior.
- **`summaries` table**: removed entirely. The hierarchical message → summary compression is replaced by the event stream with importance-weighted decay. There is no summarization step.
- **`SummaryMemory` service**: removed.
- **`ConversationMemory` service**: substantially changed — it may be retained to store narration outputs for the user-facing chat log, but its role in feeding character prompts is eliminated.

### 3.4 Narration History

The user-facing chat log (what the user reads) is now the output of step 6.5 (Narration). This is stored as part of the Session's `narration_history` (sliding window of last K turns) and optionally in a simplified `messages`-like table for the full chat transcript.

**Retained (modified)**: The `messages` table can store narration outputs and user inputs as a chronological log for display purposes. But the `role` field changes meaning:
- `user` = user input text
- `narration` = narrator output (third-person prose)
- Remove `evaluation` type (the Evaluation model is eliminated)
- Remove `assistant` role (no single-character response anymore)

---

## 4. Services: What Changes

### 4.1 Services to Remove

| Service | Reason |
|---------|--------|
| `CharacterResponder` | Core interaction engine. Entirely replaced by the turn pipeline. The single-LLM-call response generation is replaced by the 8-step flow. |
| `SummaryMemory` | Replaced by event stream decay. No more periodic summarization. |
| `Evaluation` model + evaluation step in `CharacterResponder` | The evaluation step (patterns_to_avoid, status_update, time_passed) is replaced by structured GM evaluation (6.3) and programmatic state tracking. |
| `CharacterPipeline` (`character_pipeline.py`) | The pipeline concept survives but is completely rewritten as the Turn Pipeline. |
| `ScenarioGenerator` | Needs significant revision — scenarios now reference rulesets and multiple characters. |

### 4.2 Services to Create

| Service | Responsibility |
|---------|---------------|
| `TurnPipeline` | Orchestrates steps 6.1 through 6.10. Manages the turn lifecycle, calls sub-steps, handles fault tolerance and rollback. |
| `InputClassifier` | Step 6.1 — classifies freeform user input as action/relocation/time_skip. |
| `ActionGenerator` | Step 6.2 — generates one action per NPC. Parallel execution. |
| `GMEvaluator` | Step 6.3 — evaluates actions for skill checks, determines DCs and drive effects. |
| `DiceResolver` | Step 6.4 — programmatic dice resolution. No LLM. |
| `Narrator` | Step 6.5 — produces streamed prose from action outcomes. |
| `ObservationExtractor` | Step 6.6 — extracts observations from narration. |
| `CharacterProcessor` | Step 6.7 — per-NPC state diffs and optional reflection. |
| `IntentManager` | Step 6.8 — intent lifecycle (reevaluation, generation, completion check). |
| `ContinuationGenerator` | Step 6.9 — generates user continuation options. |
| `WorldTraversalService` | Section 7 — handles relocation, time skips, NPC entry/departure/offscreen. |
| `EventStreamService` | Manages per-character event streams: add observations/reflections, compute decay, assemble memory for prompts, prune. |
| `SessionStateService` | Manages session state: world state, snapshots, turn counter. Handles snapshot save/restore for regeneration. |
| `RulesetService` | Loads rulesets, validates state against schemas, applies programmatic state updates (drive decay, effect application, range clamping). |

### 4.3 Services to Keep (modified)

| Service | Changes |
|---------|---------|
| `CharacterLoader` | Unchanged in role. Loads characters from DB. May need to also load starting drive/skill values. |
| `CharacterManager` | Unchanged in role. Validation needs updating for new character card fields. |
| `CharacterCreator` / `CharacterCreationAssistant` | Keep, but generated characters need starting drives/skills appropriate to a ruleset. May need ruleset context during creation. |
| `ScenarioCreationAssistant` | Keep, but scenario creation now requires selecting a ruleset and multiple characters. |
| `PromptProcessor` / `PromptProcessorFactory` | Unchanged. The abstraction over LLM providers stays. Turn pipeline steps just call `respond_with_model()` or `respond_with_stream()`. |
| `ChatLogger` | Keep for debugging. |

---

## 5. Prompt Processor Usage Changes

The current system makes 2-3 LLM calls per user message (evaluation + response, occasional summary). The new system makes 2N + 4 unconditional calls per turn (N = number of NPCs present), plus conditional calls for intent lifecycle.

**Model tier mapping**:
- `mini` calls (6.1, 6.2, 6.6, 6.7, 6.8, 6.9): use cheap/fast models (e.g., Gemini Flash, Haiku, Deepseek).
- `large` calls (6.3, 6.5): use expensive/capable models (e.g., Claude Sonnet, Gemini Pro).

The `PromptProcessor` interface needs no change — it already supports `respond_with_model()` (structured JSON output) and `respond_with_stream()` (freeform streaming). Each pipeline step will select the appropriate processor tier.

The `InteractRequest` currently sends a single `processor_type`. This should be expanded to allow separate processor selection for mini vs. large calls, or default to a sensible pairing.

---

## 6. Database Migration

### Tables to Create

1. **`rulesets`** — Ruleset definitions with state schemas.
2. **`world_lore`** — Individual lore entries with freeform tags (locations, factions, history, etc.).
3. **`sessions`** — Explicit session table with world state, turn counter, snapshots.
4. **`character_states`** — Per-character per-session runtime state (drives, skills, emotions, intent).
5. **`events`** — Per-character event stream (observations and reflections).

### Tables to Modify

6. **`characters`** — Add `starting_drives`, `starting_skills`, `starting_emotional_state` (JSON columns). Remove `key_locations`, `setting_description` fields from character_data JSON. Keep `is_persona`.
7. **`scenarios`** — Add `ruleset_id`, `character_ids` (JSON list), `lore_ids` (JSON list), `starting_world_state` (JSON). Remove `narrative_category`. Change `character_id` → `character_ids`.
8. **`messages`** — Repurpose as narration log. Change `role` check constraint to `('user', 'narration')`. Remove `character_id` (no longer single-character). Remove `type` column (no more evaluation type). Keep `session_id`, `offset`, `content`, `user_id`.

### Tables to Remove

9. **`summaries`** — Replaced entirely by the event stream + session snapshots. Drop table.

---

## 7. Frontend Changes

### 7.1 Session/Chat Experience

The current `ChatView` displays a simple user ↔ character message stream. The new experience is:

1. **Turn-based display**: each turn shows narrator prose (streamed), then continuation options.
2. **Multi-character**: narration references multiple NPCs. No single "character response" — the narrator describes everyone's actions.
3. **Continuation options**: presented as clickable buttons/cards after each narration. User can also type freeform.
4. **World state sidebar** (optional): show current location, time, characters present, and optionally character drive/emotional summaries.

**Changes to `ChatView.vue`**:
- Message display: instead of alternating user/assistant bubbles, show user input + narration blocks.
- Add continuation options UI after each narration.
- Replace `InteractRequest` with a new turn request that sends user input type (action/relocation/time_skip) and content.
- Streaming still works via SSE but the event types change (narration chunks instead of character response chunks).

### 7.2 Character Page

`CharacterPageView.vue` currently shows one character's details and its scenarios. With multi-character scenarios, the relationship between characters and scenarios changes:

- A scenario references multiple characters, not one.
- The character page can still list scenarios that include this character, but scenario creation now requires selecting characters from a pool.

### 7.3 Scenario Creation

`ScenarioCreationView.vue` needs to support:
- Selecting a ruleset.
- Selecting multiple NPC characters.
- Selecting a user persona.
- Defining starting world state.

### 7.4 New: Ruleset Management

New views for creating/editing rulesets:
- Define drives, skills, emotional state dimensions.
- Write freeform rules text.
- Preview the generated schemas.

### 7.5 Character Creation

`CharacterCreationView.vue` — mostly unchanged, but may need a step where starting drives/skills are set (once a target ruleset is known).

---

## 8. API Endpoint Changes

### Endpoints to Remove

| Endpoint | Reason |
|----------|--------|
| `POST /api/interact` | Replaced by new turn endpoint. |
| `GET /api/sessions/{session_id}/summary` | Summaries no longer exist. Replace with session state endpoint. |

### Endpoints to Add

| Endpoint | Purpose |
|----------|---------|
| **Rulesets** | |
| `GET /api/rulesets` | List rulesets |
| `POST /api/rulesets` | Create ruleset |
| `GET /api/rulesets/{id}` | Get ruleset detail |
| `PUT /api/rulesets/{id}` | Update ruleset |
| `DELETE /api/rulesets/{id}` | Delete ruleset |
| **World Lore** | |
| `GET /api/world-lore` | List lore entries (supports `?tag=` filter) |
| `POST /api/world-lore` | Create lore entry |
| `GET /api/world-lore/{id}` | Get lore entry |
| `PUT /api/world-lore/{id}` | Update lore entry |
| `DELETE /api/world-lore/{id}` | Delete lore entry |
| `GET /api/world-lore/tags` | List all tags used by this user (for autocomplete) |
| **Turn** | |
| `POST /api/turn` | Submit user input and execute turn pipeline. Returns SSE stream: narration chunks, then final event with continuation options, updated world state. |
| `POST /api/turn/regenerate` | Re-run turn from last snapshot (new dice rolls, new narration). |
| **Session State** | |
| `GET /api/sessions/{id}/state` | Get full session state (world state, all character states, event streams). |
| `GET /api/sessions/{id}/characters` | List characters in session with current state summaries. |

### Endpoints to Modify

| Endpoint | Change |
|----------|--------|
| `POST /api/sessions/start` | Now requires `scenario_id` (which references a ruleset). Must initialize world state, all character states, generate initial intents for each NPC. |
| `POST /api/scenarios/save` | Scenario now has `ruleset_id`, `character_ids`, etc. |
| `POST /api/scenarios/generate-stream` | Scenario generation must account for rulesets and multi-character setup. |

---

## 9. Models Removed (full list)

These Pydantic models and DB entities are eliminated:

| Model | File | Replaced By |
|-------|------|-------------|
| `StorySummary` | `models/summary.py` | Session state + CharacterState + Event streams |
| `RelationshipState` | `models/summary.py` | Ruleset-defined per-relationship emotional state in CharacterState |
| `PhysicalState` | `models/summary.py` | Not tracked as a separate model. Physical positioning is in narration; drive-based state is in CharacterState.drives |
| `EmotionalState` | `models/summary.py` | Ruleset-defined emotional state in CharacterState |
| `PlotTracking` | `models/summary.py` | Replaced by intent system + event streams. No explicit plot thread tracking. |
| `TimeState` | `models/summary.py` | Session.world_state.time (programmatic) |
| `QualityIssue` | `models/summary.py` | Removed. Quality control is handled by prompt engineering in each step, not tracked state. |
| `Evaluation` | `models/evaluation.py` | Eliminated entirely. Its functions are distributed: patterns_to_avoid → prompt instructions; status_update → GM evaluation + observation extraction; time_passed → programmatic turn counter. |
| `Summary` (DB) | `memory/db_models.py` | Event streams with decay |
| `ActionPlan` | `models/action_plan.py` | Intent system |

---

## 10. Models Added (full list)

| Model | Purpose |
|-------|---------|
| `Ruleset` | Defines mechanical layer: rules text + drive/skill/emotion schemas |
| `DriveSchema` | Schema for a single drive (name, range, default, decay_rate, offscreen_baseline) |
| `SkillSchema` | Schema for a single skill (name, range) |
| `EmotionalDimSchema` | Schema for one emotional dimension (name, range, default, offscreen_baseline) |
| `WorldLore` | Individual lore entry: name, content, tags |
| `WorldState` | Current location, time, characters present |
| `CharacterState` | Per-character runtime: drives, skills, emotional state, intent |
| `Intent` | Goal, success_condition, source_refs |
| `SuccessCondition` | type (drive_threshold/narrative), drive, operator, threshold, description |
| `Event` | Observation or reflection in a character's event stream |
| `Observation` | subject, content, importance, visibility, actor |
| `Reflection` | subject, content, importance, source_refs |
| `CharacterAction` | type (action/dialogue/reaction), target, description |
| `GMEvaluation` | check_required, skill, dc, contested_with, drive_effects, departure |
| `ActionOutcome` | character, action, result (success/failure), roll_details |
| `StateDiff` | stat, target, change, reasoning |
| `ContinuationOption` | type (action/dialogue/relocation/time_skip), description, target |
| `TurnSnapshot` | Complete serializable state at a turn boundary |
| `Session` (DB) | Explicit session table |
| `CharacterState` (DB) | Per-character per-session state table |
| `Event` (DB) | Event stream entries table |
| `Ruleset` (DB) | Rulesets table |

---

## 11. Functionality Deduplication

Several current features become redundant or are absorbed into the new pipeline:

| Current Feature | Status |
|----------------|--------|
| `/regenerate` command in CharacterResponder | Replaced by `POST /api/turn/regenerate` using session snapshots |
| `/rewind` command in CharacterResponder | Replaced by restoring a previous snapshot (snapshots are saved per turn) |
| Periodic summarization (every N messages) | Eliminated. Event stream with decay replaces compression. |
| Evaluation step (patterns_to_avoid, time_passed, etc.) | Eliminated. Functions distributed across pipeline steps. |
| Character `to_prompt_card()` | Kept but simplified — no more `include_world_info` flag (world info lives in WorldLore). |
| `ScenarioGenerator.generate_scenarios()` | Revised — must generate multi-character scenarios with ruleset reference. |
| Persona suggestion in scenario creation | Kept — persona selection is still part of scenario setup. |

---

## 12. Implementation Order (suggested)

1. **Ruleset + state schema models** — foundation everything else depends on.
2. **Character card revisions** — add starting drives/skills/emotional state fields.
3. **Session + CharacterState + Event DB tables and services** — runtime state infrastructure.
4. **Turn pipeline skeleton** — orchestrator with stub steps.
5. **Steps 6.2-6.4** (action gen, GM eval, dice) — the mechanical core.
6. **Step 6.5** (narration) — user-visible output, streaming.
7. **Steps 6.6-6.7** (observation extraction, character processing) — memory and state update.
8. **Step 6.8** (intent lifecycle) — NPC goal management.
9. **Steps 6.1, 6.9** (input classification, continuation options) — user interaction.
10. **Section 7** (world traversal) — relocation, time skips, NPC entry/departure.
11. **Section 8** (persistence, snapshots, regeneration) — fault tolerance.
12. **Scenario + Ruleset creation UI** — frontend for authoring.
13. **Chat UI overhaul** — turn-based display with continuation options.
14. **Remove old services and models** — clean up deprecated code.

---

## 13. What to Carry Forward from the Current System

The new design's prompt templates (docs/prompt-templates.md) are structurally correct but deliberately generic — they specify *what* each step outputs, not *how well* it should be written. The current system has accumulated significant prompt craft that should be preserved. This section maps each reusable element to the specific new pipeline step it belongs in, with notes on what must be adapted to avoid violating the new system's constraints.

### 13.1 Narration Quality (applies to step 6.5 — Narrator)

The current character response prompt contains a mature writing style framework. The new Narrator prompt (6.5) should absorb these guidelines into its system prompt, since the narrator is now the sole producer of user-facing prose.

**Carry forward verbatim or near-verbatim:**

- **Prose style direction**: "Write in a way that's sharp and impactful; keep it concise. Skip the flowery, exaggerated language." and the reference to Hemingway, Woolf, Thompson as stylistic anchors. The new narrator prompt says "vivid, engaging prose" which is too vague — it needs this specific aesthetic direction.
- **Show don't tell**: "Bring scenes to life with clear, observable details — body language, facial expressions, gestures, and the way someone speaks. Do not over-explain character emotions or reactions; let the user infer them from context, actions, and dialogue." The new prompt's "Show character through behavior" bullet is a weaker version of this.
- **Sensory grounding**: "Do not use vague descriptors or euphemisms; be specific and concrete in displaying physical actions and emotions — create vivid, true-to-life imagery, state things as they are." This specificity is missing from the new narrator prompt entirely.
- **Pacing awareness**: "Vary pacing. Some turns call for a slow beat; others for something quick and sharp. Match the energy of what's happening." Present in the new prompt but less direct.
- **Response length guidance**: The current system's "Aim for 3-6 sentences for general responses. Write more only for significant time skips, setting changes, or important internal monologue" is a valuable calibration. The new narrator prompt has no length guidance at all. Adapt to: default 3-8 sentences per turn (slightly longer because multiple characters act), extend for relocations and significant events.

**Carry forward with adaptation:**

- **No moralizing**: "Never moralize or lecture the user — generally avoid judgmental tone." Still applies to the narrator. The narrator should not editorialize on characters' choices.
- **No questions at end**: "Never end response with 'Do you want [X] or [Y]?'" — in the new system, this is structurally enforced (continuation options are a separate step 6.9), but the narrator prompt should still explicitly say: "Do not end with questions or prompts for the reader. The narration is a passage, not a conversation."
- **Dialogue voice**: "If a character's action was dialogue, write their actual words. Dialogue should sound like that specific character, not generic." Carry forward. The new prompt has this but the current wording is stronger.

**Do NOT carry forward to narrator:**

- First-person perspective instructions (narrator writes third-person)
- Character thinking/internal monologue instructions (narrator describes only observable behavior — internal states are in character processing step 6.7)
- "Do not narrate from user's perspective" — in the new system the narrator describes all characters equally including the user persona
- Response formatting with asterisks for actions and quotes for dialogue — the new narrator writes continuous prose, not chat-formatted text

### 13.2 Character Authenticity (applies to step 6.2 — Action Generation)

The current system has an exceptional character authenticity framework that the new action generation prompt (6.2) should absorb. The new 6.2 prompt is purely mechanical ("stay in character") without any of this nuance.

**Carry forward into the 6.2 system prompt:**

- **Foundation not checklist**: "Treat character information as foundation, not a checklist. A carpenter doesn't mentally recite 'I am a carpenter' in every scene — they simply exist and act naturally." This is the single most important carry-forward. Without it, NPC actions will feel like trait demonstrations.
- **Contradictions are realistic**: "Real people are contradictory and situational. Someone 'confident' can still doubt themselves; someone 'introverted' can still be chatty with the right person in the right moment." This prevents robotic adherence to stated traits.
- **Organic emergence**: "Let unstated aspects emerge organically. Characters can have interests, reactions, or quirks not explicitly listed. They're people, not data points." Prevents action generation from being bounded to only what's on the character card.
- **Emotional state over trait matching**: "'Would a real person in this emotional state do this?' matters more than 'Does this match trait #3?'" Directly relevant — the action prompt receives emotional state as input, and this guideline tells the LLM to weight it above static personality.
- **Knowledge limitations**: "Respect knowledge limitations, do not be omniscient: characters only know what they've experienced or been told." Critical for the new system where information asymmetry is a core mechanic (characters only see observations distributed to them).

**Carry forward with adaptation:**

- **Character autonomy**: "Character pursues their own agenda and wishes actively; they are not obliged to serve the user's wishes." Adapt to: the character acts toward their active intent, not toward what would be convenient for the user's story. The intent system enforces this structurally, but the prompt should reinforce it.
- **Plot momentum**: "Avoid stalling — keep the narrative moving forward. Characters should take actions rather than endlessly asking questions or waiting for permission." Adapt to action generation context: the character's action should be concrete and advancing, not passive observation or hesitation (unless that's genuinely in character given low composure/confidence).

**Do NOT carry forward to action generation:**

- Writing style guidelines (action gen outputs structured JSON, not prose)
- Response length guidance (actions are short structured descriptions)
- Formatting instructions (no asterisks/quotes — structured output)

### 13.3 Anti-Repetition and Quality Control

The current system has a two-layer quality control mechanism: (1) the Evaluation prompt detects repetitive phrases, echoing, and cliches, and (2) the StorySummary persists `ai_quality_issues` which are injected into subsequent prompts. The new design eliminates both, relying on per-step prompt engineering. This is a regression risk.

**What to carry forward:**

The detection categories from `QualityIssue` are valuable and should be embedded as negative instructions in the relevant new prompts:

| Quality Issue | Which New Step | How to Embed |
|--------------|----------------|--------------|
| `repetitive_phrase` | 6.5 Narrator | Add to narrator system prompt: "Do not reuse distinctive phrases, metaphors, or sentence structures from the recent narration history. If the same image or turn of phrase appeared in the last 3 turns, find a different way to express it." |
| `echoing_user` | 6.5 Narrator | "Do not paraphrase the user's input text. The user's action is already established — describe its consequences and other characters' reactions, not a restatement of what the user said." |
| `purple_prose` | 6.5 Narrator | Already addressed by the Hemingway/sharp-and-impactful style direction from 13.1. |
| `character_sheet_fixation` | 6.2 Action Gen | Already addressed by the "foundation not checklist" guideline from 13.2. |
| `physical_impossibility` | 6.3 GM Eval | Add to GM system prompt: "Flag any action that is physically impossible given current positioning or circumstances as auto-fail, not as a check. Characters cannot interact with objects or people not present." |
| `over_analysis` | 6.2 Action Gen, 6.7 Char Processing | The `reasoning` fields in both steps already channel analytical output into a structured field rather than the narrative. Reinforce: "The reasoning field is for your analytical process. The action/reflection is for the character's behavior. Do not bleed analysis into character output." |

**Structural replacement for the feedback loop:**

The current system's loop (detect issue → store in summary → inject into future prompts) is eliminated. The new system's equivalent is:

- The **narration history** (last K turns fed to step 6.5) gives the narrator its own recent output to avoid repeating. Add an explicit instruction: "Review the recent narration below. Do not repeat distinctive phrases, imagery, or sentence patterns from it."
- Per-NPC **event streams** naturally avoid echoing because observations are third-person factual (not prose), and the narrator never sees them.
- There is no cross-turn quality state accumulation. This is acceptable — the sliding window of recent narration provides sufficient context for repetition avoidance without needing persistent quality tracking.

### 13.4 Scene Analysis and Situational Awareness

The current Evaluation prompt performs rich scene analysis: body language interpretation, subtext detection, emotional undertone, physical positioning, environmental details, and pacing assessment. This analysis feeds directly into the character response. In the new system, this analytical function is distributed:

| Current Evaluation Function | New System Equivalent |
|----------------------------|----------------------|
| "What is happening visibly?" | Step 6.6 — observation extraction captures visible events |
| "What body language or non-verbal cues are present?" | Step 6.5 — narrator should describe these in prose. Add to narrator prompt: "Show body language, non-verbal cues, and behavioral tells. Characters communicate as much through what they don't say as what they do." |
| "What might be the underlying intent or subtext?" | Step 6.7 — character processing reflections capture character-specific interpretation of subtext |
| "How does this relate to the ongoing dynamic?" | Step 6.7 — reflections and state diffs capture relationship impact |
| "What emotional undertone is present?" | Step 6.7 — emotional state diffs |
| Physical state tracking (position, clothing, contact) | Partially lost. The narrator describes physical state in prose, but it's not tracked structurally. **Recommendation**: add a `physical_notes` field to the observation schema for position-relevant details (e.g., "Marta is standing with her back to the table"). This is lighter than the current `PhysicalState` model but prevents continuity errors. |
| Environmental details and notable objects | Step 6.5 — narrator prompt already says "Bring the world alive" but should be stronger: "Ground each passage in the physical space. Where are characters positioned? What can they see, hear, smell? What objects are within reach?" This is the current prompt's strength. |
| Time tracking | Programmatic (turn counter + world state time). No LLM needed. |
| Pacing assessment | No direct equivalent. The narrator should self-assess pacing from the narration history. Add: "Assess pacing from recent narration. If the last turns were slow and conversational, consider whether this turn needs more momentum. If recent turns were action-heavy, allow a slower beat if the content supports it." |

### 13.5 Character Card Assembly

The current `to_prompt_card()` method produces a well-structured prompt representation with labeled sections (`[Backstory]`, `[Personality]`, etc.) and a field-description guidance block explaining how each field should be used. The new design doesn't specify a card format.

**Carry forward:**

- The labeled section format (`[Backstory]`, `[Personality]`, `[Desires]`, etc.) — clean, parseable, and proven. Adapt for new fields: add `[Starting Drives]`, `[Starting Skills]` sections when relevant.
- The "Character Description Guidance" block that explains how to *use* each field (backstory is foundation not biography, personality shows tendencies not laws, desires drive autonomous action, etc.). This should be included in the 6.2 Action Generation system prompt, not in the card itself — the card is data, the guidance is instruction.
- The controller label (`[Controlled by AI]` / `[Controlled by User]`) — still relevant for steps that see multiple character cards (e.g., 6.3 GM evaluation, 6.5 narration).

**Adapt:**

- Remove `[Kinks]` field from prompt cards if the field is removed from the character model, or keep as `[Preferences]` if retained as flavor text.
- Remove `[Relationships]` from the card — runtime per-relationship emotional state replaces it. The card may retain a `[Background Relationships]` field for narrative context (e.g., "Marta and Ren have been roommates for two years") but not as tracked state.
- `include_world_info` flag is no longer needed — world info comes from WorldLore, not the character card.

### 13.6 User Learning Accumulation

The current StorySummary has a `user_learnings` field that captures meta-preferences ("User prefers direct action over atmospheric buildup", "User dislikes when character over-explains emotions"). This is eliminated in the new design, which has no cross-turn preference tracking.

**Recommendation:** This is a genuine loss. User preferences affect narration quality significantly. Two options:

1. **Session-level preferences field**: Add an optional `user_preferences: list[str]` to the Session model. Updated manually by the user (settings panel) or extracted by a lightweight post-turn analysis. Injected into the narrator prompt (6.5) as style directives.
2. **Defer**: Accept the loss for now. The narrator's style is governed by the ruleset's rules_text (which can include tone guidance) and the prompt craft from 13.1. If users report quality regressions, add preference tracking later.

Option 2 is recommended for initial implementation — the ruleset's freeform rules text is the right place for per-game style direction, and it's authored upfront rather than detected at runtime.

### 13.7 Content Policy

The current `processor_specific_prompt` (content policy block) is returned by each PromptProcessor and injected into character response and evaluation prompts. It permits mature content for story realism while excluding harmful content involving minors, self-harm instructions, and hate speech.

**Carry forward:** This policy applies to the new system's creative output steps:
- **6.2 Action Generation**: NPC actions may involve mature themes appropriate to the scenario.
- **6.5 Narration**: The narrator must be able to depict mature content when the scenario calls for it.
- **6.7 Character Processing**: Reflections may reference mature themes.

Inject the content policy into the system prompts of these three steps. The GM evaluation (6.3), observation extraction (6.6), and continuation options (6.9) are mechanical/analytical and don't need it.

### 13.8 Summary of Prompt Enrichments by Step

| Step | What to add from current system |
|------|-------------------------------|
| 6.2 Action Gen | Character authenticity framework (13.2), character card usage guidance (13.5), autonomy/plot momentum (13.2), knowledge limitations (13.2), anti-fixation (13.3), content policy (13.7) |
| 6.3 GM Eval | Physical impossibility detection (13.3) |
| 6.5 Narration | Full writing style framework (13.1), anti-repetition (13.3), anti-echoing (13.3), scene grounding / environmental detail (13.4), pacing self-assessment (13.4), body language and subtext (13.4), content policy (13.7), no moralizing (13.1) |
| 6.6 Observations | No changes needed — extraction is mechanical |
| 6.7 Char Processing | Anti-over-analysis in reasoning vs. output (13.3), content policy (13.7) |
| 6.8 Intent | No changes needed — lifecycle checks are mechanical |
| 6.9 Continuation | No changes needed — option generation is mechanical |

---

## 14. Frontend Changes (Detailed)

This section describes the frontend UX at a level sufficient for implementation planning. The goal is to preserve the current app's strengths (conversational creation assistants, streaming, clean navigation) while supporting the new multi-character, turn-based, ruleset-driven architecture.

### 14.1 Navigation Structure

The current router has 5 routes centered around single-character workflows. The new structure needs routes for rulesets, multi-character scenario assembly, and a revised chat experience.

**Proposed routes:**

| Route | View | Notes |
|-------|------|-------|
| `/` | `HomeView` | Landing page — recent sessions + quick actions |
| `/characters` | `CharacterListView` | Browse characters and personas (current `CharacterSelectionView`, adapted) |
| `/characters/create` | `CharacterCreationView` | Create character (current flow, adapted — see 14.4) |
| `/characters/:id` | `CharacterDetailView` | View character, sessions and scenarios involving it (see 14.8) |
| `/characters/:id/edit` | `CharacterCreationView` | Edit character |
| `/rulesets` | `RulesetListView` | Browse rulesets (new — see 14.9) |
| `/rulesets/create` | `RulesetCreationView` | Create ruleset (new — see 14.5) |
| `/rulesets/:id` | `RulesetDetailView` | View ruleset detail |
| `/rulesets/:id/edit` | `RulesetCreationView` | Edit ruleset |
| `/world-lore` | `WorldLoreListView` | Browse world lore entries (new — see 14.9) |
| `/world-lore/create` | `WorldLoreCreationView` | Create world lore (new — see 14.6) |
| `/world-lore/:id` | `WorldLoreDetailView` | View world lore detail |
| `/world-lore/:id/edit` | `WorldLoreCreationView` | Edit world lore |
| `/scenarios` | `ScenarioListView` | Browse scenarios (new — see 14.9) |
| `/scenarios/create` | `ScenarioCreationView` | Create scenario — selects existing entities, AI-assisted (see 14.7) |
| `/scenarios/:id` | `ScenarioDetailView` | View scenario detail, start session (see 14.10) |
| `/scenarios/:id/edit` | `ScenarioCreationView` | Edit scenario |
| `/play/:sessionId` | `PlayView` | Turn-based play experience (replaces `ChatView` — see 14.3) |

**Key navigation changes:**
- Each entity type (characters, rulesets, world lore, scenarios) has its own dedicated list/create/detail/edit routes. Entities are created independently and composed at scenario level.
- The entry point to a play session is: browse scenarios → view scenario detail → "Start New Session". Or from home: resume a recent session.
- The home page shows recent sessions prominently (resume play), with quick links to all entity management pages.
- Characters, rulesets, and world lore are reusable building blocks. Scenarios reference them. Sessions are instances of scenarios.

### 14.2 Home / Dashboard

**Current**: `CharacterSelectionView` — a grid of character cards. Clicking a character navigates to their page.

**New**: `HomeView` — the primary landing experience.

**Layout:**

```
+--------------------------------------------------+
|  [Settings]                         [User avatar] |
+--------------------------------------------------+
|                                                    |
|  Recent Sessions                                   |
|  +----------+ +----------+ +----------+            |
|  | Session 1| | Session 2| | Session 3|  ...       |
|  | "Apt kit"| | "Market" | | "Forest" |            |
|  | 12m ago  | | 2h ago   | | yesterday|            |
|  | Turn 7   | | Turn 3   | | Turn 15  |            |
|  +----------+ +----------+ +----------+            |
|                                                    |
|  [+ New Session]                                   |
|                                                    |
|  Quick Links                                       |
|  [Characters] [Rulesets] [World Lore] [Scenarios]  |
|                                                    |
+--------------------------------------------------+
```

- Session cards show: scenario name/summary, time since last played, turn count, characters involved (small avatars/names).
- Clicking a session card resumes play (`/play/:sessionId`).
- "+ New Session" opens a scenario picker or navigates to scenario creation.
- Quick links navigate to entity management pages.

### 14.3 Play View (replaces ChatView)

This is the most significant UI change. The current `ChatView` is a chat interface with alternating user/assistant messages. The new `PlayView` is a turn-based narrative experience.

**Layout:**

```
+----------------------------------------------------------+
| [< Back]  Scenario Name              [Settings] [State]  |
+----------------------------------------------------------+
|                                                           |
|  +-----------------------------------------------------+ |
|  |                    STORY FEED                        | |
|  |                                                      | |
|  |  > You pour yourself some coffee and sit down.       | |
|  |                                                      | |
|  |  Alex pours a cup of coffee from the pot and         | |
|  |  settles into a chair at the kitchen table. At the   | |
|  |  stove, Marta pulls eggs and butter from the fridge  | |
|  |  without a word...                                   | |
|  |                                                      | |
|  |  [dice icon] Ren: Persuasion check (14 vs DC 13)    | |
|  |  --- success                                         | |
|  |                                                      | |
|  +-----------------------------------------------------+ |
|                                                           |
|  +-----------------------------------------------------+ |
|  | What do you do?                                      | |
|  |                                                      | |
|  | [Say something to break  ] [Ask Ren what happened   ]| |
|  | [the tension → Marta     ] [last night → Ren        ]| |
|  |                                                      | |
|  | [Stay quiet and drink    ] [Head to your room       ]| |
|  | [coffee                  ] [→ Alex's bedroom        ]| |
|  |                                                      | |
|  | Or type your own action:                             | |
|  | [____________________________________________] [Go]  | |
|  +-----------------------------------------------------+ |
+----------------------------------------------------------+
```

**Story feed** (top scrollable area):
- Each turn is a visual block: user's input (brief, styled differently — e.g., right-aligned or muted) followed by the narration prose (the main content).
- Narration streams in real-time via SSE, using the existing `useEventStream` composable adapted for new event types.
- Optional: skill check results shown as compact inline badges between the user input and narration (e.g., `[dice] Ren: Persuasion 14 vs DC 13 — success`). These can be collapsed/hidden via a setting for users who prefer pure narrative immersion.
- Relocation and time skip narrations are visually distinct (e.g., a divider line, different background tint, or a location/time badge).

**Continuation options** (bottom area):
- 2-4 option cards displayed as clickable buttons/tiles after each narration completes.
- Each option shows: type icon (speech bubble for dialogue, boot for relocation, clock for time skip, hand for action), short description, and target (character name, location, or time).
- Below the options: a freeform text input for custom actions.
- Selecting an option or submitting freeform text triggers the next turn.
- While a turn is processing: options disappear, a loading/thinking indicator appears, narration streams in.

**State panel** (slide-out or toggle, triggered by [State] button):
- Current location and time.
- Characters present (names + small status: key drive levels as simple bars, active intent as one-line summary).
- Collapsed by default — the story feed is the primary experience. Power users or game-master-minded users can keep it open.

**Thinking indicators:**
- The current system shows thinking stages ("summarizing", "deliberating", "responding"). The new system has more stages. Show a progress indicator with stage labels: "Characters acting..." → "GM evaluating..." → "Rolling dice..." → "Narrating..." → "Processing..." → "Done."
- These map to pipeline steps 6.2 → 6.3 → 6.4 → 6.5 (streaming starts) → 6.6-6.9 → complete.

**Commands:**
- `/regenerate` → calls `POST /api/turn/regenerate`. Replaces the last turn's narration with a new one (new dice rolls, new narration). The story feed replaces the last narration block.
- `/rewind` → restores the previous turn's snapshot. Removes the last turn from the story feed.
- These can also be accessible via a context menu or buttons on the last narration block (e.g., a small "retry" icon).

**SSE event types (revised):**

| Event type | Payload | UI behavior |
|-----------|---------|-------------|
| `stage` | `{ stage: "acting" \| "evaluating" \| "rolling" \| "narrating" \| "processing" }` | Update thinking indicator |
| `dice` | `{ character, skill, roll, dc, result }` | Show dice result badge (optional) |
| `narration_chunk` | `{ content: string }` | Append to streaming narration |
| `narration_complete` | `{ full_narration: string }` | Finalize narration block |
| `options` | `{ options: ContinuationOption[] }` | Display continuation option cards |
| `world_state` | `{ location, time, characters_present }` | Update state panel |
| `error` | `{ message: string }` | Show error, offer retry |
| `turn_complete` | `{ turn_number: int }` | Mark turn complete, enable input |

### 14.4 Character Creation (adapted)

The current two-column layout (AI chat assistant on left, character sheet form on right) is effective and should be preserved. Changes are minimal.

**What stays:**
- Two-column layout with AI-assisted conversational creation.
- Streaming AI responses with incremental field updates.
- Auto-save to localStorage.
- Edit mode for existing characters.

**What changes:**
- Remove `key_locations` and `setting_description` fields from the form (moved to WorldLore/Scenario).
- Remove or rename `kinks` field depending on model decision.
- Add optional `starting_drives`, `starting_skills`, `starting_emotional_state` fields — but these are **not shown during initial character creation**. They are contextual: only relevant when a character is being added to a scenario with a specific ruleset. Two approaches:
  - **Deferred assignment**: character creation produces a character card without mechanical stats. Stats are assigned when the character is added to a scenario (the scenario creation flow presents the ruleset schema and lets the user set starting values). This is cleaner and avoids coupling character creation to a specific ruleset.
  - **Inline assignment**: if a ruleset is selected during character creation, show the drives/skills/emotions form. This is more streamlined for users who know what game they're building for.
  - **Recommendation**: deferred assignment. Character cards are reusable across rulesets. Starting stats are set per scenario-character pairing.

### 14.5 Ruleset Creation (new)

No current equivalent. This is a new view for authoring the mechanical layer.

**Layout — two-column, form-based (not AI-assisted initially):**

```
+----------------------------------------------------------+
|  Create Ruleset                              [Save] [Back]|
+----------------------------------------------------------+
|  LEFT COLUMN: Schema Builder    | RIGHT COLUMN: Rules Text|
|                                 |                         |
|  Name: [________________]      | ## Rules Text            |
|                                 | [Large textarea/editor] |
|  ## Drives                      | Write freeform rules    |
|  +---------------------------+  | about genre, tone, when |
|  | satiation  0-10  def:5   |  | checks apply, how DC   |
|  | [decay: 0.5] [baseline:5]|  | is set, etc.            |
|  +---------------------------+  |                         |
|  | energy     0-10  def:7   |  |                         |
|  | [decay: 0.5] [baseline:6]|  |                         |
|  +---------------------------+  |                         |
|  [+ Add Drive]                  |                         |
|                                 |                         |
|  ## Skills                      |                         |
|  +---------------------------+  |                         |
|  | persuasion    0-20        |  |                         |
|  +---------------------------+  |                         |
|  | stealth       0-20        |  |                         |
|  +---------------------------+  |                         |
|  [+ Add Skill]                  |                         |
|                                 |                         |
|  ## Emotional State (global)    |                         |
|  +---------------------------+  |                         |
|  | composure   0-10  def:5   |  |                         |
|  +---------------------------+  |                         |
|  [+ Add Dimension]              |                         |
|                                 |                         |
|  ## Emotional State (per-rel)   |                         |
|  +---------------------------+  |                         |
|  | trust       0-10  def:5   |  |                         |
|  | affection   0-10  def:3   |  |                         |
|  | resentment  0-10  def:0   |  |                         |
|  +---------------------------+  |                         |
|  [+ Add Dimension]              |                         |
|                                 |                         |
|  ## Config                      |                         |
|  Time per turn: [1 min]        |                         |
|  Importance threshold: [2]     |                         |
|  Max event stream: [100]       |                         |
+----------------------------------------------------------+
```

**Key UX decisions:**
- The schema builder (left) is a structured form: add/remove drives, skills, emotional dimensions. Each entry has name, range, default, and optionally decay_rate and offscreen_baseline.
- The rules text (right) is a large freeform text area. This is where genre conventions, tone, and mechanical guidance live. Markdown-capable.
- Provide 2-3 **preset rulesets** (e.g., "Slice of Life", "Fantasy Adventure", "Mystery Thriller") that users can load as a starting point and customize. Presets populate both the schema and rules text.
- Save validates that all required fields are present and schema entries are well-formed.

**Future enhancement**: AI-assisted ruleset creation (describe what kind of game you want, AI suggests drives/skills/rules text). Not needed for initial implementation — the preset + customize pattern is sufficient.

### 14.6 World Lore Creation (new)

Each world lore entry is a single article — a location, a faction, a historical event, a technology, a cultural norm, etc. Entries are created individually and organized with tags.

**Route**: `/world-lore/create`, `/world-lore/:id/edit`

**Layout — two-column, AI-assisted (same pattern as character creation):**

- **Left**: AI chat assistant. User describes what they want to document ("I need a seedy bar in the downtown area" or "describe the political faction that controls the northern district"). The AI helps flesh out the description, suggests relevant tags, and can generate related lore entries ("Should I also create an entry for the district itself?"). Streaming responses with incremental field updates.
- **Right**: Lore entry form.
  - Name (short title — "Duke's Bar", "The Silence Pact", "Riftstone Technology").
  - Tags: tag input with autocomplete from user's existing tags. Users type freely; matching existing tags appear as suggestions. Tags are freeform strings — no predefined taxonomy. The `location` tag has engine significance (marks navigable places).
  - Content: large freeform text area. Can be as long as needed — a paragraph for a minor detail, several paragraphs for a major location or faction.

Auto-save to localStorage during creation. Save to DB when done.

Lore entries are reusable across multiple scenarios. When creating a scenario, the user selects which lore entries apply.

**List view (`/world-lore`)**: shows all lore entries as cards. Each card shows name and tags as colored chips. **Filterable by tag** — clicking a tag chip in any card filters the list to entries with that tag. A tag filter bar at the top allows multi-tag filtering. This is critical for usability once the user has dozens of lore entries across multiple worlds.

### 14.7 Scenario Creation (revised)

Scenarios compose pre-existing entities: a ruleset, characters, a persona, and world lore. The scenario creation screen assumes these already exist and lets the user select them, then builds the scenario-specific content (intro, goals, hooks, atmosphere) with AI assistance.

**Route**: `/scenarios/create`

**Layout — two-column, AI-assisted:**

- **Left**: AI chat assistant. Once the user has selected the building blocks (top of right column), the AI knows the ruleset mechanics, character personalities, persona identity, and world locations. It helps craft the scenario intro, suggest plot hooks, set character goals, and define the starting situation. Streaming with incremental field updates.
- **Right**: Scenario form, divided into two zones:

**Top zone — Entity selection (form inputs, no AI):**
- Ruleset: dropdown of user's rulesets. Required.
- NPC Characters: multi-select from user's character library. At least one required.
- User Persona: dropdown of user's personas. Required.
- World Lore: multi-select from user's lore entries, filterable by tag. Optional. Shows selected entries as chips with their tags. The tag filter makes it easy to pull in all lore for a specific world (e.g., filter by "downtown" to grab all relevant entries at once).

Selecting these populates the AI assistant's context so it can give relevant suggestions. The user can change selections at any time and the AI adapts.

**Bottom zone — Scenario content (AI-assisted fields):**
- Summary (title/name).
- Intro message (the opening narration).
- Location (starting location — should reference a location from selected world lore if available).
- Time context (starting time).
- Atmosphere.
- Plot hooks (list).
- Stakes.
- Character goals: one text field per selected NPC character + one for the persona. Pre-labeled with character names.
- Potential directions (list).
- Starting state overrides: per-character drive/skill/emotional state values for this scenario. Pre-filled from character card defaults. Displayed as collapsible sections per character, showing the ruleset schema fields with editable values. Only needs attention if the user wants non-default starting conditions.

**Actions:**
- "Save to Library" — save scenario without starting.
- "Save & Play" — save scenario, create session, navigate to `/play/:sessionId`.

### 14.8 Character Detail Page (adapted)

**Current**: `CharacterPageView` shows character info, their sessions, and their saved scenarios.

**New**: Since scenarios are no longer 1:1 with characters, this page shifts focus.

**Layout:**
- Character info (name, tagline, backstory, personality, appearance — read-only display with edit button).
- **Sessions involving this character**: list of sessions where this character participates (as NPC or as user persona). Each session card shows scenario name, turn count, last played.
- **Scenarios involving this character**: list of scenarios that include this character. Click to view scenario details or start a new session from it.
- No "create scenario" button here — scenarios are created from `/scenarios/create` where you select characters. This page just shows what already references this character.

### 14.9 Entity List Pages

Each top-level entity type (characters, rulesets, world lore, scenarios) gets a list page following the same pattern as the current `CharacterSelectionView`: a grid of cards with a "+ Create New" card.

| Route | Cards show | Create navigates to |
|-------|-----------|-------------------|
| `/characters` | Name, tagline, is_persona badge | `/characters/create` |
| `/rulesets` | Name, drive/skill count, genre hint from rules_text | `/rulesets/create` |
| `/world-lore` | Name, tags as colored chips, content preview | `/world-lore/create` |
| `/scenarios` | Summary, ruleset name, character names, atmosphere | `/scenarios/create` |

Each card also supports: click to view detail, edit button, delete with confirmation.

### 14.10 Scenario Detail / New Session Flow

**Route**: `/scenarios/:id`

Shows the full scenario: intro message, selected ruleset, characters with their starting states, selected world lore entries (shown as a tagged list), plot hooks, goals, atmosphere.

**Actions:**
- "Start New Session" — creates a session from this scenario and navigates to `/play/:sessionId`.
- "Edit" — navigates to `/scenarios/:id/edit` (same creation view, pre-populated).
- "Delete" — with confirmation.

This replaces the current `ScenarioSelectionModal`. The flow to start playing is: browse scenarios → view detail → "Start New Session". Or from the home page: click a recent session to resume, or "+ New Session" to go to the scenario list.

### 14.11 Component Reuse Summary

| Current Component | Status | Notes |
|------------------|--------|-------|
| `ChatView.vue` | **Replaced** by `PlayView.vue` | Fundamentally different interaction model |
| `ChatInput.vue` | **Adapted** | Becomes the freeform input portion of the continuation options area |
| `ChatMessage.vue` | **Replaced** | Narration blocks replace chat messages. New `NarrationBlock.vue` and `UserInputBlock.vue` components |
| `CharacterCard.vue` | **Kept** | Used in character list, scenario creation character picker, entity list grids |
| `CharacterCreationView.vue` | **Adapted** | Minor field changes (see 14.4) |
| `CharacterPageView.vue` | **Adapted** | Becomes `CharacterDetailView`, scenario relationship changes (see 14.8) |
| `ScenarioCreationView.vue` | **Rewritten** | Same two-column AI-assisted pattern, but now with entity selection dropdowns at top (see 14.7) |
| `ScenarioSelectionModal.vue` | **Removed** | Replaced by `/scenarios` list page and `/scenarios/:id` detail page (see 14.9, 14.10) |
| `SessionList.vue` | **Adapted** | Sessions now show scenario name and multiple characters |
| `SummaryModal.vue` | **Replaced** | Summary system removed. Replace with a state inspector modal showing current world state + character states |
| `SettingsMenu.vue` | **Extended** | Dual model tier selection, display preferences (see 14.12) |
| `ConfirmModal.vue` | **Kept** | Generic, no changes needed |

### 14.12 Settings (revised)

The current `SettingsMenu` selects AI processor and backup processor. Changes:

- Add **model tier selection**: separate dropdowns for "Narrator & GM model" (large) and "Action & Processing model" (mini). Default to a sensible pairing (e.g., Claude Sonnet + Gemini Flash).
- Keep backup processor as a fallback for both tiers.
- Add **display preferences**: show/hide dice results in story feed, show/hide state panel by default, narration text size.
- User preferences (currently `user_learnings` in StorySummary) could be a free-text field here if implemented (see 13.6).

### 14.13 New Components

| Component | Purpose |
|-----------|---------|
| **Play view** | |
| `NarrationBlock.vue` | Displays one turn's narration prose with optional dice results and turn number |
| `UserInputBlock.vue` | Displays the user's action input for a turn (compact, muted styling) |
| `ContinuationOptions.vue` | Displays 2-4 option cards + freeform input area |
| `DiceResult.vue` | Compact inline badge showing skill check result |
| `WorldStatePanel.vue` | Slide-out panel showing location, time, characters present with state summaries |
| `CharacterStateCard.vue` | Compact card showing one character's drives, emotional state, and active intent |
| `TurnLoadingIndicator.vue` | Pipeline stage progress indicator ("Characters acting..." etc.) |
| **Entity creation** | |
| `RulesetSchemaBuilder.vue` | Form for adding/editing drives, skills, emotional dimensions in ruleset creation |
| `TagInput.vue` | Reusable tag input with autocomplete from existing tags — used in lore creation and lore filtering |
| `LoreSelector.vue` | Multi-select for lore entries with tag-based filtering — used in scenario creation |
| `CharacterStatAssignment.vue` | Form for assigning starting drive/skill/emotional state values to a character within a scenario |
| `EntitySelector.vue` | Reusable dropdown/multi-select for picking existing entities (rulesets, characters, personas, world lore) with "Create New" action |
| **Shared** | |
| `EntityListGrid.vue` | Reusable grid of cards for any entity type list page (characters, rulesets, world lore, scenarios) — standardizes the card grid + "Create New" pattern |
| `EntityDetailHeader.vue` | Reusable detail page header with name, metadata, edit/delete actions |

### 14.14 Streaming Architecture

The current `useEventStream` composable connects to SSE endpoints and handles chunk/session/thinking/command/complete events. This pattern is preserved and extended.

**Changes:**
- New event types (see 14.3 table): `stage`, `dice`, `narration_chunk`, `narration_complete`, `options`, `world_state`, `turn_complete`.
- The composable should expose reactive refs for: `currentStage`, `diceResults[]`, `streamingNarration`, `continuationOptions[]`, `worldState`, `turnComplete`.
- The `connect()` method's payload changes from `InteractRequest` to a new `TurnRequest` shape: `{ session_id, input_type: "action"|"relocation"|"time_skip", content: string, option_index?: number }`.
