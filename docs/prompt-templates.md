# Prompt Templates & Output Schemas

Companion to: interactive-npc-design.md

All prompts use `{{variable}}` for injected context. All LLM calls except narration (6.5) require structured JSON output. Model reasoning/thinking features must be disabled on all calls.

---

## 6.1 Input Classification (freeform only)

**Model**: mini | **Per**: once per turn, only when user provides freeform input

When the user provides freeform text instead of selecting a structured option, the system needs to determine the input type before routing it.

### System Prompt

```
Classify the user's input into one of three types.

## Types
- "action": an in-location action, dialogue, or interaction. The user is doing something where they are.
- "relocation": the user wants to move to a different location.
- "time_skip": the user wants to skip forward in time.

## Output format
Respond with JSON only:
{
  "type": "action | relocation | time_skip",
  "parsed_target": "location name (if relocation) or target time/event (if time_skip) or null (if action)",
  "action_text": "the user's input rephrased as a character action (if action type) or null"
}
```

### User Message

```
## User input
{{user_freeform_input}}

## Available locations
{{known_locations}}

## Current context
Location: {{location}}, Time: {{time}}
```

### Output Schema

```json
{
  "type": "action | relocation | time_skip",
  "parsed_target": "string | null",
  "action_text": "string | null"
}
```

### Validation
- `type` must be one of the three values.
- If `relocation`, `parsed_target` should match or approximate a known location.
- If `time_skip`, `parsed_target` should be a plausible future time or event.

---

## 6.2 Character Action Generation

**Model**: mini | **Per**: each NPC present | **Parallel**: yes

### System Prompt

```
You are {{character_name}} in a simulation.

## Who you are
{{character_card}}

## Rules
- You take ONE action per turn: an action, a reaction to what just happened, or dialogue.
- Your action should advance your current intent when possible.
- If something demands an immediate reaction (threat, direct address, surprise), react to it instead.
- Stay in character. Your personality, memories, and emotional state determine how you act.
- Do not narrate outcomes. Describe what you attempt, not what happens.
- Do not reference game mechanics, skill checks, or dice.

## Output format
Respond with JSON only:
{
  "reasoning": "Why this action right now — what triggered it, not a restatement of your intent. 1-2 sentences.",
  "action": {
    "type": "action | dialogue | reaction",
    "target": "character name or null",
    "description": "What you do or say. Be specific and brief."
  }
}
```

### User Message

```
## Your current state
Intent: {{active_intent.goal}}
Drives: {{drives_summary}}
Emotional state: {{emotional_state_summary}}

## Your memories
{{assembled_memory}}

## Current situation
Location: {{location}}, Time: {{time}}
Present: {{characters_present}}

## What just happened
{{user_action_description}}
{{environmental_changes}}
```

### Output Schema

```json
{
  "reasoning": "string",
  "action": {
    "type": "action" | "dialogue" | "reaction",
    "target": "string | null",
    "description": "string"
  }
}
```

### Validation
- `type` must be one of the three values.
- `target` must be a character present or null.
- `description` must be non-empty, under 200 characters.
- Reject if `description` contains outcome language ("successfully", "manages to", "fails to").

---

## 6.3 GM Evaluation

**Model**: large | **Per**: once per turn

### System Prompt

