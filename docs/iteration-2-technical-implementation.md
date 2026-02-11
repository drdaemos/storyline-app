# Iteration 2 Technical Implementation (High-Level)

## Key Decisions (Confirmed)
- Single-character is a special case of multi-character.
- Rulesets are system-provided and contain DM-style rulebook text.
- Ruleset execution is guided by LLM reasoning + tool calls (dice, time) based on the rulebook.
- Observations are stored per character with time-based + importance-based decay.
- Each scene is a complete snapshot per turn.
- Narrator is a distinct pipeline step, not a character.
- One turn is one atomic transaction with optimistic concurrency control.
- Model outputs are schema-validated; invalid outputs enter a repair/retry path.
- State changes are represented as typed engine operations, not free-form numeric deltas.
- User input, tool calls, and model outputs are always persisted for replay/debugging.
- "Small" and "large" model choices are configurable per session.
- Model choice uses one taxonomy key per tier (existing `processor_type` style), not separate provider/model fields.

## Scope Recap
This iteration replaces the current system with a unified multi-character simulation framework. All scenarios use the same framework and ruleset-driven execution. The system does not rely on raw conversation history. Instead, it uses scene state + per-character observations with decay.

## Core Entities
- Ruleset: mechanics + schemas + rulebook text.
- World Lore: canonical world facts and setting.
- Scenario: setup referencing ruleset + lore + characters + stakes.
- Character: base profile + ruleset-specific stat block.
- Session: runtime container for a scenario instance.
- Scene: full snapshot per turn: time, location, pressure, present characters, constraints.
- Observation: per-character memory item (importance + decay).
- Action: per-character action record for the turn.

## Execution Pipeline
1. Ruleset Resolution (LLM + tool)
2. Per-Character Reflection (LLM, small model from session)
3. Narrator Continuation (LLM, large model from session)
4. State Operation Validation + Apply (engine code)
5. State Snapshot Write (scene + observations + actions + events)
6. Decay Read Computation (time + importance)

Single-character scenarios are represented as sessions with one non-user character.

## Ruleset Format (System-Provided)
Rulesets are a combination of:
- DM-style rulebook text (primary logic)
- Character stat schema (JSON Schema)
- Scene state schema (JSON Schema)

Example ruleset record (conceptual):

```json
{
  "id": "seven-minutes",
  "name": "Seven Minutes to Heaven",
  "rulebook_text": "Time pressure is strict. The scene lasts 7 minutes. Any move to initiate, flirt, or cross a boundary requires a shyness check. Use 1d20 + (10 - shyness) + chemistry. 18+ is bold success, 12-17 is awkward partial, below 12 is failure with tension.",
  "character_stat_schema": {
    "type": "object",
    "required": ["shyness", "chemistry"],
    "properties": {
      "shyness": {"type": "integer", "min": 0, "max": 10},
      "chemistry": {"type": "integer", "min": 0, "max": 10}
    }
  },
  "scene_state_schema": {
    "type": "object",
    "required": ["minutes_left"],
    "properties": {
      "minutes_left": {"type": "integer", "min": 0, "max": 7}
    }
  }
}
```

## LLM Steps (Inputs + History Representation)

### A) Ruleset Resolution (small model; session-configured)
Inputs:
- rulebook_text
- scene_state
- user_action
- character_stat_blocks (only involved characters)
- recent_observations (last 3-5 per involved character)

Output:
- dice_request[] (expressions, modifiers)
- resolved_outcome
- new_observations[]
- state_ops[]

Tool call:
- dice tool invoked for each check.

### B) Per-Character Reflection (small model; session-configured)
Inputs (per character):
- character_profile
- stat_block
- decayed_observations[] (with priority scores)
- resolved_outcome
- scene_state

Output:
- action_text
- intent_tags (optional)

### C) Narrator Continuation (large model; session-configured)
Inputs:
- scene_state
- user_action
- resolved_outcome
- all_character_actions
- rulebook_summary
- scenario_tone
- recent_events (last narrator output or summary snippet)

Output:
- narration_text
- new_observations[] (per character, numeric importance)
- state_ops[]

