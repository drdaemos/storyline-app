# Example Walkthrough: Complete Turn Flow

Companion to: interactive-npc-design.md, prompt-templates.md

This walkthrough traces two complete turns showing every output and how data flows between steps. Only outputs are shown — prompts are in prompt-templates.md.

## Setup

**Scenario**: Slice-of-life. Shared apartment kitchen, morning.

**User persona**: Alex (the player)
**NPCs**: Marta (roommate), Ren (roommate)

**Relevant state at turn start**:

```
World state: { location: "apartment kitchen", time: "8:15 AM" }
Characters present: [Alex (user), Marta, Ren]

Marta:
  drives: { satiation: 3/10, energy: 6/10 }
  emotional_state:
    global: { composure: 7/10 }
    relationships: { Alex: { trust: 6/10 }, Ren: { trust: 4/10, resentment: 5/10 } }
  intent: { goal: "make breakfast", success_condition: { type: "drive_threshold", drive: "satiation", operator: ">=", threshold: 7 } }
  recent_memory: [obs-41] "Ren came home at 3 AM last night."

Ren:
  drives: { satiation: 4/10, energy: 3/10 }
  emotional_state:
    global: { composure: 5/10, confidence: 4/10 }
    relationships: { Marta: { trust: 5/10, affection: 6/10 }, Alex: { trust: 7/10 } }
  intent: { goal: "apologize to Marta for waking everyone up", success_condition: { type: "narrative", description: "Marta acknowledges the apology" } }
  recent_memory: [obs-40] "Marta gave me a cold look when I walked in."
```

---

## Turn 1

### 6.1 User Input

Alex (user) types: `"I pour myself some coffee and sit down at the table"`

Input classification: skipped (this is clearly an in-location action).

### 6.2 Character Action Generation

**Marta's call** → output:
```json
{
  "reasoning": "I'm hungry and Ren is here but I'm still annoyed about last night. I'll focus on cooking and not engage.",
  "action": {
    "type": "action",
    "target": null,
    "description": "Opens the fridge and starts pulling out eggs and butter, keeping her back to the table."
  }
}
```

**Ren's call** → output:
```json
{
  "reasoning": "She's right there at the stove. Better to say something now before it gets more awkward.",
  "action": {
    "type": "dialogue",
    "target": "Marta",
    "description": "Hey, Marta — I'm sorry about last night. I didn't mean to wake everyone up."
  }
}
```

### 6.3a GM Challenge Setup

Input: all three actions (Alex's coffee + Marta cooking + Ren's apology).

```json
{
  "evaluations": [
    {
      "character": "Alex",
      "action_summary": "Pour coffee and sit at table",
      "reasoning": "Mundane domestic action, no uncertainty.",
      "result_override": "auto_succeed",
      "check_required": false,
      "skill": null,
      "dc": null,
      "contested_with": null,
      "departure": false
    },
    {
      "character": "Marta",
      "action_summary": "Get eggs and butter from fridge, start cooking",
      "reasoning": "Routine kitchen activity.",
      "result_override": "auto_succeed",
      "check_required": false,
      "skill": null,
      "dc": null,
      "contested_with": null,
      "departure": false
    },
    {
      "character": "Ren",
      "action_summary": "Apologize to Marta for waking everyone",
      "reasoning": "Sincere apology to someone who's annoyed. Whether it lands well depends on delivery. Persuasion check, moderate difficulty given Marta's current resentment.",
      "result_override": null,
      "check_required": true,
      "skill": "persuasion",
      "dc": 13,
      "contested_with": null,
      "departure": false
    }
  ]
}
```

### 6.4 Dice Resolution

- Alex: auto_succeed (result_override)
- Marta: auto_succeed (result_override)
- Ren: persuasion check. Ren's persuasion = 2. Roll: 1d20 + 2 = 14. DC 13. **Success.**

```
outcomes: [
  { character: "Alex", action: "Pour coffee and sit", result: "auto_succeed", roll: null },
  { character: "Marta", action: "Cook eggs", result: "auto_succeed", roll: null },
  { character: "Ren", action: "Apologize to Marta", result: "success", roll: "14 vs DC 13" }
]
```

### 6.3b GM Consequence Resolution

Input: all outcomes with resolved results.