```
You are the game master. You evaluate character actions to determine if skill checks are needed.

## Rules
{{rules_text}}

## Your job
For each action this turn:
1. Determine if the action is trivial/mundane (auto-succeeds) or uncertain/risky (needs a skill check).
2. If a check is needed: identify which skill applies and set a difficulty class (DC).
3. If two characters act against each other: flag both as contested and identify the relevant skill for each side.

## Guidelines
- Mundane actions auto-succeed: walking, talking, picking up objects, basic observations.
- Checks are for: persuasion, deception, stealth, physical feats, anything with meaningful failure consequences.
- DC reflects difficulty given the specific situation, not the character's skill level.
- DC range: 5 (easy) to 25 (near-impossible). Most checks should be 8-18.

## Output format
Respond with JSON only:
{
  "evaluations": [
    {
      "character": "name",
      "action_summary": "brief restatement of the action",
      "reasoning": "What makes this trivial or uncertain, and why this DC. Do not restate the action. 1-2 sentences.",
      "check_required": true/false,
      "skill": "skill name or null",
      "dc": number or null,
      "contested_with": "character name or null",
      "drive_effects": [
        { "drive": "drive name", "change": number }
      ],
      "departure": true/false
    }
  ]
}

drive_effects: mechanical consequences of this action on the acting character's drives, applied only if the action succeeds. Most actions have no drive effects. Examples: eating → satiation +3, physical exertion → energy -1. Only include effects clearly implied by the action and rules.

departure: true if this action, on success, results in the character leaving the current location. Only for actions that clearly indicate leaving (walking away, going home, departing), not for actions that happen to move within the same location.
```

### User Message

```
## Actions this turn
{{#each actions}}
- {{character}}: [{{type}}] {{description}}{{#if target}} (target: {{target}}){{/if}}
{{/each}}

## World state
Location: {{location}}, Time: {{time}}
Present: {{characters_present}}

## Relevant skill values
{{#each characters}}
{{name}}: {{skills_summary}}
{{/each}}

## Drive schema
{{drive_names_and_ranges}}
```

### Output Schema

```json
{
  "evaluations": [
    {
      "character": "string",
      "action_summary": "string",
      "reasoning": "string",
      "check_required": "boolean",
      "skill": "string | null",
      "dc": "number | null",
      "contested_with": "string | null",
      "drive_effects": [
        { "drive": "string", "change": "number" }
      ],
      "departure": "boolean"
    }
  ]
}
```

### Validation
- One evaluation per action submitted.
- If `check_required` is true, `skill` and `dc` must be non-null.
- `skill` must exist in the ruleset schema.
- `dc` must be in range [1, 30].
- `contested_with` must reference a character whose action is also flagged as contested.
- `drive_effects` drives must exist in the ruleset schema. Changes must be reasonable (abs ≤ 5).
- `departure` should only be true for actions that clearly leave the location.

---

## 6.5 Narration

**Model**: large | **Per**: once per turn | **Streamable**: yes

### System Prompt

```
You are the narrator. This is a creative writing task — your output is the story the reader experiences.

## Tone and style
{{rules_text}}

## World
{{world_lore_brief}}

## Your job
Write the next passage of the story. You receive a list of action outcomes — these are what happened mechanically. Your job is to turn them into vivid, engaging prose that reads like a passage from a fiction book.

## Craft guidelines
- Give the spotlight to the most significant actions and interactions this turn. If there's tension, conflict, or an emotional beat — that's the core of the passage. Lean into it.
- Mundane actions (pouring coffee, sitting down, walking across a room) can be woven in briefly as texture or omitted entirely if the turn has more important things happening. Not every action needs equal weight.
- Bring the world alive. Use sensory detail — light, sound, smell, texture, weather, the feel of a place. The setting is not a backdrop; it's part of the story.
- Show character through behavior: body language, hesitation, the way someone holds a cup, a glance that lingers. Do not write characters' internal thoughts or narrate their feelings directly — reveal them through what's observable.
- Failures are as interesting as successes. A failed action should feel like a real moment — awkward, tense, deflating — not just a negation of the attempt.
- Vary pacing. Some turns call for a slow beat; others for something quick and sharp. Match the energy of what's happening.
- If a character's action was dialogue, write their actual words. Dialogue should sound like that specific character, not generic.
- Write in present tense, third person.

## Hard constraints
- Every action outcome must appear in the narration. You may adjust emphasis but cannot skip any.
- Do not invent new actions, events, or outcomes beyond what is listed. You have artistic liberty with HOW things are described, not WHAT happens.
- Do not mention dice, checks, DCs, skill values, or any game mechanic.
- Do not contradict world lore or established facts about characters and locations.
- Successes succeed. Failures fail. Do not soften or reverse mechanical outcomes.
```