### D) Decay Update (code)
Inputs:
- observations with timestamps + importance + reinforcement_count
- decay_policy

Output:
- computed decay_weight at read time

## Observation Priority & Decay
Observation fields:
- importance (int 1-5)
- created_at (timestamp)
- reinforcement_count (int, default 0)

Priority score:

```
priority = importance * exp(-lambda * age_in_minutes) * reinforcement_multiplier
```

Decay policy:

```
decay_weight = exp(-lambda * age_in_minutes)
reinforcement_multiplier = 1 + min(reinforcement_count, 3) * 0.15
```

Optional: lambda can be ruleset-specific.
Decay is computed on read and is not periodically written back to all rows.

## Turn Transaction Contract
- Each user turn is processed in one DB transaction.
- Session row is checked with optimistic concurrency:
  - Guard on `sessions.current_scene_id` (or `scene_index`) from turn start.
  - If guard fails, abort and retry from fresh state.
- Idempotency key: `session_id + user_action_id`.
  - Duplicate submissions return existing turn result.
  - No duplicate scene indices are created.
- Commit boundary includes:
  - action records
  - observation records
  - narrator output
  - applied state operations
  - next scene snapshot
  - session pointer update
  - event log entries

## Output Validation & Retry Policy
- Every LLM step has a strict JSON Schema output contract.
- On invalid output:
  1. Attempt one structured repair prompt with original output.
  2. Re-validate repaired JSON.
  3. If still invalid, execute one full step retry.
  4. If still invalid, fail the turn with a typed error and no partial writes.
- Validation includes:
  - required fields and enum values
  - character IDs exist in session
  - importance is in range 1-5
  - state operations are allowed by ruleset and scene schema

## Determinism & Replay
- Persist all dice calls with expression, raw rolls, modifier, total, and seed.
- Persist model metadata per step: provider, model name, prompt version, and timestamp.
- Persist the exact user action text used for execution.
- Replay mode can:
  - reuse recorded dice results for deterministic debugging, or
  - re-roll with recorded seed for deterministic simulation rerun.

## Failure Handling
- Retryable failures:
  - transient model/API errors
  - tool timeout/failure
  - optimistic concurrency conflict
- Non-retryable failures:
  - schema validation failure after repair/retry
  - ruleset/schema mismatch in stored data
- Retry policy:
  - Step retries are bounded and logged.
  - Turn retries restart from turn start state.
- User-facing behavior:
  - On terminal failure, no scene advance.
  - User receives a recoverable error response and can retry input.

## Model Tier Configuration (Per Session)
- Runtime uses two model tiers:
  - small model: ruleset resolution + per-character reflection
  - large model: narrator continuation
- Model tier selection is stored on session at creation time and may be updated between turns:
  - `small_model_key`
  - `large_model_key`
- Keys reuse existing provider taxonomy aliases (same style as `processor_type` in runtime factory), for example:
  - `claude-sonnet`
  - `gpt-5.2`
  - `google-pro`
  - `deepseek-v32`
- Turn execution must resolve model configuration from session, not global config.
- `turn_events` persists resolved model key for each model step, so replay shows the exact model selection used.

## Dice Tool (Local Function)
Inputs:
- expression: string (e.g. "2d12+3", "1d20", "3d6-1")
- seed: optional
- context: optional (character id, check type)

Output:
- total
- rolls[]
- modifier
- expression

The ruleset resolution step requests dice tool calls when needed.

## Scenario Generation (Iteration on Existing)
The scenario generator must become ruleset-aware and produce:
- ruleset_id
- world_lore_id
- character_ids (materialized from join table)
- scene_seed that validates scene_state_schema
- character_stat_blocks that validate character_stat_schema
- intro/narrator seed text

Generation pipeline (high-level):
1. Generate scenario outline (tone, stakes, cast, location)
2. Validate against ruleset schemas
3. Produce initial scene state and initial observations

## Storage Shape (High-Level)
- Normalized observation, action, relation, and event tables.
- Each scene is a full snapshot, referencing observation/action records.
- Session points to current scene.
- Character membership is normalized via join tables.

