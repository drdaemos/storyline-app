# Script JSON Schema — DRAFT (not committed)

Complete format definition plus a worked example. Draft-only choices are marked `[D#]` and listed at the end.

## 1. Top level

```json
{
  "meta": { "title": "string", "protagonist": "character_name" },
  "state_vars": [ /* StateVar */ ],
  "start_scene": "scene_id",
  "scenes": [ /* Scene */ ]
}
```

## 2. StateVar

```json
{ "name": "met_alice",      "type": "flag",    "initial": false }
{ "name": "affinity_alice", "type": "counter", "max": 5, "initial": 0 }
{ "name": "town_status",    "type": "enum",    "values": ["calm", "alert"], "initial": "calm" }
```

Declared once, fixed at generation. Runtime cannot create variables.

## 3. Condition, Guard, Effect

**Condition** — one of:
```json
{ "var": "affinity_alice", "op": ">=", "value": 3 }
{ "visited": "sc_market", "value": false }
```
- Var ops: `==`, `>=`, `<=`. Visited `value` defaults to `true`; targets a scene or beat id. [D7]

**Guard** — a list of conditions, **AND** semantics. OR = multiple edges/options with the same target. Empty/absent = always true. [D4]

**Effect**:
```json
{ "var": "affinity_alice", "op": "inc", "value": 1 }
```
- Ops: `set`, `inc`, `dec`; clamped to the variable's domain. [D2]

## 4. Scene

```json
{
  "id": "sc_market",
  "intent": "free-form: what entering this scene means (narration source; shown as a choice option at open exits)",
  "prerequisites": [ /* Guard */ ],
  "repeatable": false,
  "forced": null,
  "entry_beat": "beat_id",
  "beats": [ /* Beat */ ]
}
```

- **Available** = prerequisites match state + visitedness. Once-only built in: visited + `repeatable: false` → never available again.
- `forced` — optional integer. At an open exit, highest forced available scene auto-enters; equal forced priorities among available scenes = generation-time error. `null` = player-choosable. [D6]
- Exactly one entry beat. An **exit node** is a beat carrying `exit_edges` or `exit: "open"`; exit routing and in-scene routing are mutually exclusive on one beat. [D1]
- Invariant: the subgraph of non-gated beats/edges must connect entry to an exit.

## 5. Beat

Common fields:

```json
{
  "id": "b_arrive",
  "type": "plain | check | choice | ending",
  "intent": "free-form: what happens here (narration source, no prose)",
  "effects": [ /* Effect, optional */ ],
  "extension": { "deeper_domain": "free-form, optional" }
}
```

- `extension` — presence marks an extension point; the micro-loop returns here; skip path = the beat's normal routing. [D3]

Routing, by type — exactly one block:

**plain**
```json
{ "next": "beat_id" }
{ "exit_edges": [ { "target_scene": "sc_x", "guard": [ /* Guard */ ], "priority": 1 } ] }
{ "exit": "open" }
```
- Exit edges: highest-priority eligible wins; equal priorities on one exit node = generation-time error.
- `exit: "open"`: runtime queries the pool; forced preempts, else available scenes' intents are presented as ordinary choice options.

**check**
```json
{
  "check": {
    "difficulty": 12,
    "modifiers": [ { "var": "injured", "op": "==", "value": true, "mod": -2 } ],
    "on_success": "beat_id",
    "on_failure": "beat_id"
  }
}
```
- A modifier = condition + `mod`; applicable mods sum. Resolution: f(roll, difficulty, sum) — roll model is a hardcoded placeholder in the prototype, redesigned next version. [D5]

**choice**
```json
{ "options": [ { "intent": "free-form", "guard": [ /* Guard */ ], "target": "beat_id" } ] }
```
- Guarded options are additive only (non-gated path invariant).

**ending**
```json
{ "ending_id": "good_end_reconciliation" }
```
- Terminal; `ending_id` is what the softlock checker consumes as an intended ending.

## 6. Input: premise / goal

Part of the input object, not the script.

```json
"premise": {
  "synopsis": "free-form: starting situation and central conflict",
  "protagonist_goal": "free-form: what the protagonist wants",
  "scope": { "target_scenes": 8, "target_endings": 3 }
}
```
- `scope` is structured because counts are hard-gateable (output matches requested scope = automatable check). [D8]

## 7. Worked example

Minimal script exercising every element: 2 scenes + 1 forced scene, a check, a choice with a gated option, an extension point, an open exit, two endings.