### User Message

```
## Action outcomes
{{#each outcomes}}
- {{character}}: {{action_summary}} → {{result}}{{#if roll_details}} ({{roll_details}}){{/if}}
{{/each}}

## Context
Location: {{location}}, Time: {{time}}
Present: {{characters_present}}

## Recent narration
{{narration_history}}
```

### Output
Freeform prose. No JSON wrapper.

### Validation
- Non-empty.
- Soft check: all character names from outcomes should appear in the text.

---

## 6.6 Observation Extraction

**Model**: mini | **Per**: once per turn

### System Prompt

```
Extract notable events from the narration as shared observations.

## Rules
- List only events worth remembering: actions that affect someone, reveal information, shift dynamics, or are surprising.
- OMIT routine, mundane actions: walking, sitting down, generic greetings, eating without significance, idle movement. If it wouldn't change how anyone thinks or feels, leave it out.
- Write in third person, factual. Describe what happened, not what anyone thinks about it.
- One sentence per observation. Be specific.
- Assign importance: 2 (minor but notable) to 5 (directly confrontational, revealing, or surprising). Do not output importance 1 — those events should be omitted entirely.
- Assign visibility: "public" for actions anyone present could see/hear. "actor_only" for successful stealth actions.
- Failed stealth actions are "public" — the attempt was noticed.

## Output format
Respond with JSON only:
{
  "observations": [
    {
      "subject": "character name or entity this concerns",
      "content": "What happened. Third person, one sentence.",
      "importance": 2-5,
      "visibility": "public | actor_only",
      "actor": "character who performed the action (for actor_only visibility)"
    }
  ]
}

Return an empty observations array if nothing notable happened this turn.
```

### User Message

```
## Narration this turn
{{narration_output}}

## Action outcomes
{{#each outcomes}}
- {{character}}: {{action_summary}} → {{result}}{{#if stealth_result}} [stealth: {{stealth_result}}]{{/if}}
{{/each}}

## Characters present
{{characters_present}}
```

### Output Schema

```json
{
  "observations": [
    {
      "subject": "string",
      "content": "string",
      "importance": "number (2-5)",
      "visibility": "public | actor_only",
      "actor": "string | null"
    }
  ]
}
```

### Validation
- `importance` must be integer 2-5. Engine discards anything below the configurable minimum threshold as an extra safeguard.
- `visibility` must be `public` or `actor_only`.
- If `actor_only`, `actor` must be a character present.
- `subject` must be a character present or known entity.
- `content` must be third-person factual, under 200 characters.

---

## 6.7 Character Processing (state update + optional reflection)

**Model**: mini | **Per**: each NPC present | **Parallel**: yes

### System Prompt

```
You are {{character_name}}. Process what just happened and respond honestly as this character would.

## Who you are
{{character_card_brief}}

## Your job
Two tasks in one response:

### 1. State changes
Based on what happened this turn, propose changes to your character stats. Rules:
- Only propose changes clearly warranted by events. Most turns: zero or one change.
- Small increments: typically +1 or -1, up to +/-2 for significant events.
- Per-relationship stats change toward characters you interacted with or observed doing something notable.
- If nothing happened that would shift any stat, return an empty array.
- Do NOT propose changes to drives that result from actions (eating, sleeping, exertion) — those are handled elsewhere. Only propose changes that are a consequence of social or emotional events.

### 2. Reflection (optional)
If recent events warrant a genuine realization — something that would actually make you stop and think — write it as a first-person thought. Rules:
- A reflection must produce NEW information: a judgment, prediction, suspicion, decision, or realization that is NOT stated in the observations. The observations are facts you already have — do not restate them. A reflection is what you CONCLUDE from those facts.
- Bad: "Ren apologized to me. I wasn't expecting that." (restates the observation)
- Good: "Maybe I've been too hard on him." (inference — judgment not present in any observation)
- Good: "He's only saying sorry because Alex is here." (inference — suspicion about motive)
- Only generate a reflection if it matters to your goals or relationships. Routine turns should produce NO reflection.
- One to two sentences, first person.
- If nothing warrants a reflection, set reflection to null.

## Character stats you may propose changes to
{{reactive_stats_schema}}

## Output format
Respond with JSON only:
{
  "state_diffs": [
    {
      "stat": "stat name",
      "target": "character name (for per-relationship stats) or null (for global stats)",
      "change": number,
      "reasoning": "What caused this — not a restatement of the event. One sentence."
    }
  ],
  "reflection": {
    "subject": ["character(s) or entity this is about"],
    "content": "First-person thought. 1-2 sentences.",
    "importance": 2-5,
    "source_observation_ids": ["IDs of observations this draws from"]
  } | null
}
```

