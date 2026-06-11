# Interactive NPC System — Technical Design Document

## 1. Overview

An LLM-driven interactive narrative system inspired by tabletop RPGs, adapted for slice-of-life scenarios. Characters are independent, self-driven agents that observe, reflect, plan, and act based on their own perception of the world. Conflicts and uncertain outcomes are resolved through skill checks against difficulty classes.

## 2. Entity Model

### Static Entities (authored content)

- **Ruleset**: defines the mechanical layer of a simulation. Contains two parts:
  - *Freeform rules text*: natural language explanation of genre conventions, tone, when skill checks apply, how difficulty is assessed, in-story limitations. Included in LLM prompts as context.
  - *State schemas*: strict structured definitions of drives, skills, and emotional state fields to track at runtime. The engine reads these schemas and enforces them — no game-specific logic is hardcoded. (See section 5 for schema details.)

- **Scenario**: genre, intro, stakes/goals. References a ruleset. Defines the starting conditions for a playable story, including which characters are involved, the initial location and time, and any scenario-specific setup.

- **Character Card**: who, backstory, personality, desires, interests. Also contains the character's starting values for all drives and skills defined by the ruleset schema. Multiple characters per scenario.

- **World Lore**: locations, notable places, cultural details, relevant history. Used by a scenario to ground the narrative in a specific setting.

### Dynamic Entities (runtime state)

- **Session**: a specific instance of a scenario and its ongoing development. Contains all runtime state.

- **World State**: current time, user's location, set of characters present with the user. Updated every turn. There are no discrete "scenes" — the world is continuous. When the user moves or time passes, the state updates accordingly.

- **Character State** (per character, per session):
  - *Drive values*: current levels for each drive defined by the ruleset schema (e.g., satiation, energy, social).
  - *Skill values*: set from character card at session start, potentially modified by events.
  - *Emotional state*: global mood + per-relationship sentiment. Updated during state update step.
  - *Active intent*: the character's current goal (see section 4). NPC-only.
  - *Event stream*: the character's memory — ordered list of observations and reflections (see section 3). NPC-only.

## 3. Observation & Memory System

### Event Stream

Each NPC maintains a single ordered event stream. Every event has:

- **type**: `observation` or `reflection`
- **tick**: when it was created (turn number)
- **subject**: which character(s) or entity this concerns
- **content**: natural language description
- **importance**: numeric, assigned at creation
- **decay_rate**: numeric, observations decay faster than reflections
- **source_refs**: list of event IDs this was derived from (empty for raw observations, populated for reflections)

### Observations

Observations are **shared events** — generated once per turn as a list of notable things that happened, then distributed by the engine to all characters who could perceive them.

Format: third-person factual. `"Marta slams the phone down."` `"Ren glances at the door and shifts uncomfortably."` Observations describe what happened, not what anyone thinks about it.

**Generation** (step 6.6): a single LLM call extracts notable events from the narration. Output is a flat list of `(subject, content, importance, visibility)`. The engine then copies each observation into the event stream of every character who can perceive it.

**Visibility**:
- `public` — perceived by all characters present. Default for most actions.
- `actor_only` — perceived only by the acting character. Used for successful stealth actions.
- Failed stealth actions are `public` (the attempt was noticed).

**Importance filtering**: observations with importance below a minimum threshold (configurable, e.g., ≥ 2) are **discarded and not stored**. Routine, mundane actions that don't affect anyone's goals or relationships should not enter the event stream at all. The prompt instructs the LLM to only extract events worth remembering, and the engine enforces a floor.

### Reflections

A reflection is a first-person thought that draws a NEW conclusion from observations — a judgment, prediction, suspicion, or realization not present in the observations themselves. Same stream, same structure, typed as `reflection`, with a lower decay rate.

Format: first-person, character-specific. Reflections must produce novel information beyond what the observations state. Observations are facts; reflections are what the character *infers* from those facts, colored by their personality, biases, and emotional state.

- Observation (fact): `"Ren apologizes to Marta for waking everyone up last night."`
- Good reflection (inference): `"He's only saying sorry because Alex is here watching."`
- Bad reflection (reiteration): `"Ren apologized to me. I wasn't expecting that."`

**Generation**: reflections are generated as part of the merged character update step (6.7). The LLM decides whether a reflection is warranted based on the observations it's already processing. No separate importance threshold trigger — the LLM judges directly whether recent events merit a new conclusion.

### Memory Assembly for Prompts

When building a character's prompt for action, memory is assembled by:

1. Pull all events with `remaining_decay > 0`
2. Score each event: `score = importance × remaining_decay × recency_bonus`
   - `recency_bonus`: multiplier based on tick distance (more recent = higher bonus)
3. Filter to events whose **subject** matches any character present or the current location
4. Rank by score, take top N that fits the context budget

No semantic relevance matching. Subject matching is deterministic, based on character/location tags.

### Decay

```
remaining_decay = initial_decay - (current_tick - creation_tick) × decay_rate
```

When `remaining_decay ≤ 0`, the event is removed from the stream.

Observations have a higher decay rate (fade fast). Reflections have a lower decay rate (persist longer).

## 4. Planning & Intent System

### Intent

Each character holds at most one active intent at a time. An intent represents a concrete, actionable goal derived from the character's personality, current drives, emotional state, and current context.

An intent has:

- **goal**: natural language description of what they want to achieve. Always specific and situational, not abstract. E.g., "find food", "ask Ren about his family", "get closer to Mika."
- **success_condition**: how to determine the goal is met. Can be structured (drive-based: `hunger < 3`) or fuzzy (narrative: "learn Ren's reason for avoiding me").
- **source_refs**: references to memory events or drives that motivated this intent.

### Intent Generation

When a character has no active intent (session start, after completion, after abandonment), a planning prompt generates one. Inputs:

- Character card (personality, traits, desires)
- Current drive/state values (from the ruleset schema)
- Current emotional state
- Assembled memory (top N events by score)
- Current context (location, characters present)

The LLM translates abstract desires and current needs into a single concrete intent appropriate to the moment.

### Action Generation

Each turn, the character produces one action toward their current intent. The action prompt receives:

- Current intent
- Assembled memory
- Context (location, characters present, what just happened)

The action is what the character does *right now*, adapted to circumstances. No multi-step plans are stored or sequenced.

### Intent Lifecycle

1. **Created**: generated when the character has no active intent.
2. **Held**: persists across turns. The character stays committed and does not replan every turn.
3. **Completed**: checked after each turn. Programmatic check if the success condition is structured; LLM call if fuzzy.
4. **Reevaluated**: triggered when a new reflection is generated that shares a subject tag with the current intent. A quick LLM evaluation determines whether the reflection changes what the character wants. If yes, the intent is dropped and a new one is generated.
5. **Abandoned**: if the intent becomes impossible given current circumstances, or if the character goes offscreen and the intent was tied to a specific situation.