```json
{
  "consequences": [
    {
      "character": "Alex",
      "action_ref": "Pour coffee and sit at table",
      "drive_effects": [],
      "reactive_effects": [],
      "reasoning": "Mundane action, no consequences."
    },
    {
      "character": "Marta",
      "action_ref": "Get eggs and butter from fridge, start cooking",
      "drive_effects": [{ "drive": "satiation", "change": 2 }],
      "reactive_effects": [],
      "reasoning": "Cooking produces food — satiation increases."
    },
    {
      "character": "Ren",
      "action_ref": "Apologize to Marta for waking everyone",
      "drive_effects": [],
      "reactive_effects": [],
      "reasoning": "Successful apology has no mechanical drive effect. Emotional impact handled in character processing."
    }
  ]
}
```

### 6.5 Narration

Input: outcomes + world state + narration history (empty — first turn).

Output (streamed to user):

> Alex pours a cup of coffee from the pot and settles into a chair at the kitchen table. At the stove, Marta pulls eggs and butter from the fridge without a word, cracking two eggs into a pan with practiced efficiency. Ren lingers near the doorway for a moment, then clears his throat. "Hey, Marta — I'm sorry about last night. I didn't mean to wake everyone up." His voice is careful, genuine. Marta's hand pauses over the pan for a beat before she continues cooking.

### 6.6 Observation Extraction

Input: narration + outcomes + characters present.

```json
{
  "observations": [
    {
      "subject": "Marta",
      "content": "Marta starts cooking eggs without greeting anyone, keeping her back to the table.",
      "importance": 2,
      "visibility": "public",
      "actor": null
    },
    {
      "subject": "Ren",
      "content": "Ren apologizes to Marta for waking everyone up last night, sounding sincere.",
      "importance": 4,
      "visibility": "public",
      "actor": null
    },
    {
      "subject": "Marta",
      "content": "Marta pauses briefly at Ren's apology but doesn't respond, continuing to cook.",
      "importance": 3,
      "visibility": "public",
      "actor": null
    }
  ]
}
```

Note: Alex pouring coffee is omitted — routine, not worth storing. Three shared observations, all `public`, distributed to both Marta's and Ren's event streams.

Engine assigns IDs: obs-50, obs-51, obs-52.

### 6.7 State Update, Character Processing & Observation Distribution

**Programmatic updates** (run first):
- Drive effects from 6.3b applied: Marta satiation 3 → 5 (drive effect +2 from cooking). No reactive effects this turn.
- All drives: decay applied (satiation -0.5/turn, energy -0.5/turn)
- Marta after decay: satiation 4.5, energy 5.5
- Ren after decay: satiation 3.5, energy 2.5
- Time: 8:15 → 8:16 AM
- Observations obs-50, obs-51, obs-52 distributed to both Marta and Ren event streams.

**Marta's character processing call** → input includes obs-50, obs-51, obs-52 + prior unreflected [obs-41]:

```json
{
  "state_diffs": [
    { "stat": "resentment", "target": "Ren", "change": -1, "reasoning": "The apology took effort — he didn't have to do it in front of Alex." }
  ],
  "reflection": {
    "subject": ["Ren"],
    "content": "Maybe I've been too hard on him. At least he owned up to it instead of pretending nothing happened.",
    "importance": 3,
    "source_observation_ids": ["obs-41", "obs-51", "obs-52"]
  }
}
```

**Ren's character processing call** → input includes obs-50, obs-51, obs-52 + prior unreflected [obs-40]:

```json
{
  "state_diffs": [
    { "stat": "composure", "target": null, "change": -1, "reasoning": "The non-response is worse than being told off." }
  ],
  "reflection": {
    "subject": ["Marta"],
    "content": "One apology isn't going to cut it. She needs to see I mean it, not just hear the words.",
    "importance": 3,
    "source_observation_ids": ["obs-51", "obs-52"]
  }
}
```

**Programmatic application:**
- Marta: resentment toward Ren 5 → 4
- Ren: global composure 5 → 4
- Marta's reflection stored as ref-10 (subject: ["Ren"], importance: 3, lower decay rate)
- Ren's reflection stored as ref-11 (subject: ["Marta"], importance: 3, lower decay rate)

### 6.8 Intent Lifecycle Check

**Marta**: ref-10 generated, subject "Ren" — does not overlap with current intent "make breakfast." No reevaluation triggered. Check completion: satiation = 4.5, threshold = 7. Not met. Intent held.

**Ren**: ref-11 generated, subject "Marta" — overlaps with intent "apologize to Marta." Reevaluation triggered.

**Ren reevaluation call** (6.8a):

```json
{
  "reasoning": "The silence doesn't mean rejection — she might be processing. Giving up after one attempt would be premature.",
  "keep": true
}
```