## Relation Tracking (Scene State)
Canonical relation storage is DB table `scene_relations`.
Scene JSON may include relation edges as a denormalized prompt assembly convenience.

Example:

```json
"relations": [
  {"a": "lena", "b": "user-persona", "trust": 4, "tension": 6, "closeness": 3}
]
```

Query logic treats (a, b) as an unordered pair. A DB-level `scene_relations` table can normalize the pair for fast lookup.

## Ruleset Concepts (Examples)

### Ruleset A: "Everyday Tension" (Slice-of-Life)
Design goals:
- Grounded, typical scenes with subtle stakes.
- Failures are plausible: awkwardness, missed timing, mild conflict, obligation drift.
- Chance exists without turning the scene into high drama.

Stats (each includes archetypes + consequences):

- Warmth
  - Represents: friendliness and emotional availability.
  - High archetype: easy to approach, inviting, generous.
  - Low archetype: distant, cool, hard to read.
  - Success: creates rapport.
  - Fail: comes off cold or overly familiar.

- Self-Awareness
  - Represents: awareness of own impact and behavior.
  - High: reflective, measured.
  - Low: oblivious, unintentionally blunt.
  - Success: avoids missteps.
  - Fail: slips into awkward or inconsiderate behavior.

- Boundaries
  - Represents: ability to set limits or respect others'.
  - High: clear, steady, respectful.
  - Low: oversteps or retreats.
  - Success: keeps interaction healthy.
  - Fail: crossed line or excessive withdrawal.

- Physicality / Fitness
  - Represents: baseline bodily comfort, stamina, and ease in physical space.
  - High: grounded, steady, physically confident.
  - Low: tense, fatigued, physically tentative.
  - Success: handles physical moments smoothly.
  - Fail: clumsy, tires quickly, or withdraws from physical proximity.

- Logic
  - Represents: ability to rationalize and reason about everyday situations.
  - High: clear-headed, orderly, realistic.
  - Low: scattered, vague, easily derailed.
  - Success: makes sensible calls or defuses confusion.
  - Fail: misjudges basics or overcomplicates simple situations.

Rulebook core:
- Roll only for moments of social risk, ambiguity, or tension shifts.
- Use `1d20 + relevant_stat`.
- 16+ clean success, 10–15 mixed, 9- failure.
- Mixed/failure ticks `pressure_clock` (0–6).
- At 6, the scene shifts (someone leaves, call interrupts, opportunity closes).

### Ruleset B: "Inner Chorus" (Disco-Inspired)
Design goals:
- Stats represent inner voices and impulses.
- High stats can override natural reactions and cause unexpected behavior.
- Failures are narrative, not pure loss.

Stats (each includes archetypes + consequences):

- Logic
  - Represents: rational analysis, pattern seeking.
  - High: detached, incisive.
  - Low: intuitive, messy thinker.
  - Success: sees a crucial pattern.
  - Fail: overthinks, misses emotional nuance.

- Empathy
  - Represents: emotional attunement to others.
  - High: deeply sensitive.
  - Low: blunt, insulated.
  - Success: reads hidden feelings.
  - Fail: absorbs too much, destabilized.

- Volition
  - Represents: inner discipline, self-control.
  - High: steady, principled.
  - Low: impulsive, drifting.
  - Success: resists unhealthy impulses.
  - Fail: gives in or withdraws.

- Imagination
  - Represents: symbolic thinking, creative leaps.
  - High: visionary, metaphor-driven.
  - Low: literal, concrete.
  - Success: finds a novel angle.
  - Fail: invents meaning where none exists.

- Composure
  - Represents: social self-control.
  - High: polished, restrained.
  - Low: raw, reactive.
  - Success: keeps face.
  - Fail: blurts or reveals too much.

- Physique
  - Represents: bodily confidence, physical presence.
  - High: bold, commanding.
  - Low: withdrawn, uncertain.
  - Success: dominates space.
  - Fail: recoils or retreats.