### Design Rationale

- **Commitment from BDI**: characters don't replan every turn. They hold an intent until it's completed, reevaluated by reflection, or abandoned. This produces consistent, believable behavior.
- **No stored multi-step plans**: the intent gives direction, but the specific action is always generated in-the-moment. This avoids plans going stale as circumstances change.
- **Reflections as the only replan trigger**: raw observations alone don't cause replanning. A character must *process* new information through reflection before changing course. This mirrors how people don't instantly pivot — they sit with information before adjusting.

## 5. Ruleset & State

### Ruleset Structure

The ruleset defines the mechanical layer of a simulation. It has two parts:

#### Freeform Rules Text

Natural language explanation of:

- How the game/simulation works
- Genre conventions and tone
- What kinds of actions require skill checks vs. auto-succeed
- How difficulty class (DC) should be assessed
- Any in-story limitations or special conditions

This text is included in LLM prompts (GM prompt, narrator prompt) as context. It is authored content, not interpreted programmatically.

#### State Schemas

Strict, structured definitions of what gets tracked at runtime. These are data structures the engine manages and enforces. Defined per ruleset and filled in per character.

**Drive schema**: numeric values representing positive capacity / satiation. All drives follow a uniform model:

- **High value** = satisfied, resourceful, no pressure to act.
- **Low value** = depleted, creating motivation to replenish.
- **Zero** = neutral (absent/irrelevant) or fully depleted (depending on drive).
- **Decay always decreases** the value toward zero over time.
- Actions replenish drives (e.g., eating restores satiation, sleeping restores energy).

This means drives are always framed as positive capacity, not as needs. Track "satiation" not "hunger", "energy" not "fatigue", "social fulfillment" not "loneliness."

```
drives:
  - name: string        # e.g., "satiation", "energy", "social"
    type: number
    range: [0, max]
    default: number
    decay_rate: number   # always positive — subtracted each turn
    offscreen_baseline: number | null  # see below
```

Drive decay is applied programmatically by the engine: `value = max(0, value - decay_rate)`. No drive-specific logic needed — the engine treats all drives identically.

**Offscreen baseline**: when a character re-enters the user's location after being offscreen, drives with `offscreen_baseline` set are restored to `max(current_value, offscreen_baseline)`. This models the assumption that functioning characters maintain basic needs while offscreen — they eat, sleep, etc. without explicit simulation. Drives with `offscreen_baseline: null` are frozen at their last value and persist across offscreen gaps (appropriate for emotional states, grief, relationship tension, etc.). The offscreen summary step may override the baseline for specific drives if the character's circumstances warrant it (e.g., a character fleeing danger may not have eaten).

Low drive values feed into intent generation. The intent prompt sees which drives are low and the character is motivated to address them, without the engine needing to understand what each drive means.

**Skill schema**: numeric values representing character capabilities.

```
skills:
  - name: string        # e.g., "persuasion", "stealth", "cooking"
    type: number
    range: [min, max]
```

**Emotional state schema**: structured similarly to drives, but tracked per-relationship as well as globally. The ruleset defines which emotional dimensions to track.

```
emotional_state:
  global:                          # character's general mood
    - name: string                 # e.g., "composure", "confidence", "hope"
      type: number
      range: [0, max]
      default: number
      offscreen_baseline: null     # emotional states persist offscreen by default
  per_relationship:                # how this character feels about each other character
    - name: string                 # e.g., "trust", "affection", "resentment"
      type: number
      range: [0, max]
      default: number
```

Per-relationship entries are instantiated for each pair of characters known to each other. New relationships start at `default` values. Updated during step 6.7 (character processing) based on what happened during the turn — the LLM proposes diffs, the engine validates and applies them.

Global emotional state influences intent generation (a character low on composure may act impulsively). Per-relationship sentiment influences action generation (a character with high resentment toward someone may avoid or confront them). Both are included in character prompts.

**Three sources of state change**: the ruleset defines all dynamic stats, but they change through three different mechanisms:
- **Action-driven** (GM consequence resolution, step 6.3b): drive effects caused by actions given their outcomes (eating succeeds → satiation +3, running and failing → energy -1). The GM identifies these because they require interpreting the action and its outcome against the rules.
- **Cross-character reactive** (GM consequence resolution, step 6.3b): mechanical effects on OTHER characters caused by an action's outcome (failed public seduction → target's attraction drops, successful intimidation → target's composure -1). These are direct, mechanical consequences, not emotional reactions.
- **Emotional/social reactive** (character processing, step 6.7): changes that result from social or emotional events — trust shifts, mood changes, resentment building. The character processing LLM identifies these because they require interpreting events through the character's personality and perspective.

The engine doesn't distinguish between these at the storage level — all produce `{stat, change}` diffs validated against the same schema. The distinction is only about *which step* proposes them.

### Dynamic Character State

At runtime, each character has:

- **Drive values**: current levels for each drive defined in the schema.
- **Skill values**: set at character creation, potentially modified by events.
- **Emotional state**: global mood values + per-relationship sentiment values for each known character. Updated during state update step (6.7).
- **Active intent**: the character's current goal (see section 4). NPC-only — not tracked for the user persona.
- **Event stream**: the character's memory — ordered list of observations and reflections (see section 3). NPC-only — the user doesn't need simulated memory.

### User Persona

The user controls one character — their **persona**. The persona has a character card, drives, skills, and emotional state like any other character. From the engine and GM's perspective, the persona is treated identically to NPCs for rules evaluation, skill checks, narration, and state tracking.

The difference is in the turn flow. For the user persona, the following steps are **skipped**:

- **6.2 Character Action Generation**: the user provides their own action (via 6.1).
- **6.7 Character Processing** (LLM part): the user doesn't need emotional state updates or reflections generated by the system. Observation distribution still applies — observations reference the user's actions for NPC memory. Programmatic state updates (drives, decay) still apply.
- **6.8 Intent Lifecycle**: the user decides their own goals.

Everything else applies: the GM evaluates the user's action for skill checks, dice are rolled, narration covers the user's outcomes, drives are updated programmatically, and the user's state is persisted.

### State Mutation Rules

- The LLM never directly mutates state.
- The LLM (via GM or narrator prompts) proposes what should change.
- The engine receives structured state diffs and applies them: e.g., `{character: "Ren", drive: "hunger", change: +2}`.
- The engine validates all changes against the schema (clamps ranges, validates types).
- This ensures state is always consistent and never drifts from LLM hallucination.

### Skill Checks

When an action is uncertain or contested, it is resolved via a skill check:

- The GM prompt determines: (a) whether a check is needed, (b) which skill applies, (c) the difficulty class (DC).
- DC is set based on the action, the target, and the context, guided by the freeform rules text.
- Resolution is programmatic: `1d20 + skill_value vs DC`. This is not an LLM decision.
- Outcomes: success or failure, fed into the narrator prompt to incorporate into the story.

For contested actions (two characters in opposition), both roll and the higher result wins, or the attacker rolls against a DC derived from the defender's relevant skill.

## 6. Turn Flow

A turn is the fundamental unit of simulation. Each turn processes user input, resolves all character actions, narrates the outcome, and updates state.

### 6.0 Session Initialization

Before the first turn:

1. World state is initialized from the scenario definition (location, time, characters present).
2. Character states are initialized from character cards (drive values, skill values, starting emotional state).
3. Each character generates an initial intent (planning prompt, see section 4).
4. An intro message is generated and prefilled into the session.

### Prompt Directives (apply to all LLM calls)

- **No model reasoning/thinking**: all prompts must explicitly disable any built-in reasoning or chain-of-thought features (e.g., extended thinking, `thinking` blocks). These are inconsistent across models and not controllable.
- **Explicit reasoning fields**: where reasoning is needed, it is requested as a structured output field (`reasoning: string`) that the model fills in as part of its response. This is predictable, debuggable, and model-agnostic.
- **Structured output**: all LLM calls should request output in a specified format (JSON or similar). Freeform prose output is only used for narration.
- **No reiteration of inputs**: LLM outputs must not restate information already present in the prompt inputs. Reasoning fields should explain *why*, not repeat *what*. Reflections must produce novel inferences, not summarize observations. Action descriptions should state the new action, not re-describe the situation. Every output token should add information that wasn't already in the prompt.

Full prompt templates and output schemas for each step are in **prompt-templates.md**. A traced example of two complete turns is in **example-walkthrough.md**.

### 6.1 User Input

The user sends a continuation: either selecting from presented options or providing freeform input. This represents the user character's action for the turn.

### 6.2 Character Action Generation

**For each NPC present at the user's location**, independently and simultaneously:

**Model**: mini/cheap