Intent held. Completion check: narrative condition "Marta acknowledges the apology" — not met (she didn't respond). Intent continues.

### 6.9 User Continuation Options

```json
{
  "options": [
    { "type": "dialogue", "description": "Say something to break the tension", "target": "Marta" },
    { "type": "dialogue", "description": "Ask Ren what happened last night", "target": "Ren" },
    { "type": "action", "description": "Stay quiet and drink coffee", "target": null },
    { "type": "relocation", "description": "Head to your room", "target": "Alex's bedroom" }
  ]
}
```

Turn 1 complete. Snapshot saved.

---

## Turn 2

### 6.1 User Input

Alex selects: `"Ask Ren what happened last night"`

### 6.2 Character Action Generation

**Marta's call** → input includes: obs-50, obs-51, obs-52, ref-10. Intent: "make breakfast."

```json
{
  "reasoning": "Ren's apology is on my mind but I'm not ready to address it. I'll just finish making food.",
  "action": {
    "type": "action",
    "target": null,
    "description": "Plates the eggs and brings them to the table, setting one plate at her seat without offering any to Ren."
  }
}
```

**Ren's call** → input includes: obs-50, obs-51, obs-52, ref-11. Intent: "apologize to Marta."

```json
{
  "reasoning": "Alex is asking me directly. If I explain honestly in front of both of them, maybe Marta will see it was a genuine accident.",
  "action": {
    "type": "dialogue",
    "target": "Alex",
    "description": "I was out with some friends and lost track of time. I tried to be quiet coming in but I knocked over that shelf in the hallway. I feel terrible about it."
  }
}
```

### 6.3a GM Challenge Setup

```json
{
  "evaluations": [
    {
      "character": "Alex",
      "action_summary": "Ask Ren what happened last night",
      "reasoning": "Casual question to a roommate, no check needed.",
      "result_override": "auto_succeed",
      "check_required": false,
      "skill": null,
      "dc": null,
      "contested_with": null,
      "departure": false
    },
    {
      "character": "Marta",
      "action_summary": "Plate eggs and bring to table, only for herself",
      "reasoning": "Domestic action. The deliberate exclusion of Ren is social but not a check — she's just not offering.",
      "result_override": "auto_succeed",
      "check_required": false,
      "skill": null,
      "dc": null,
      "contested_with": null,
      "departure": false
    },
    {
      "character": "Ren",
      "action_summary": "Explain last night to Alex honestly",
      "reasoning": "Straightforward honest account. No deception, no difficulty.",
      "result_override": "auto_succeed",
      "check_required": false,
      "skill": null,
      "dc": null,
      "contested_with": null,
      "departure": false
    }
  ]
}
```

### 6.4 Dice Resolution

All auto_succeed (result_override).

### 6.3b GM Consequence Resolution

```json
{
  "consequences": [
    {
      "character": "Alex",
      "action_ref": "Ask Ren what happened last night",
      "drive_effects": [],
      "reactive_effects": [],
      "reasoning": "Casual question, no mechanical consequence."
    },
    {
      "character": "Marta",
      "action_ref": "Plate eggs and bring to table, only for herself",
      "drive_effects": [{ "drive": "satiation", "change": 3 }],
      "reactive_effects": [],
      "reasoning": "Eating a full plate of eggs restores satiation."
    },
    {
      "character": "Ren",
      "action_ref": "Explain last night to Alex honestly",
      "drive_effects": [],
      "reactive_effects": [],
      "reasoning": "Honest explanation has no mechanical drive effect."
    }
  ]
}
```

### 6.5 Narration

Input: outcomes + world state + narration history (turn 1 narration).

> "So what happened last night?" Alex asks, looking at Ren over the rim of the coffee mug. Ren rubs the back of his neck. "I was out with some friends and lost track of time. I tried to be quiet coming in but I knocked over that shelf in the hallway. I feel terrible about it." At the stove, Marta plates the scrambled eggs and carries them to the table, setting one plate down at her own seat. She sits and starts eating without a word.

### 6.6 Observation Extraction

```json
{
  "observations": [
    {
      "subject": "Ren",
      "content": "Ren explains he was out late with friends, accidentally knocked over the hallway shelf, and feels bad about it.",
      "importance": 3,
      "visibility": "public",
      "actor": null
    },
    {
      "subject": "Marta",
      "content": "Marta plates eggs only for herself and sits down to eat without offering food to anyone.",
      "importance": 3,
      "visibility": "public",
      "actor": null
    }
  ]
}
```

Alex's question omitted — it's the trigger for Ren's answer, but the observation is Ren's explanation, not the question itself. Engine assigns: obs-53, obs-54.

### 6.7 State Update, Character Processing & Observation Distribution

**Programmatic:**
- Drive effects from 6.3b applied: Marta satiation 4.5 → 7.5 (drive effect +3 from eating). No reactive effects this turn.
- All drives decay: Marta satiation 7.5 → 7.0, energy 5.5 → 5.0. Ren satiation 3.5 → 3.0, energy 2.5 → 2.0
- Time: 8:16 → 8:17 AM
- obs-53, obs-54 distributed to Marta and Ren.

**Marta's character processing call** → input includes obs-53, obs-54 (this turn) + no prior unreflected:

```json
{
  "state_diffs": [
    { "stat": "resentment", "target": "Ren", "change": -1, "reasoning": "The full story makes it sound like a genuine accident, not carelessness." }
  ],
  "reflection": {
    "subject": ["Ren"],
    "content": "I've been punishing him for an accident. That's not fair — I'd want the same grace if it were me.",
    "importance": 4,
    "source_observation_ids": ["obs-51", "obs-53"]
  }
}
```

**Ren's character processing call** → input includes obs-53, obs-54 (this turn):

```json
{
  "state_diffs": [
    { "stat": "affection", "target": "Marta", "change": -1, "reasoning": "The deliberate exclusion stings more than the silence did." }
  ],
  "reflection": null
}
```

Note: Ren's turn produces no reflection — he noticed Marta's exclusion but it's not a new realization on top of what he already knows. The LLM judged correctly that this doesn't warrant a new thought.

**Application:**
- Marta: resentment toward Ren 4 → 3
- Ren: affection toward Marta 6 → 5
- Marta's reflection stored as ref-12 (subject: ["Ren"], importance: 4)

### 6.8 Intent Lifecycle Check

**Marta**: ref-12 generated, subject "Ren" — does not overlap with intent "make breakfast." No reevaluation. Check completion: satiation = 7.0, threshold = 7. **Met.** Intent completed and cleared. New intent needed next turn.

**Ren**: no reflection generated. Check completion: "Marta acknowledges the apology" — still not met. Intent continues.

### 6.9 User Continuation Options

```json
{
  "options": [
    { "type": "dialogue", "description": "Ask Marta if she's okay", "target": "Marta" },
    { "type": "dialogue", "description": "Tell Ren it's not a big deal", "target": "Ren" },
    { "type": "action", "description": "Make some toast for yourself and Ren", "target": null },
    { "type": "time_skip", "description": "Finish breakfast quietly", "target": "8:30 AM" }
  ]
}
```

Turn 2 complete. Snapshot saved.

---

## State After Turn 2

```
Marta:
  drives: { satiation: 7.0/10, energy: 5.0/10 }
  emotional_state:
    relationships: { Ren: { trust: 4/10, resentment: 3/10 } }
  intent: null (completed — will generate new intent at start of turn 3)
  event_stream (recent):
    [obs-50] "Marta starts cooking eggs without greeting anyone..."     importance: 2
    [obs-51] "Ren apologizes to Marta for waking everyone..."           importance: 4
    [obs-52] "Marta pauses briefly at Ren's apology..."                 importance: 3
    [ref-10] "Maybe I've been too hard on him..."                      importance: 3
    [obs-53] "Ren explains he was out late with friends..."             importance: 3
    [obs-54] "Marta plates eggs only for herself..."                    importance: 3
    [ref-12] "I've been punishing him for an accident..."              importance: 4

Ren:
  drives: { satiation: 3.0/10, energy: 2.0/10 }
  emotional_state:
    global: { composure: 4/10 }
    relationships: { Marta: { trust: 5/10, affection: 5/10 } }
  intent: { goal: "apologize to Marta", ... } (still active)
  event_stream (recent):
    [obs-50] "Marta starts cooking eggs without greeting anyone..."     importance: 2
    [obs-51] "Ren apologizes to Marta for waking everyone..."           importance: 4
    [obs-52] "Marta pauses briefly at Ren's apology..."                 importance: 3
    [ref-11] "One apology isn't going to cut it..."                    importance: 3
    [obs-53] "Ren explains he was out late with friends..."             importance: 3
    [obs-54] "Marta plates eggs only for herself..."                    importance: 3
```

## Data Flow Summary

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