- Rhetoric
  - Represents: persuasive framing and verbal leverage.
  - High: sharp, compelling, wins arguments.
  - Low: bland, easily dismissed.
  - Success: reframes the moment in their favor.
  - Fail: talks past the point or escalates tension.

- Perception
  - Represents: noticing subtle details and changes.
  - High: alert, observant.
  - Low: misses obvious signals.
  - Success: spots the critical detail.
  - Fail: overlooks something that changes the outcome.

- Suggestion
  - Represents: subtle influence, charm, and social steering.
  - High: magnetic, persuasive without force.
  - Low: blunt, hard to follow.
  - Success: nudges others into agreement.
  - Fail: seems pushy or falls flat.

Rulebook core:
- In high stress or ambiguity, roll for the dominant aspect.
- `1d20 + aspect_stat`.
- 18+ aspect overrides reaction.
- 12–17 aspect influences.
- 11- natural reaction, unless another stat is clearly higher.
- Failures are narrative: wrong read, conflict, sudden shift in intention.

## Schema Drafts (Concrete)

### rulesets
Fields:
- id (string, primary key)
- name (string)
- rulebook_text (text)
- character_stat_schema (json)
- scene_state_schema (json)
- mechanics_guidance (json, optional)
- schema_version (int)
- created_at (timestamp)
- updated_at (timestamp)

Example JSON:

```json
{
  "id": "seven-minutes",
  "name": "Seven Minutes to Heaven",
  "rulebook_text": "...",
  "character_stat_schema": {"type": "object", "required": ["shyness", "chemistry"], "properties": {"shyness": {"type": "integer"}, "chemistry": {"type": "integer"}}},
  "scene_state_schema": {"type": "object", "required": ["minutes_left"], "properties": {"minutes_left": {"type": "integer"}}},
  "mechanics_guidance": {"uses_dice": true, "dice_formats": ["NdM+K"]},
  "schema_version": 1
}
```

### world_lore
Fields:
- id (string, primary key)
- name (string)
- lore_text (text)
- lore_json (json, optional structured facts)
- schema_version (int)
- created_at (timestamp)
- updated_at (timestamp)

Example JSON:

```json
{
  "id": "motel-verse",
  "name": "Motel Verse",
  "lore_text": "A roadside motel outside a small town where rumors have teeth.",
  "lore_json": {"locations": ["Room 12", "Parking lot"], "factions": []},
  "schema_version": 1
}
```

### characters
Fields:
- id (string, primary key)
- name (string)
- base_profile (json)
- ruleset_id (string)
- stat_block (json, validated against ruleset.character_stat_schema)
- schema_version (int)
- created_at (timestamp)
- updated_at (timestamp)

Example JSON:

```json
{
  "id": "lena",
  "name": "Lena",
  "ruleset_id": "seven-minutes",
  "base_profile": {"tagline": "Quiet, sharp, quick to blush", "personality": "..."},
  "stat_block": {"shyness": 7, "chemistry": 3},
  "schema_version": 1
}
```

### scenarios
Fields:
- id (string, primary key)
- title (string)
- summary (string)
- ruleset_id (string)
- world_lore_id (string)
- character_ids (json array, denormalized cache)
- scene_seed (json, validated against ruleset.scene_state_schema)
- stakes (string)
- goals (json)
- tone (string)
- intro_seed (text)
- schema_version (int)
- created_at (timestamp)
- updated_at (timestamp)

Example JSON:

```json
{
  "id": "seven-minutes-01",
  "title": "Seven Minutes",
  "summary": "A cramped storage closet, a ticking timer.",
  "ruleset_id": "seven-minutes",
  "world_lore_id": "motel-verse",
  "character_ids": ["lena", "user-persona"],
  "scene_seed": {"minutes_left": 7, "location": "storage closet", "pressure": "timer"},
  "stakes": "If this goes wrong, trust collapses.",
  "goals": {"lena": "survive the closeness", "user": "break the awkwardness"},
  "tone": "tense, awkward, intimate",
  "intro_seed": "The door clicks shut behind you. It's darker than you expected.",
  "schema_version": 1
}
```