```json
{
  "meta": { "title": "The Locked Granary", "protagonist": "Mara" },
  "state_vars": [
    { "name": "injured",     "type": "flag", "initial": false },
    { "name": "has_key",     "type": "flag", "initial": false },
    { "name": "guard_trust", "type": "counter", "max": 3, "initial": 0 }
  ],
  "start_scene": "sc_gate",
  "scenes": [
    {
      "id": "sc_gate",
      "intent": "Talk your way past the granary guard",
      "prerequisites": [],
      "repeatable": false,
      "forced": null,
      "entry_beat": "b_approach",
      "beats": [
        {
          "id": "b_approach",
          "type": "plain",
          "intent": "Mara approaches the gate; the guard blocks the way",
          "extension": { "deeper_domain": "guard's appearance, gate details, evening atmosphere" },
          "next": "b_talk"
        },
        {
          "id": "b_talk",
          "type": "choice",
          "intent": "How does Mara handle the guard?",
          "options": [
            { "intent": "Persuade him", "target": "b_persuade" },
            { "intent": "Slip past while he is distracted", "target": "b_sneak" },
            { "intent": "Mention his sister vouched for you", "guard": [ { "var": "guard_trust", "op": ">=", "value": 1 } ], "target": "b_vouched" }
          ]
        },
        {
          "id": "b_persuade",
          "type": "plain",
          "intent": "The guard softens but does not yield; Mara learns his name",
          "effects": [ { "var": "guard_trust", "op": "inc", "value": 1 } ],
          "next": "b_talk"
        },
        {
          "id": "b_sneak",
          "type": "check",
          "intent": "Mara tries to slip past unnoticed",
          "check": {
            "difficulty": 12,
            "modifiers": [ { "var": "injured", "op": "==", "value": true, "mod": -2 } ],
            "on_success": "b_inside",
            "on_failure": "b_caught"
          }
        },
        {
          "id": "b_caught",
          "type": "plain",
          "intent": "Caught and thrown back; Mara twists her ankle",
          "effects": [ { "var": "injured", "op": "set", "value": true } ],
          "next": "b_talk"
        },
        {
          "id": "b_vouched",
          "type": "plain",
          "intent": "The guard relents and hands over the side-door key",
          "effects": [ { "var": "has_key", "op": "set", "value": true } ],
          "next": "b_inside"
        },
        {
          "id": "b_inside",
          "type": "plain",
          "intent": "Mara is past the gate, in the granary yard",
          "exit": "open"
        }
      ]
    },
    {
      "id": "sc_granary",
      "intent": "Search the granary for the ledger",
      "prerequisites": [],
      "repeatable": false,
      "forced": null,
      "entry_beat": "b_search",
      "beats": [
        {
          "id": "b_search",
          "type": "plain",
          "intent": "Mara searches the granary",
          "exit_edges": [
            { "target_scene": "sc_reckoning", "guard": [ { "var": "has_key", "op": "==", "value": true } ], "priority": 2 },
            { "target_scene": "sc_reckoning", "guard": [], "priority": 1 }
          ]
        }
      ]
    },
    {
      "id": "sc_reckoning",
      "intent": "Face the granary master",
      "prerequisites": [ { "visited": "sc_gate" } ],
      "repeatable": false,
      "forced": 1,
      "entry_beat": "b_confront",
      "beats": [
        {
          "id": "b_confront",
          "type": "choice",
          "intent": "The granary master demands an explanation",
          "options": [
            { "intent": "Tell the truth", "target": "b_end_truth" },
            { "intent": "Run", "target": "b_end_run" }
          ]
        },
        { "id": "b_end_truth", "type": "ending", "intent": "Mara confesses; an uneasy bargain is struck", "ending_id": "end_bargain" },
        { "id": "b_end_run",   "type": "ending", "intent": "Mara flees into the night, ledgerless", "ending_id": "end_flight" }
      ]
    }
  ]
}
```

Notes on the example:
- `sc_gate` keeps the non-gated path invariant: persuade-loop → vouched option requires trust, but sneak success reaches `b_inside` ungated.
- `b_persuade` → `b_talk` reconverges (in-scene mini-graph); `b_caught` shows an effect feeding a later check modifier.
- `sc_reckoning` is forced: when `b_inside`'s open exit fires, it preempts player choice if available — here it demonstrates the mechanism; with `sc_granary` also available, `sc_reckoning` wins by being forced.
- The two `exit_edges` in `sc_granary` show priority + the always-true fallback edge.

## Draft-only choices needing confirmation

- **[D1]** Exit node = beat with `exit_edges` or `exit: "open"`; mutually exclusive with in-scene routing on one beat.
- **[D2]** Effect ops limited to `set` / `inc` / `dec`.
- **[D3]** Extension point is an annotation on any beat (not a beat type), carrying only `deeper_domain`; skip path = the beat's own routing.
- **[D4]** Guards are AND-lists; OR via duplicate edges. No nested boolean expressions.
- **[D5]** Check modifiers reuse the condition shape + `mod`; applicable mods sum. No per-unit counter scaling (finer granularity = multiple threshold conditions).
- **[D6]** Forced is a scene-level integer priority field, `null` when absent.
- **[D7]** Visited condition shape: `{ "visited": "id", "value": true|false }`, default true.
- **[D8]** Premise = two free-form fields (`synopsis`, `protagonist_goal`) + structured `scope` size knobs.