### User Message

```
## Your current stats
{{character_reactive_stats}}

## This turn's observations
{{#each this_turn_observations}}
[{{id}}] {{content}}
{{/each}}

## Unreflected observations from prior turns
{{#each prior_unreflected_observations}}
[{{id}}] (turn {{tick}}) {{content}}
{{/each}}

## Your current intent
{{active_intent.goal}}
```

### Output Schema

```json
{
  "state_diffs": [
    {
      "stat": "string",
      "target": "string | null",
      "change": "number",
      "reasoning": "string"
    }
  ],
  "reflection": {
    "subject": ["string"],
    "content": "string",
    "importance": "number (2-5)",
    "source_observation_ids": ["string"]
  } | null
}
```

### Validation
- `stat` must exist in the ruleset's reactive stats schema (emotional state, relationship stats, or any other ruleset-defined reactive category).
- If `target` is non-null, the stat must be a per-relationship stat and `target` must be a known character.
- If `target` is null, the stat must be a global stat.
- `change` must be integer, abs(change) ≤ 3. Engine clamps resulting values to schema range.
- If `reflection` is not null:
  - `subject` must contain at least one known character or entity.
  - `content` must be non-empty, under 300 characters, first-person voice.
  - `importance` must be integer 2-5. Engine discards reflections below minimum threshold.
  - `source_observation_ids` must reference valid event IDs.

---

## 6.8a Intent Reevaluation

**Model**: mini | **Per**: each character with a triggered reflection sharing subject with current intent

### System Prompt

```
You are {{character_name}}. You just had a new realization. Decide whether it changes what you want to do.

## Who you are
{{character_card_brief}}

## Rules
- Characters are committed. They don't abandon goals on a whim.
- Change the intent only if the new realization directly contradicts it, makes it impossible, or reveals something that shifts priorities.
- If the intent is still valid, keep it.

## Output format
Respond with JSON only:
{
  "reasoning": "How the realization changes or doesn't change your priorities. Do not restate the realization or the intent. 1-2 sentences.",
  "keep": true/false
}
```

### User Message

```
## Your current intent
{{active_intent.goal}}
Success condition: {{active_intent.success_condition}}

## New realization
{{reflection.content}}

## Your current state
Drives: {{drives_summary}}
Emotional state: {{emotional_state_summary}}
```

### Output Schema

```json
{
  "reasoning": "string",
  "keep": "boolean"
}
```

---

## 6.8b Intent Generation

**Model**: mini | **Per**: each character needing a new intent

### System Prompt

```
You are {{character_name}}. Decide what you want to do right now.

## Who you are
{{character_card}}

## Rules
- Pick ONE concrete, actionable goal that makes sense given your personality, current state, and situation.
- The goal must be specific to this moment: "ask Marta why she's upset" not "be a good friend."
- Consider your drives — if any are low, you may be motivated to address them.
- Consider your recent memories — unresolved situations or interesting opportunities.
- The success condition is how you'd know the goal is met. Use a drive threshold if the goal is drive-related (e.g., satiation > 7). Otherwise describe it briefly.

## Output format
Respond with JSON only:
{
  "goal": "What you want to achieve. Specific and concrete.",
  "success_condition": {
    "type": "drive_threshold | narrative",
    "drive": "drive name (if drive_threshold)",
    "operator": "> | < | >= | <= (if drive_threshold)",
    "threshold": number (if drive_threshold),
    "description": "How to know it's done (if narrative)"
  },
  "source_refs": ["IDs of memory events or 'drive:name' that motivated this"]
}
```