**Prompt inputs**:
- Character card (personality, backstory, desires)
- Current character state (drives, emotional state, active intent)
- Assembled memory (top N events by score, filtered to present characters/location — see section 3)
- Current world state (location, time, characters present)
- What just happened (user's action + any environmental changes)

**Output** (structured):
- `reasoning`: why the character is taking this action — connects to their intent, relevant memories, and current emotional state. This is not shown to the user but is logged for debugging.
- `action`: one action/reaction in structured format: `(type: action|reaction|dialogue, target: character|none, description: string)`
- The action should advance the character's current intent where possible, but may be a reaction to immediate events if they demand it.

All character actions are generated independently — no character sees another NPC's action for this turn. This is simultaneous resolution.

### 6.3a GM Challenge Setup

**Model**: large/expensive

**Prompt inputs**:
- Freeform rules text from the ruleset
- All character actions from step 6.2 (including the user's action)
- Current world state
- Relevant character skill values
- Relevant relationship stats (for context on difficulty — e.g., target's attraction toward actor)

**Output** (structured):
- For each action:
  - `character`, `action_summary`, `reasoning`: why this action does or doesn't require a check, and why this DC. Logged for debugging and tuning.
  - `result_override`: `"auto_succeed"` | `"auto_fail"` | `null`. Auto-succeed is for mundane/trivial actions. Auto-fail is for actions that are physically impossible, violate world constraints, or have no reasonable chance of success (effective DC > 25).
  - `check_required`, `skill`, `dc`, `contested_with`: same as before, only when `result_override` is null.
  - `departure`: flag if this action implies leaving the current location. Evaluated regardless of outcome, but departure only proceeds if the action is not auto-failed.
- For contested actions (two characters acting against each other): both are flagged as contested, with the relevant skill for each side.

The GM does not determine outcomes — only whether checks are needed, their parameters, and whether actions are overridden. Drive effects are determined after dice resolution in step 6.3b.

### 6.3b GM Consequence Resolution

**Model**: large/expensive

Runs AFTER dice resolution (step 6.4).

**Prompt inputs**:
- All actions with their resolved outcomes (success/failure/auto_succeed/auto_fail, roll details)
- Freeform rules text from the ruleset
- Current world state
- Relevant character states

**Output** (structured):
- For each action:
  - `character`, `action_ref` (reference back to the action)
  - `drive_effects`: array of `{ "drive": string, "change": number }` — mechanical consequences of this action given its outcome. Can differ based on success vs failure. Examples: eating succeeds → satiation +3. Failed public seduction → reputation -1, confidence -1. Running and failing → energy -1 (you still exerted yourself). Auto-fail at something embarrassing in public → reputation -2.
  - `reactive_effects`: array of `{ "character": string, "drive": string, "change": number }` — effects on OTHER characters caused by this action's outcome. Example: a character witnesses a cringeworthy failed flirtation → their attraction toward the actor drops. One character's successful intimidation → target's composure -1. This is for cross-character consequences that are direct and mechanical, not emotional (emotional reactions are still handled in 6.7).
  - `reasoning`: why these consequences, given the outcome. One sentence.
- The GM sees ALL outcomes holistically, so it can reason about interactions: if character A tried to deflect character B's action and succeeded, the consequences for B account for the deflection.
- Most actions will have empty `drive_effects` and `reactive_effects`. The GM should not invent consequences for mundane actions.

### 6.4 Dice Resolution

**Programmatic — no LLM involved.**

For each action:
- When `result_override` is `"auto_succeed"`: record as success with result `"auto_succeed"`, no roll.
- When `result_override` is `"auto_fail"`: record as failure with result `"auto_fail"`, no roll.
- When `result_override` is `null` and `check_required` is true: roll `1d20 + character's skill value` vs DC. Record result as `"success"` or `"failure"`.
- For contested actions: both sides roll, higher total wins.

Output: a list of action outcomes `(character, action, result: "success"|"failure"|"auto_succeed"|"auto_fail", roll_details)`.

### 6.5 Narration

**Model**: large/expensive

This is a creative writing task. The narrator turns mechanical action outcomes into engaging prose — the story the user actually reads.

**Prompt inputs**:
- Freeform rules text (for tone and genre guidance)
- World lore (brief — for setting texture and sensory detail)
- All action outcomes from step 6.4 (successes, failures, auto_succeed, auto_fail, contest results)
- Consequences from step 6.3b (drive_effects, reactive_effects per action)
- Current world state (location, time, characters present)
- Recent story history (sliding window of last K narrator outputs — see Context Budget section)

**Output**:
- Story continuation prose incorporating all action outcomes. This should read like a passage from a fiction book: vivid, well-paced, with attention to sensory detail and character behavior.

The narrator has artistic liberty over *how* events are described — emphasis, pacing, sensory detail, atmosphere — but not over *what* happens. All outcomes must appear. No new events may be invented. Mechanical outcomes (success/failure/auto_succeed/auto_fail) are binding. World lore and character facts are binding.

Auto-failed actions must be narrated as genuine attempts that fail. Do not skip them or reduce them to a thought — the character tried and it did not work.

The narrator should spotlight the most significant actions and interactions. Mundane actions can be woven in as texture or omitted if there's more important content. The world around the characters — light, sound, weather, objects — should feel present, not just the characters' actions in a void.

This is the only step that outputs freeform prose. It should be streamable to the user.

### 6.6 Observation Extraction

**Model**: mini/cheap | **Per**: once per turn

Extracts notable events from the narration as shared observations. Does NOT generate per-character perspectives — the engine distributes observations to characters based on visibility.

**Prompt inputs**:
- Narrator output from step 6.5
- Action outcomes from step 6.4 (including stealth results)
- List of characters present

**Output** (structured):
- A flat list of observations: `(subject, content, importance, visibility)`.
- `content` is third-person factual: what happened, not what anyone thinks about it.
- `visibility`: `public` (default) or `actor_only` (successful stealth).
- `importance`: 1-5. Only events worth remembering — routine actions (walking, sitting, generic greetings) should be omitted entirely.

**Programmatic post-processing**:
- Discard any observation with `importance` below the minimum threshold (configurable, default ≥ 2).
- Distribute remaining observations: `public` observations are copied into every NPC's event stream. `actor_only` observations go only to the acting character's stream.

### 6.7 State Update, Character Processing & Observation Distribution

**Programmatic state updates** (run first, before LLM calls):
- Drive effects from consequence resolution: applied from the GM's `drive_effects` output (step 6.3b). These are outcome-aware — the GM determined them after seeing dice results. Validated against schema.
- Reactive effects from consequence resolution: applied from the GM's `reactive_effects` output (step 6.3b). These affect target characters specified in each reactive effect. Validated against schema.
- Drive decay applied: `value = max(0, value - decay_rate)` for each drive, each turn.
- Time advances (e.g., +1 minute per turn, configurable in ruleset).
- Observations from step 6.6 distributed to NPC event streams (see above).
- Characters present list updated: any NPC whose action was flagged as `departure: true` by the GM (step 6.3a) and succeeded or auto-succeeded (step 6.4) is removed. On departure: their state is frozen, `intended_destination` is noted from their action description, and they become offscreen.
- **Empty location check**: if no NPCs remain present after departures, the turn ends early after continuation options (step 6.9) — the user is prompted with options that include relocation or time skip.

**LLM-assisted character update** (per NPC, parallel):

**Model**: mini/cheap

A single call per NPC that combines reactive state updates and optional reflection. The LLM receives this turn's observations for this character and decides:
1. What stat changes are warranted as a consequence of events (e.g., trust shifts, mood changes). These are *emotional/social reactive* changes — not action-driven ones like "eating restores satiation" or cross-character mechanical effects (those are handled by the GM's consequence resolution in step 6.3b).
2. Whether the observations merit a reflection — a first-person conclusion or realization (if any).

**Prompt inputs**:
- Character card (brief — personality, key traits)
- Current character stats (all ruleset-defined reactive stats — global and per-relationship)
- Reactive stats schema (what stats exist and their ranges)
- This turn's observations for this character
- Recent unreflected observations (from prior turns, if any)
- Current active intent

**Output** (structured):
- `state_diffs`: proposed changes to any ruleset-defined reactive stat (global or per-relationship). Empty if nothing warrants a change.
- `reflection`: a first-person thought synthesizing recent observations into a conclusion. Null if nothing warrants one. Only generate a reflection if the character would genuinely stop and think about what just happened — not for routine events. Reflections must produce novel inferences, not restate observations.

### 6.8 Intent Lifecycle Check

**For each character**, after observations and reflections are processed:

1. **If a reflection was generated this turn** and it shares a subject tag with the current intent → run intent reevaluation (mini model). Output includes `reasoning` field explaining why the intent is kept or changed.
2. **If no active intent** (completed, abandoned, or just reevaluated away) → run intent generation (mini model, see section 4).
3. **Check completion**: if the current intent has a structured success condition, check it programmatically. If fuzzy, run a quick LLM check. If complete, clear the intent (a new one will be generated next turn or in the next step if needed).

### 6.9 User Continuation Options

**Model**: mini/cheap

**Prompt inputs**:
- Current world state (location, time, characters present)
- What just happened (narrator output)
- User character's state and intent

**Output**:
- 2-4 suggested continuation options for the user. Options may include:
  - **In-location actions**: dialogue, interactions, activities at the current location.
  - **Relocation**: "Go to [location]" — moves the user to a new location (see section 7, User Relocation).
  - **Time skip**: "Wait until [time]" or "Skip ahead to [event]" — advances the clock (see section 7, Time Skips).
- The user may also provide freeform input instead. Freeform input that clearly indicates relocation or time skip is handled the same way as the structured options.

### 6.10 Loop

Return to step 6.1.

### Model Usage Summary

| Step | Model | Reason |
|------|-------|--------|
| 6.2 Character Actions | mini × N | Per NPC, structured output, has `reasoning` field |
| 6.3a GM Challenge Setup | large × 1 | Complex reasoning about rules, context, difficulty, has `reasoning` field |
| 6.4 Dice Resolution | programmatic | Deterministic, verifiable |
| 6.3b GM Consequence Resolution | large × 1 | Outcome-aware consequence reasoning, requires understanding rules and context |
| 6.5 Narration | large × 1 | Creative writing — vivid prose from mechanical outcomes, streamable |
| 6.6 Observation Extraction | mini × 1 | Shared extraction from narration, not per-character |
| 6.7 Character Processing | mini × N | Per NPC: reactive state diffs + optional reflection in one call |
| 6.8 Intent Lifecycle | mini (conditional) | Only runs when reflection generated or intent needs check |
| 6.9 Continuation Options | mini × 1 | Suggestion generation, includes relocation/time-skip options |

**Unconditional per turn**: 2N + 5 LLM calls (N for 6.2, 1 for 6.3a, 1 for 6.3b, 1 for 6.5, 1 for 6.6, N for 6.7, 1 for 6.9). The merge absorbs the old conditional reflection calls into the unconditional 6.7 calls — same base count, but no additional conditional calls on top.

### Design Principles (informed by Dwarf Fortress)

- **Cascade potential**: the observation → reflection → intent → action → observation loop is the system's engine for emergent stories. One character's action creates observations for others, which may trigger reflections, which may change intents, which produce new actions. Do not dampen this loop.
- **Let simple interactions compound**: complex stories emerge from many simple rules interacting, not from any single step being clever. Each step should do one thing well.
- **Personality must be observable**: unlike DF where personality traits often don't surface visibly in behavior, our LLM-based action generation should make personality directly shape how characters act and speak. The character card should be strongly present in every action prompt.
- **Internal contradiction creates narrative**: characters whose desires conflict with their circumstances or with each other are the source of interesting stories. The system should not resolve tension prematurely.

### Prompt & Step Design Criteria

**Step merge criteria** — two LLM steps may be merged into a single call only if ALL of these hold:

1. Output must be non-streaming (structured JSON). Cannot merge with the narration step.
2. Must not bleed private data between characters. One character's card, secret backstory, or internal state must not be visible to another character's prompt. Per-NPC calls stay isolated.
3. Must be consequential — the steps run one after another with no branching between them.
4. Must not require programmatic logic between them — e.g., cannot merge action generation and narration because dice resolution runs in between.

**Voice conventions**:

- **Observations**: third-person factual. Shared across characters. `"Marta slams the phone down."` Observations are what happened, not what anyone thinks about it.
- **Reflections**: first-person, character-specific. `"I think Marta is hiding something from me."` Colored by personality, biases, and emotional state.
- **Character reasoning fields** (`reasoning` in action generation, intent reevaluation, etc.): first-person. This is the character's internal thought process.
- **GM reasoning**: third-person analytical. The GM is a referee, not a character.
- **Narration**: third-person prose. Describes observable events only — no internal thoughts.

**Mundane output filtering**:

- Observations below a configurable importance threshold are discarded before storage. The LLM is instructed to omit routine events entirely, and the engine enforces a floor.
- Reflections are optional — the LLM only generates one when recent events genuinely warrant a conclusion or realization. Mundane turns should produce no reflection.
- Emotional diffs are optional — most turns produce zero or one change. The LLM is instructed to return empty arrays when nothing emotionally relevant occurred.

**Anti-reiteration**:

Every output token should add information not already present in the prompt. This applies to all LLM calls:

- **Reasoning fields** explain *why*, not *what*. Don't restate the character's intent, the action being evaluated, or the observation being reflected on — these are already in the prompt inputs.
- **Reflections** must produce novel inferences (judgments, predictions, suspicions, decisions), not summaries of what was observed. The observations are facts; a reflection is what the character *concludes* from those facts.
- **Actions** describe what the character does, not the situation they're in or why they're here.
- **Observations** describe what happened, not what everyone already knows about the characters.

This is enforced through prompt instructions and can be validated heuristically (e.g., flagging outputs with high lexical overlap with their inputs).

### Context Budget & Narration History

Every LLM call has a finite context window. The system needs to allocate this budget across competing inputs. The exact token counts depend on the model used, but the priority order and strategy are fixed.

**Priority order for prompt assembly** (highest priority fills first):

1. **System instructions**: step-specific instructions, output format requirements. Fixed size per step, authored once.
2. **Rules text**: freeform rules from the ruleset. Fixed per session. If a ruleset's rules text is too long, that's an authoring problem, not a runtime one.
3. **Character card**: personality, backstory, desires. Fixed per character. Included in steps that need character voice (6.2, 6.7, 6.8).
4. **Current state**: drives, skills, emotional state, active intent. Small, structured.
5. **World context**: location, time, characters present, current actions. Varies per turn but bounded.
6. **Narration history**: recent narrator outputs for prose continuity. Variable — this is what gets squeezed.
7. **Assembled memory**: event stream entries scored and ranked. Variable — fills remaining budget.

Items 1-5 are essentially fixed cost per call. Items 6-7 are elastic and compete for the remaining space.

**Narration history**:

The narrator (step 6.5) receives recent narration outputs to maintain prose style, tone, and continuity. This is a sliding window:

- **Keep last K narrator outputs**, where K is tuned to balance continuity vs. budget. A reasonable starting point: K = 3-5 turns.
- Narration outputs are stored as part of session state (see section 8).
- If budget is tight, narration history is truncated from the oldest end first.
- When the user relocates, the relocation narration naturally shifts the prose context. No explicit reset needed — the sliding window will age out old-location narration within a few turns.

**Assembled memory budget**:

After fixed-cost items and narration history are placed, the remaining context is filled with memory events. The memory assembly process (section 3) already ranks events by score — it simply takes as many as fit.

This means in practice: early in a session with short history, characters have rich memory context. As narration history grows, memory budget shrinks slightly. The decay system naturally keeps memory streams bounded over longer timescales.

## 7. World Traversal & Time

There are no discrete "scenes." The world is continuous — the user is always at a location, time always advances, and characters come and go. What was previously called "scene transitions" are just changes to the world state: the user moves, time passes, NPCs arrive or depart.

### User Relocation

When the user selects a relocation option (from step 6.10) or provides freeform input that indicates movement to a new location:

1. **Narration**: the narrator describes the journey/transition briefly.
2. **World state updated**: location changes, time advances by travel duration (defined by ruleset or estimated).
3. **Departing NPCs go offscreen**: any NPCs at the old location who don't follow the user are frozen (see NPC Offscreen below).
4. **Arriving NPCs processed**: any NPCs at the new location go through NPC Entry processing (see below).
5. **New surroundings described**: a brief narration of what the user sees at the new location.
6. Turn flow resumes at step 6.10 (continuation options for the new location).

This is not a mid-turn interruption — it replaces the normal turn. The user's "action" for this turn was relocation.

### Time Skips

When the user selects a time skip option or provides freeform input indicating a time skip (e.g., "wait until evening", "skip to the meeting"):

1. **Time advances** by the specified or inferred duration.
2. **Drive decay applied** for all present characters for the elapsed time.
3. **Drive homeostasis applied** for the user persona and all present NPCs (for survival drives with `offscreen_baseline`).
4. **Offscreen summary** (mini model): brief account of what happened during the skip — for the user and any NPCs present. Mundane passage of time, no dramatic events. No skill checks.
5. **Narration**: the narrator describes the time passage and new situation.
6. **NPC re-evaluation**: NPCs present may have their intents re-evaluated given the new time context — an NPC who was chatting at lunch might leave in the evening.
7. Turn flow resumes at step 6.10.

### NPC Offscreen

NPCs not at the user's current location are **not simulated**:

- No actions, observations, reflections, or skill checks.
- Event stream and character state frozen at point of departure.
- Drive decay is **not applied** while offscreen.
- They have **no knowledge** of events at the user's location while away. Consistent with the information asymmetry model.

### NPC Entry

When an NPC arrives at the user's location (either because the user relocated to where they are, or because the NPC's intent brought them here):

1. **Drive homeostasis applied** (programmatic): all drives with `offscreen_baseline` are set to `max(current_value, offscreen_baseline)`.
2. **Offscreen summary + arrival context** (mini model): based on the character card, their last known intent, elapsed time, and current situation, generate:
   - A brief plausible account of what they did offscreen (1-3 observations added to their event stream).
   - What they notice on arrival (1-2 observations about who's present and what's happening).
   - Optional state diff overrides for unusual circumstances (e.g., character was fleeing — may not have eaten). Validated against schema. No skill checks.
   - **Constraint**: the offscreen observations **cannot involve any other tracked characters**. Only solo activities or interactions with unnamed background NPCs.
3. **Intent regenerated**: current intent cleared, new one generated from new context + existing memory + current state.
4. From the next turn, they participate normally (step 6.2).

### NPC Departure

When an NPC's action is flagged as `departure: true` by the GM (step 6.3a) and succeeds or auto-succeeds (step 6.4):

- Their departure is narrated (step 6.5).
- During state update (step 6.7): `intended_destination` recorded from their action description, state frozen, removed from characters present.

## 8. Persistence & Fault Tolerance

### Session State Serialization

The full session state must be serializable at any turn boundary (between step 6.10 looping back to 6.1). This allows:

- Saving and resuming across player sessions
- Regenerating a turn from the same starting state (for debugging or if the user wants a re-roll)
- Replaying from any checkpoint

**Persisted state** (the complete snapshot at a turn boundary):

- **World state**: current location, time, characters present
- **Per-character state** (for all characters, including offscreen):
  - Drive values
  - Skill values
  - Emotional state (global + per-relationship)
  - Active intent (goal, success_condition, source_refs)
  - Event stream (all observations and reflections, with tick, importance, decay_rate, source_refs)
- **Location history**: ordered log of location changes (location, time entered, time left, characters encountered)
- **Narration history**: last K narrator outputs (sliding window for prose continuity — see Context Budget section)
- **Turn counter**: global tick for decay calculations

**Not persisted** (regenerated on load or derived):

- Assembled memory (computed from event stream at prompt time)
- Continuation options (regenerated each turn)

### Turn Regeneration

Because all LLM calls within a turn are derived from the snapshot at the turn boundary, any turn can be regenerated by:

1. Restoring the snapshot
2. Re-running steps 6.1 through 6.10

This means the system should save the snapshot *before* processing each turn, not after. The post-turn state is the *next* turn's snapshot.

Note: LLM outputs are non-deterministic, so regeneration produces a different turn, not an identical replay. This is a feature — the user can "retry" a turn if the outcome was unsatisfying.

### Fault Tolerance

Each step in the turn flow can fail (LLM timeout, malformed output, validation error). The system should handle failures gracefully without corrupting state.

**General principles:**

- **State is only committed at turn boundaries.** Mid-turn state is tentative. If a turn fails partway through, the system rolls back to the last snapshot.
- **LLM outputs are validated before use.** Structured output that doesn't match the expected schema is rejected.
- **Retries with backoff.** LLM calls that fail (timeout, rate limit, malformed output) are retried up to N times before the turn is aborted.

**Per-step fault tolerance:**

| Step | Failure mode | Recovery |
|------|-------------|----------|
| 6.1 User Input | User disconnects | Session paused, resume from snapshot |
| 6.2 Character Actions | LLM fails for one NPC | Retry. If still failing, the character takes a default no-op action ("hesitates", "stays quiet"). Turn continues. |
| 6.3a GM Challenge Setup | LLM fails | Retry. If still failing, all actions get `result_override: "auto_succeed"` (no checks). Degrades quality but doesn't block. |
| 6.3b GM Consequence Resolution | LLM fails | Retry. If still failing, apply no drive_effects or reactive_effects this turn. Narration proceeds without consequence data. State updates skip consequence application. Degrades quality but doesn't block. |
| 6.4 Dice Resolution | N/A (programmatic) | Cannot fail meaningfully. |
| 6.5 Narration | LLM fails | Retry. If still failing, generate a minimal factual summary from action outcomes (programmatic fallback). User sees degraded prose but turn completes. |
| 6.6 Observation Extraction | LLM fails | Retry. If still failing, generate one generic observation per action from outcomes. Low quality but stream not broken. |
| 6.7 Character Processing | LLM fails for one NPC | Retry. If still failing, skip emotional updates and reflection for that character this turn. Drives still update programmatically. |
| 6.7 Character Processing | Validation error (bad diff) | Reject the invalid diff, log it. Apply only valid diffs. Discard malformed reflection. |
| 6.8 Intent Lifecycle | LLM fails | Keep current intent unchanged. Re-attempt next turn. |
| 6.9 Continuation Options | LLM fails | Present generic options ("continue", "look around", "go to [location]") or allow freeform only. |

**Abort threshold**: if more than 2 critical steps fail in a single turn (6.3 + 6.5, for example), abort the turn entirely, roll back to the snapshot, and inform the user that the turn couldn't be processed. The user can retry.

### Memory Pruning

Over long sessions, event streams grow. Pruning is handled by the decay system — events with `remaining_decay ≤ 0` are removed from the stream. This is sufficient for medium-length sessions.

For very long sessions (50+ turns), additional pruning may be needed:

- **Hard cap per stream**: if an event stream exceeds a max length, remove the lowest-scored events (by `importance × remaining_decay`) until within budget.
- **Reflection compression**: when pruning, prefer to keep reflections over observations, since reflections are summaries that already compress earlier events.
- **Archive** (optional): pruned events could be moved to cold storage rather than deleted, available for retrieval if the character revisits a topic. TBD whether this is worth the complexity.

## 9. Example Walkthrough

Two complete turns showing every output and how data flows between steps. Demonstrates shared observations, the merged character processing call, reflection triggering intent reevaluation, and mundane event filtering.

### Setup

Scenario: slice-of-life. Shared apartment kitchen, morning.

User persona: Alex (the player). NPCs: Marta (roommate), Ren (roommate).

State at turn start:

```
World: { location: "apartment kitchen", time: "8:15 AM" }
Present: [Alex (user), Marta, Ren]

Marta:
  drives: { satiation: 3/10, energy: 6/10 }
  emotional_state:
    global: { composure: 7/10 }
    relationships: { Alex: { trust: 6 }, Ren: { trust: 4, resentment: 5 } }
  intent: { goal: "make breakfast", success_condition: { type: "drive_threshold",
            drive: "satiation", operator: ">=", threshold: 7 } }
  memory: [obs-41] "Ren came home at 3 AM last night."

Ren:
  drives: { satiation: 4/10, energy: 3/10 }
  emotional_state:
    global: { composure: 5/10, confidence: 4/10 }
    relationships: { Marta: { trust: 5, affection: 6 }, Alex: { trust: 7 } }
  intent: { goal: "apologize to Marta for waking everyone up",
            success_condition: { type: "narrative",
            description: "Marta acknowledges the apology" } }
  memory: [obs-40] "Marta gave me a cold look when I walked in."
```

### Turn 1

**6.1** — Alex types: "I pour myself some coffee and sit down at the table"

**6.2 Marta** →
```json
{ "reasoning": "I'm hungry and making breakfast. Ren is here but I'm still
   annoyed about last night. I'll focus on cooking.",
  "action": { "type": "action", "target": null,
    "description": "Opens the fridge and starts pulling out eggs and butter,
     keeping her back to the table." } }
```
**6.2 Ren** →
```json
{ "reasoning": "My intent is to apologize to Marta. She's right there. I should
   say something now before it gets more awkward.",
  "action": { "type": "dialogue", "target": "Marta",
    "description": "Hey, Marta — I'm sorry about last night. I didn't mean to
     wake everyone up." } }
```

**6.3a GM Challenge Setup** →
```json
{ "evaluations": [
    { "character": "Alex", "action_summary": "Pour coffee and sit",
      "reasoning": "Mundane.",
      "result_override": "auto_succeed", "check_required": false,
      "skill": null, "dc": null, "departure": false },
    { "character": "Marta", "action_summary": "Cook eggs",
      "reasoning": "Routine kitchen activity.",
      "result_override": "auto_succeed", "check_required": false,
      "skill": null, "dc": null, "departure": false },
    { "character": "Ren", "action_summary": "Apologize to Marta",
      "reasoning": "Sincere apology to someone annoyed. Persuasion check,
       moderate DC given her resentment.",
      "result_override": null, "check_required": true,
      "skill": "persuasion", "dc": 13, "departure": false }
] }
```

**6.4 Dice** — Alex: auto_succeed. Marta: auto_succeed. Ren: 1d20+2 = 14 vs DC 13 → **success**.

**6.3b GM Consequence Resolution** →
```json
{ "consequences": [
    { "character": "Alex", "action_ref": "Pour coffee and sit",
      "drive_effects": [], "reactive_effects": [],
      "reasoning": "Mundane action, no consequences." },
    { "character": "Marta", "action_ref": "Cook eggs",
      "drive_effects": [{ "drive": "satiation", "change": 2 }],
      "reactive_effects": [],
      "reasoning": "Cooking produces food — satiation increases." },
    { "character": "Ren", "action_ref": "Apologize to Marta",
      "drive_effects": [], "reactive_effects": [],
      "reasoning": "Successful apology has no mechanical drive effect. Emotional impact handled in character processing." }
] }
```

**6.5 Narration** (streamed) →

> Alex pours a cup of coffee from the pot and settles into a chair at the kitchen table. At the stove, Marta pulls eggs and butter from the fridge without a word, cracking two eggs into a pan with practiced efficiency. Ren lingers near the doorway for a moment, then clears his throat. "Hey, Marta — I'm sorry about last night. I didn't mean to wake everyone up." His voice is careful, genuine. Marta's hand pauses over the pan for a beat before she continues cooking.

**6.6 Observation Extraction** →
```json
{ "observations": [
    { "subject": "Marta",
      "content": "Marta starts cooking eggs without greeting anyone,
       keeping her back to the table.",
      "importance": 2, "visibility": "public" },
    { "subject": "Ren",
      "content": "Ren apologizes to Marta for waking everyone up last night,
       sounding sincere.",
      "importance": 4, "visibility": "public" },
    { "subject": "Marta",
      "content": "Marta pauses briefly at Ren's apology but doesn't respond,
       continuing to cook.",
      "importance": 3, "visibility": "public" }
] }
```

Alex pouring coffee: omitted — routine, below importance threshold. Three shared observations, all `public`, assigned IDs obs-50, obs-51, obs-52 and distributed to both Marta's and Ren's event streams.

**6.7 Programmatic** — Marta satiation 3→5 (+2 from 6.3b drive_effects), then decay (all drives -0.5): Marta satiation 4.5, energy 5.5. Ren satiation 3.5, energy 2.5. Time → 8:16 AM.

**6.7 Marta processing** → (receives obs-50, obs-51, obs-52 + prior unreflected obs-41)
```json
{ "emotional_diffs": {
    "global": [],
    "relationship": [
      { "target": "Ren", "name": "resentment", "change": -1,
        "reasoning": "He actually apologized. That took some effort." }
    ] },
  "reflection": {
    "subject": ["Ren"],
    "content": "I wasn't expecting him to apologize. Maybe he does feel bad
     about it. I'm still annoyed, but at least he said something.",
    "importance": 3,
    "source_observation_ids": ["obs-41", "obs-51", "obs-52"] } }
```

**6.7 Ren processing** → (receives obs-50, obs-51, obs-52 + prior unreflected obs-40)
```json
{ "emotional_diffs": {
    "global": [
      { "name": "composure", "change": -1,
        "reasoning": "She didn't respond to the apology. Tense silence." }
    ],
    "relationship": [] },
  "reflection": {
    "subject": ["Marta"],
    "content": "She heard me but didn't say anything. I can't tell if she's
     thinking about it or just ignoring me. This isn't over.",
    "importance": 3,
    "source_observation_ids": ["obs-51", "obs-52"] } }
```

Applied: Marta resentment→Ren 5→4, Ren composure 5→4. Reflections stored as ref-10, ref-11.

**6.8 Intent lifecycle** —
- Marta: ref-10 subject "Ren" ≠ intent subject "breakfast." No reevaluation. Completion: satiation 4.5 < 7. Held.
- Ren: ref-11 subject "Marta" = intent subject "Marta." Reevaluation triggered →
```json
{ "reasoning": "I apologized but she didn't acknowledge it. Goal not met.
   I should keep trying.", "keep": true }
```
Completion: "Marta acknowledges apology" — not met. Held.

**6.9 Continuation options** →
```json
{ "options": [
    { "type": "dialogue", "description": "Say something to break the tension",
      "target": "Marta" },
    { "type": "dialogue", "description": "Ask Ren what happened last night",
      "target": "Ren" },
    { "type": "action", "description": "Stay quiet and drink coffee",
      "target": null },
    { "type": "relocation", "description": "Head to your room",
      "target": "Alex's bedroom" }
] }
```

### Turn 2

**6.1** — Alex selects: "Ask Ren what happened last night"

**6.2 Marta** →
```json
{ "reasoning": "Still cooking. Ren's apology is on my mind but I'm not ready
   to address it. I'll just finish making food.",
  "action": { "type": "action", "target": null,
    "description": "Plates the eggs and brings them to the table, setting one
     plate at her seat without offering any to Ren." } }
```
**6.2 Ren** →
```json
{ "reasoning": "Alex is asking me what happened. Maybe if I explain honestly
   in front of both of them, it'll help with Marta too.",
  "action": { "type": "dialogue", "target": "Alex",
    "description": "I was out with some friends and lost track of time. I tried
     to be quiet coming in but I knocked over that shelf in the hallway.
     I feel terrible about it." } }
```

**6.3a GM Challenge Setup** → All three actions get `result_override: "auto_succeed"`. No checks needed.

**6.4 Dice** — All auto_succeed.

**6.3b GM Consequence Resolution** → Marta gets drive effect: satiation +3 (eating). Alex and Ren: no effects.

**6.5 Narration** (streamed) →

> "So what happened last night?" Alex asks, looking at Ren over the rim of the coffee mug. Ren rubs the back of his neck. "I was out with some friends and lost track of time. I tried to be quiet coming in but I knocked over that shelf in the hallway. I feel terrible about it." At the stove, Marta plates the scrambled eggs and carries them to the table, setting one plate down at her own seat. She sits and starts eating without a word.

**6.6 Observation Extraction** →
```json
{ "observations": [
    { "subject": "Ren",
      "content": "Ren explains he was out late with friends, accidentally knocked
       over the hallway shelf, and feels bad about it.",
      "importance": 3, "visibility": "public" },
    { "subject": "Marta",
      "content": "Marta plates eggs only for herself and sits down to eat without
       offering food to anyone.",
      "importance": 3, "visibility": "public" }
] }
```

Alex's question omitted — it's a trigger for Ren's answer, not independently notable. IDs: obs-53, obs-54.

**6.7 Programmatic** — Marta satiation 4.5→7.5 (+3 from 6.3b drive_effects), decay → 7.0, energy → 5.0. Ren satiation → 3.0, energy → 2.0. Time → 8:17 AM.

**6.7 Marta processing** → (receives obs-53, obs-54)
```json
{ "emotional_diffs": {
    "global": [],
    "relationship": [
      { "target": "Ren", "name": "resentment", "change": -1,
        "reasoning": "Hearing the full story — it was an accident, not
         carelessness." }
    ] },
  "reflection": {
    "subject": ["Ren"],
    "content": "He wasn't being inconsiderate on purpose. He knocked over the
     shelf by accident. I've been giving him the cold shoulder over an accident.",
    "importance": 4,
    "source_observation_ids": ["obs-51", "obs-53"] } }
```

**6.7 Ren processing** → (receives obs-53, obs-54)
```json
{ "emotional_diffs": {
    "global": [],
    "relationship": [
      { "target": "Marta", "name": "affection", "change": -1,
        "reasoning": "She made food only for herself. Pointed exclusion." }
    ] },
  "reflection": null }
```

Ren produces no reflection — he noticed the exclusion but it's not a new realization. Applied: Marta resentment→Ren 4→3, Ren affection→Marta 6→5. Marta's reflection stored as ref-12.

**6.8 Intent lifecycle** —
- Marta: ref-12 subject "Ren" ≠ intent "breakfast." No reevaluation. Completion: satiation 7.0 ≥ 7. **Met.** Intent cleared.
- Ren: no reflection → no reevaluation. Completion: "Marta acknowledges apology" — not met. Held.

**6.9 Continuation options** →
```json
{ "options": [
    { "type": "dialogue", "description": "Ask Marta if she's okay",
      "target": "Marta" },
    { "type": "dialogue", "description": "Tell Ren it's not a big deal",
      "target": "Ren" },
    { "type": "action", "description": "Make some toast for yourself and Ren",
      "target": null },
    { "type": "time_skip", "description": "Finish breakfast quietly",
      "target": "8:30 AM" }
] }
```

### State After Turn 2

```
Marta:
  drives: { satiation: 7.0, energy: 5.0 }
  relationships: { Ren: { trust: 4, resentment: 3 } }
  intent: null (completed — new intent generated at start of turn 3)
  stream: obs-50(2), obs-51(4), obs-52(3), ref-10(3), obs-53(3), obs-54(3), ref-12(4)

Ren:
  drives: { satiation: 3.0, energy: 2.0 }
  relationships: { Marta: { trust: 5, affection: 5 } }
  intent: "apologize to Marta" (still active — not acknowledged)
  stream: obs-50(2), obs-51(4), obs-52(3), ref-11(3), obs-53(3), obs-54(3)
```

Both characters share obs-50 through obs-54 (same content, same IDs). Reflections are character-specific: Marta has ref-10 and ref-12, Ren has ref-11. Note Ren's low energy (2.0) — if his apology intent completes or is abandoned, his next intent will likely be drive-motivated (rest or eat).

### Data Flow Diagram

```
6.1 user input
    ↓
6.2 [per NPC] → actions → 6.3a GM challenge setup
    ↓
    evaluations: result_override, checks, DCs, departures (NO drive_effects)
    ↓
6.4 dice resolution
    ↓
    outcomes (success/failure/auto_succeed/auto_fail)
    ↓
6.3b GM consequence resolution ← outcomes + world state
    ↓
    drive_effects, reactive_effects per action
    ↓
6.5 narration ← outcomes + consequences + world state + history
    ↓ (streamed to user)
6.6 observation extraction ← narration + outcomes
    ↓
    shared observations (engine distributes)
    ↓
6.7 programmatic: drive_effects, reactive_effects, decay, time, departures
    ↓
6.7 [per NPC] character processing ← this NPC's observations
    ↓
    state_diffs + optional reflection
    ↓
6.8 intent lifecycle ← reflection subject vs intent subject
    ↓
6.9 continuation options → presented to user
    ↓
6.10 loop → 6.1
```

## 10. Open Design Questions

Issues identified during design that need further exploration.

### NPC Location Presence (TBD — optional, game-type dependent)

**Problem**: when the user relocates, the system needs to determine which NPCs are at the new location. In many game types, this is handled by scenario authoring or user choice (e.g., "go talk to Marta"). But for open-world-style play where characters move autonomously, the system needs a way to populate locations without scripting.

**Possible approaches** (not yet committed):
- **Location affinities**: per-character, per-location weights (optionally time-of-day modulated) representing how likely they are to be found there. Authored on the character card. Engine rolls against weights on relocation.
- **Intent-driven presence**: derive from NPCs' last known intent. If intent was "go to the market," they're at the market. Uses `intended_destination` tracked on departure.
- **Relationship/reflection pull**: NPCs with unresolved business (recent reflections referencing the user or characters at the user's location) get a boosted appearance probability.

**Considerations**:
- Not every game type needs this. Many scenarios will have fixed or user-directed character placement.
- Risk of locations being empty or overcrowded if not balanced. May need soft caps or probability.
- This is an area for future improvement, not a launch blocker.

**Status**: TBD. Deferred as optional enhancement for open-world game types.