### sessions
Fields:
- id (string, primary key)
- scenario_id (string)
- ruleset_id (string)
- world_lore_id (string)
- character_ids (json array, denormalized cache)
- current_scene_id (string)
- small_model_key (string)
- large_model_key (string)
- created_at (timestamp)
- updated_at (timestamp)

Example JSON:

```json
{
  "id": "session-uuid",
  "scenario_id": "seven-minutes-01",
  "ruleset_id": "seven-minutes",
  "world_lore_id": "motel-verse",
  "character_ids": ["lena", "user-persona"],
  "current_scene_id": "scene-0001",
  "small_model_key": "deepseek-v32",
  "large_model_key": "claude-sonnet"
}
```

### scenes
Fields:
- id (string, primary key)
- session_id (string)
- scene_index (int)
- state_json (json)
- created_at (timestamp)

Example JSON:

```json
{
  "id": "scene-0001",
  "session_id": "session-uuid",
  "scene_index": 1,
  "state_json": {"minutes_left": 6, "location": "storage closet", "present": ["lena", "user-persona"], "pressure": "timer", "relations": [{"a": "lena", "b": "user-persona", "trust": 4, "tension": 6, "closeness": 3}]}
}
```

### observations
Fields:
- id (string, primary key)
- session_id (string)
- scene_id (string)
- character_id (string)
- content (text)
- importance (int 1-5)
- reinforcement_count (int, default 0)
- created_at (timestamp)

Example JSON:

```json
{
  "id": "obs-001",
  "session_id": "session-uuid",
  "scene_id": "scene-0001",
  "character_id": "lena",
  "content": "User's voice softened after the timer started.",
  "importance": 3,
  "reinforcement_count": 1
}
```

### actions
Fields:
- id (string, primary key)
- session_id (string)
- scene_id (string)
- character_id (string)
- action_text (text)
- resolved_outcome (text or json)
- created_at (timestamp)

Example JSON:

```json
{
  "id": "act-001",
  "session_id": "session-uuid",
  "scene_id": "scene-0001",
  "character_id": "lena",
  "action_text": "She steadies her breathing and meets your eyes.",
  "resolved_outcome": "calm response"
}
```

### session_characters
Fields:
- session_id (string, foreign key)
- character_id (string, foreign key)
- role (string; e.g. npc, user_persona)
- created_at (timestamp)

Composite primary key:
- (session_id, character_id)

### scenario_characters
Fields:
- scenario_id (string, foreign key)
- character_id (string, foreign key)
- created_at (timestamp)

Composite primary key:
- (scenario_id, character_id)

### scene_relations
Fields:
- id (string, primary key)
- session_id (string)
- scene_id (string)
- character_a_id (string, normalized low sort key)
- character_b_id (string, normalized high sort key)
- trust (int)
- tension (int)
- closeness (int)
- created_at (timestamp)

Unique index:
- (scene_id, character_a_id, character_b_id)

### turn_events
Fields:
- id (string, primary key)
- session_id (string)
- scene_id (string, nullable for turn start events)
- turn_index (int)
- event_type (string; user_action, model_output, tool_call, state_apply, error)
- step_name (string; ruleset_resolution, reflection, narrator, engine_apply)
- payload_json (json)
- model_key (string, nullable)
- prompt_version (string, nullable)
- created_at (timestamp)

## State Machine (Execution Flow with Storage Writes)

### Turn Start
- Start transaction.
- Load session, scenario, ruleset, world lore.
- Resolve `small_*` and `large_*` model config from session.
- Load current scene snapshot and verify optimistic concurrency guard.
- Load per-character observations (compute decay on read).
- Persist `turn_events` entry for user action.

### Step 1: Ruleset Resolution
- LLM classifies action and decides if checks are required.
- Dice tool executes roll(s).
- Validate model output schema.
- Persist:
  - ruleset-resolution `turn_events` (model output + tool calls)
  - new observations from ruleset resolution
  - canonical action record for user action

### Step 2: Per-Character Reflection
- For each character:
  - LLM generates action.
  - Validate model output schema.
  - Persist action record.
  - Persist per-character reflection `turn_events`.