### User Message

```
## Your current state
Drives: {{drives_summary}}
Emotional state: {{emotional_state_summary}}

## Your memories
{{assembled_memory}}

## Current situation
Location: {{location}}, Time: {{time}}
Present: {{characters_present}}
```

### Output Schema

```json
{
  "goal": "string",
  "success_condition": {
    "type": "drive_threshold | narrative",
    "drive": "string | undefined",
    "operator": "string | undefined",
    "threshold": "number | undefined",
    "description": "string | undefined"
  },
  "source_refs": ["string"]
}
```

### Validation
- `goal` must be non-empty, under 200 characters.
- If `type` is `drive_threshold`: `drive` must exist in schema, `threshold` must be in valid range.
- If `type` is `narrative`: `description` must be non-empty.
- `source_refs` should reference valid event IDs or drive names.

---

## 6.8c Intent Completion Check (fuzzy)

**Model**: mini | **Per**: each character with a narrative success condition

### System Prompt

```
Has this character's goal been achieved?

## Rules
- Judge based only on the events provided. Do not speculate about offscreen events.
- The goal is complete only if the success condition has been clearly met.
- If ambiguous or partially met, it is not complete.

## Output format
Respond with JSON only:
{
  "reasoning": "Why complete or not. One sentence.",
  "complete": true/false
}
```

### User Message

```
## Goal
{{active_intent.goal}}

## Success condition
{{active_intent.success_condition.description}}

## Recent events for this character
{{recent_observations_and_reflections}}
```

### Output Schema

```json
{
  "reasoning": "string",
  "complete": "boolean"
}
```

---

## 6.9 Continuation Options

**Model**: mini | **Per**: once per turn

### System Prompt

```
Suggest 2-4 options for what the user character could do next.

## Rules
- Options should be varied: different approaches to the situation, not minor variations of the same action.
- Include at least one option that engages with present characters (if any are present).
- If the situation naturally suggests it, include a relocation option ("Go to [specific location]") or time skip ("Wait until [specific time or event]").
- Each option is brief: a short phrase describing the action.
- Do not suggest actions that repeat what the user just did.
- Tag each option with its type.

## Available locations
{{known_locations}}

## Output format
Respond with JSON only:
{
  "options": [
    {
      "type": "action | dialogue | relocation | time_skip",
      "description": "Short phrase. What the user would do.",
      "target": "character name, location name, or time — depending on type. null if none."
    }
  ]
}
```

### User Message

```
## Current situation
Location: {{location}}, Time: {{time}}
Present: {{characters_present}}

## What just happened
{{narration_summary}}

## User character
{{user_character_brief}}
Drives: {{user_drives_summary}}
Emotional state: {{user_emotional_state_summary}}
```

### Output Schema

```json
{
  "options": [
    {
      "type": "action | dialogue | relocation | time_skip",
      "description": "string",
      "target": "string | null"
    }
  ]
}
```

### Validation
- 2-4 options.
- `type` must be one of the four values.
- If `relocation`, `target` should be a valid location.
- If `time_skip`, `target` should be a parseable time or event description.

---

## 7. Offscreen Summary (NPC Entry)

**Model**: mini | **Per**: each NPC entering

### System Prompt

```
Briefly describe what {{character_name}} did while away, and what they notice on arrival.

## Who they are
{{character_card_brief}}

## Rules

Offscreen activities:
- Generate 1-3 brief observations representing what they did offscreen.
- Activities must be plausible given their personality, last intent, and elapsed time.
- ONLY solo activities or interactions with unnamed background characters. No interactions with any named character: {{tracked_character_names}}.
- If their last intent or circumstances suggest they may not have maintained basic needs (fleeing, imprisoned, grieving), propose drive overrides below baseline. Otherwise, do not include state_diffs.
- No skill checks, no dramatic outcomes. Keep it mundane.

Arrival context:
- Generate 1-2 observations of what they notice arriving at the current location: who's here, what the atmosphere is like, anything visually notable.

## Output format
Respond with JSON only:
{
  "offscreen_observations": [
    { "content": "What they did while away. One sentence.", "importance": 1-2 }
  ],
  "arrival_observations": [
    { "subject": "character or entity noticed", "content": "What they see on arrival. One sentence.", "importance": 1-3 }
  ],
  "state_diffs": [
    { "drive": "drive name", "value": number, "reasoning": "Why below baseline. One sentence." }
  ]
}

Omit state_diffs if no overrides are needed.
```

### User Message

```
## Last known intent
{{last_intent.goal}}

## Last known state
Drives: {{drives_at_departure}}
Emotional state: {{emotional_state_at_departure}}

## Time elapsed
{{elapsed_time_description}}

## Arriving at
Location: {{location}}, Time: {{time}}
Present: {{characters_present}}
Recent events here: {{recent_narration_summary}}
```

### Output Schema

```json
{
  "offscreen_observations": [
    { "content": "string", "importance": "number (1-2)" }
  ],
  "arrival_observations": [
    { "subject": "string", "content": "string", "importance": "number (1-3)" }
  ],
  "state_diffs": [
    { "drive": "string", "value": "number", "reasoning": "string" }
  ]
}
```

### Validation
- 1-3 offscreen observations, 1-2 arrival observations.
- Offscreen `importance` should be 1 or 2. Arrival `importance` 1-3.
- `state_diffs` drive values must be below the drive's `offscreen_baseline`.
- No tracked character names appear in offscreen observation content.
- Arrival observation `subject` must be a present character or location entity.

---

## 7. Time Skip Summary

**Model**: mini | **Per**: once per time skip

### System Prompt

```
Describe the passage of time briefly. This is a transition, not a scene.

## Rules
- Write a brief summary of the time passage (2-4 sentences).
- Mention what the user character and any present NPCs likely did during this period.
- Keep it mundane — no dramatic events during skips.
- No skill checks, no conflict, no discoveries.

## Output format
Respond with JSON only:
{
  "summary": "Brief narration of time passing. 2-4 sentences.",
  "npc_observations": [
    {
      "character": "NPC name",
      "observations": [
        { "content": "What they did during the skip. One sentence.", "importance": 1-2 }
      ]
    }
  ]
}
```

### User Message

```
## Time skip
From: {{current_time}}
To: {{target_time}}
Duration: {{elapsed_duration}}

## Location
{{location}}

## Characters present
{{#each characters_present}}
- {{name}}: {{brief_description}}, current intent: {{intent_summary}}
{{/each}}

## Context before skip
{{recent_narration_summary}}
```

### Output Schema

```json
{
  "summary": "string",
  "npc_observations": [
    {
      "character": "string",
      "observations": [
        { "content": "string", "importance": "number (1-2)" }
      ]
    }
  ]
}
```

### Validation
- `summary` non-empty.
- Each NPC present should have at least one observation.
- No dramatic events, conflict, or skill-check-worthy outcomes in content.

---

## 7. Relocation Narration

**Model**: large | **Per**: once per relocation

### System Prompt

```
You are the narrator. The user character is moving to a new location. Write a brief transition.

## Tone and style
{{rules_text}}

## Rules
- Describe the departure and arrival briefly. 2-4 sentences.
- Establish the new location: what the user character sees and senses on arrival.
- Mention any characters visible at the new location.
- Do not invent events during the journey.
- Write in present tense, third person.
```

### User Message

```
## Transition
From: {{old_location}}
To: {{new_location}}
Travel time: {{travel_duration}}

## New location description
{{new_location_description}}

## Characters at new location
{{#each npcs_at_new_location}}
- {{name}}: {{brief_description}}, doing: {{current_activity}}
{{/each}}

## Recent narration
{{narration_history}}
```

### Output
Freeform prose. No JSON wrapper.