### Step 3: Narrator Continuation
- LLM produces narration + new observations + state_ops.
- Validate model output schema.
- Persist narrator output in a mandatory scene log/messages record.
- Persist new observations.
- Persist narrator `turn_events`.

### Step 4: State Apply (engine code)
- Merge and validate all `state_ops` from ruleset + narrator.
- Apply typed operations to current state in engine code.
- Validate resulting full state against `scene_state_schema`.
- Persist `turn_events` for state application.

### Step 5: Scene Snapshot
- Persist new scene with scene_index + state_json.
- Update session.current_scene_id.
- Commit transaction.

### Step 6: Decay Read Computation
- No background write required; decay is derived when reading observations.

## Prompt Templates (Concrete)

### Ruleset Resolution Prompt (small model)
System:
- You are a ruleset executor. Apply the rulebook strictly.
- If a check is needed, specify dice expression and modifier.

User:
- Rulebook:
  {rulebook_text}
- Scene state:
  {scene_state_json}
- User action:
  {user_action}
- Character stat blocks:
  {stat_blocks_json}
- Recent observations:
  {recent_observations_json}

Expected output (JSON):
```
{
  "dice_request": ["1d20+3"],
  "resolved_outcome": "partial success",
  "new_observations": [{"character_id": "lena", "content": "...", "importance": 3}],
  "state_ops": [
    {"op": "decrement", "path": "minutes_left", "value": 1}
  ]
}
```

### Character Reflection Prompt (small model)
System:
- You are a character reacting to facts. Use only observations and current outcome.
- Output a single action, concise.

User:
- Character profile:
  {character_profile_json}
- Stat block:
  {stat_block_json}
- Scene state:
  {scene_state_json}
- Resolved outcome:
  {resolved_outcome}
- Observations (decayed):
  {decayed_observations_json}

Expected output (JSON):
```
{
  "action_text": "She steadies her breathing and meets your eyes.",
  "intent_tags": ["calm", "connection"]
}
```

### Narrator Prompt (large model)
System:
- You are the narrator. Show what happened, introduce tension, keep the story moving.
- Do not roleplay as any character.

User:
- Scene state:
  {scene_state_json}
- User action:
  {user_action}
- Ruleset outcome:
  {resolved_outcome}
- Character actions:
  {actions_json}
- Rulebook summary:
  {rulebook_summary}
- Scenario tone:
  {scenario_tone}
- Recent events:
  {recent_events}

Expected output (JSON):
```
{
  "narration_text": "The timer ticks louder. Lena holds your gaze, then...",
  "new_observations": [
    {"character_id": "lena", "content": "The timer makes her heartbeat audible.", "importance": 4},
    {"character_id": "user-persona", "content": "Lena didn't step back.", "importance": 3}
  ],
  "state_ops": [
    {"op": "set", "path": "pressure", "value": "rising"}
  ]
}
```

## Migration Plan (Current System -> Iteration 2)
- Migration phases:
  1. Add new tables and nullable columns without changing runtime behavior.
  2. Backfill historical data into scenes/actions/observations/turn_events where possible.
  3. Enable dual-write from runtime to old and new storage paths.
  4. Validate parity on sampled sessions (scene progression and observations).
  5. Switch read path to new schema.
  6. Remove old-path writes after stabilization window.
- Rollback:
  - Keep old read/write path available during dual-write and initial cutover.
  - Cut back by toggling read path if parity checks fail.

## Testing Strategy (Required Invariants)
- Contract tests:
  - LLM output JSON Schema validation for all three model steps.
  - State operation validation rejects unknown ops/paths.
- Concurrency tests:
  - Simultaneous turns on same session produce one committed scene advance.
  - Idempotency key prevents duplicate scene creation on retries.
- Determinism tests:
  - Recorded dice seed/roll replay yields identical resolved outcomes.
- Data integrity tests:
  - `scene_index` is strictly monotonic per session.
  - `session.current_scene_id` always points to latest committed scene.
  - `scene_relations` has one normalized edge per unordered pair per scene.
- Migration tests:
  - Backfill scripts are idempotent.
  - Dual-write parity checks match for core fields.
