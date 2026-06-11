# AI-Driven VN Generator — System Design

## Core Principles
1. Every AI component must be testable via automation, including creative ones.
   - Hard gate: adherence to script/module (structural + invariant checks).
   - Soft signal: LLM-as-judge detecting objective properties of output.
2. System stays as small and clean as possible. Every component must be purposeful.
3. The structural framework is minimal and uniform; a small set of reused primitives. Narrative type/complexity is expressed in how the generator uses the primitives (layers, guided by judged passes), never as new structural types.

## Two Subsystems

### A. Generation Pipeline (offline)
Produces a branching script (structural internals only — no prose) from inputs.
- **Staged pipeline**, not generate-then-repair: scene-level outline → per-scene mini-graphs → checks/effects. Each stage is validated before the next; failures stay local and repairs are small. Each stage has its own hard gate.

### B. Runtime / Narration Engine (online)
Plays the script: selects scenes, runs beats, resolves checks, and narrates.
- Narration reads skeleton + state + history and produces prose at play time.
- Narration MUST NOT change any outcome, state value, or check result.
- Detailed narration behavior is deferred; only its boundary is fixed here.

## Input Object
A single object holding both structured and free-form data.
- Structured: consumed by deterministic logic (validation, checks, branching).
- Free-form: consumed by the LLM for generation.
- Rule of thumb: data is structured only if usable in a generalized, deterministic way; otherwise free-form.

Fields:
- **Characters** (list). Each:
  - name — structured
  - background / appearance — free-form
  - ~~traits as tags~~ — **dropped**; no structured trait field. Character flavor lives in free-form fields. Check modification moved to state vars.
  - protagonist — structured flag. Kept for simplicity (POV anchor) despite tag removal.
- **Setting**:
  - world description — free-form
  - anchors, e.g. specific places — structured (shape undefined; see Gaps)
- **Rules** — mostly free-form. Tone, content boundaries, story mechanics, and check mechanics (roll type, modifier stacking, thresholds).
  - No deterministic trait-driven model.
- **Premise / goal** — undefined, deferred.

## State Model
- State is a fixed set of **named variables**, each with a declared **finite domain**.
- Shapes:
  - **flag** — domain {false, true}
  - **bounded counter** — domain {0..m}, declared max
  - **enum** — domain is a fixed value set
- A set (e.g. inventory) is modeled as a group of flags; there is no separate set type.
- Variables are **declared at generation time and fixed**. Runtime cannot create new variables.
- **Effects** are assignments, **clamped to the domain** (increment past max stays at max; an enum may only take an in-set value). State can never leave the declared space.
- **Effects attach to beats only.** Choices and check outcomes route to different beats; those beats carry the effects. Edges, options, and exits carry no effects.
- **Guards** are boolean expressions over variables (`var == v`, `var >= n`, flag).
- Total state space = product of all domains → bounded and enumerable by construction (satisfies the softlock checker).
- Namespace is flat; per-character state is a naming convention (e.g. `affinity_alice`). Confirmed.

## Checks & Randomness
- Story allows meaningful randomness (skill challenges / dice rolls).
- No character stats and no tags. **Check modifiers reference state vars**: each modifier is a condition over a state var plus a value, applied when the condition holds (e.g. `injured == true → -2`). State written by earlier beats thereby modifies later checks.
- A check is generator output inside the structure, NOT an input field.
- **Structural form: a check is a beat type** (check-beat) with exactly two outgoing edges, success and failure. No separate structural element; checks are nodes in the scene mini-graph and are validated as ordinary edges.
- At generation (offline): each check is emitted with difficulty and its state-conditional modifiers.
- At runtime (online): resolution is deterministic — f(roll, difficulty, modifiers whose conditions match current state). No LLM judgment at runtime.
- Both outcomes of a check (success and failure) must lead somewhere reachable.

## Script Structure
Format: structured data (JSON). Not a custom scripting language. Hybrid storylet + branching.

### Beats and Scenes
- The whole story is one graph of **beats**.
- **Beat types:** plain, check, choice, ending. The mini-graph is only beats + edges; all behavior variation lives in the beat type.
  - **choice**: one labeled outgoing edge per option; gated options are guarded edges.
  - **ending**: terminal beat (no outgoing edges) carrying an ending label; this is the explicit ending marking the softlock checker requires.
- A **scene** (= storylet) is a subgraph with one **entry node** and one or more **exit nodes**. A scene is exactly the run of beats from entry to exit.
- Inside a scene, beats connect directly and in-scene choices may reroute and reconverge (a mini-graph).
- In-scene beats and choice options may be **quality-gated**: state can unlock additional action/dialogue options within the scene. This is additive content, not a route switch.

### Scene commitment
- Quality-based *scene selection* (switching routes) fires ONLY at exit nodes. Between a scene's entry and its exit there is no scene-selection step, so the story cannot switch scenes mid-interchange. Commitment is structural, not an enforced rule.
- In-scene quality gating is allowed and is distinct from scene selection: it unlocks options inside the committed scene without leaving it.
- **Invariant:** every scene must always retain a non-gated path from entry to an exit. Gated beats/options are additive only; they can never be the sole way forward.

### Between-scene connection
- Scenes carry **prerequisites** (a guard over state + visitedness). A scene whose prerequisites match is **available**.
- **Scenes are once-only by default**: a visited scene is no longer available unless marked `repeatable`.
- Exits come in two kinds:
  - **Directed exit**: explicit exit edges `{ target_scene, guard, priority }` — authored continuations (the branching half).
    - A "forced" edge is simply one whose guard is always true; there is no separate `type` field.
    - An edge is eligible when its guard matches state. Selection takes the highest-priority eligible edge.
    - Equal priorities among edges of one exit node are a **generation-time validation error**.
  - **Open exit**: no targets; at runtime it queries the scene pool for available scenes (the storylet half). The generator decides which exits are open.
- **Selection at an open exit**: scenes may carry an optional `forced` priority. If any available scene is forced, the highest-priority forced one is entered automatically (equal priorities = generation-time error). Otherwise the **player chooses** from the available set.
- **Presentation**: scene selection is never exposed as such. Scenes carry an `intent` field (same name and semantics as beat intent: free-form, narration source). At an open exit the runtime presents available scenes' intents as ordinary choice options; picking one enters that scene. To the player an open exit is indistinguishable from a choice.
- Scene commitment is unchanged: pool queries happen only at exits, never mid-scene.
- The transition relation stays deterministic and enumerable (open-exit successors = scenes whose prerequisites match current state), so the softlock walk needs no new machinery — only a larger branching factor.

### Visitedness
- Runtime tracks visitedness **per scene and per beat** as built-in functionality, not state vars.
- Exposed as a condition type usable in any guard, prerequisite, or check modifier: `visited(scene_or_beat_id)`.
- Visited bits flip only false→true (monotone), so the softlock state space grows but never cycles.

### Extension points (micro-loop)
- The generator marks certain beats as **extension points**, chosen by scene tension.
- At an extension point the player may *go deeper* or *proceed*.
- *Go deeper* is a micro-loop: additional narration that returns to the same beat. It writes no state and adds no exit (outcome-neutral elaboration).
- The generator preplans the deeper-content domain and the skip path.
- Softlock analysis treats the micro-loop as an always-escapable self-loop.

### Runtime extension constraint
- Any live scene extension is limited to outcome-neutral elaboration.
- Anything that changes what can happen next must be generated offline into the skeleton, never improvised at runtime.

## Validation
### Softlock checker (generation-time)
- Deterministic walk over (scene graph × state space) that flags any node/state from which no intended ending is reachable; feeds failures back to the generator to adjust.
- **Walk variant: forward exploration over reachable states only** (from the initial state), not enumeration of the full domain product. Avoids combinatorial explosion from counters; semantics otherwise unchanged.
- Requires:
  - intended endings / gameovers are explicitly marked, to distinguish intended terminals from accidental dead-ends;
  - both outcomes of every check are explored and lead somewhere;
  - the state space is bounded and enumerable, or the walk does not terminate;
  - within each scene, the subgraph of non-gated beats/edges still connects entry to an exit (non-gated-path invariant).

## Story Quality Targets
- The LLM-as-judge harness is defined **alongside** the quality targets, not after: each target must be written as an objectively detectable property of the output (no unjudgeable terms like "engaging" without an operational definition).
- Story must be engaging.
- Characters exhibit agency (pre-planned agency acceptable).
- Only larger choices prompt player input; the rest is narrated.
- Choices have consequences.
- Player cannot see the whole story at once; branches entered via choices/checks.
- All branches engaging, each in a different way.
- Generation includes a director/playwright-style review/polish pass before the script is presented.

## Open Questions / Gaps
- **Roll model:** design deferred to next version. Prototype uses a hardcoded placeholder rule (explicitly non-final); the free-form-Rules vs deterministic-resolver contradiction is resolved with it.
- **Open-exit narrative coherence:** any available scene must read sensibly after any open exit; this is the main risk of the pool model and the first thing demo runs should stress. No validation mechanism defined yet beyond the judged pass.
- **Beat content fields:** proposal under review (id, type, intent, effects, extension annotation, type-specific routing); not committed.
- **JSON schema:** draft exists as a separate document; not committed.
- **Quality targets as judgeable properties:** current targets are not yet rewritten as objectively detectable properties (mechanism decided, rewrite pending).
- **Setting anchors:** exact structured shape undefined.
- **Premise / goal:** draft format exists in the schema draft document ([D8]); not committed.
- **Narration engine details:** deferred.

## Decisions Log
- Two subsystems: offline generation (internals only, no prose) and online runtime/narration.
- State is a fixed set of finite-domain variables (flag / bounded counter / enum); sets as flag groups; declared at generation and fixed; effects clamped to domain; guards are boolean expressions; state space = product of domains (bounded, enumerable).
- Narration never alters outcomes, state, or check results.
- Inputs are one object combining structured + free-form data.
- Character fields: name (structured), background/appearance (free-form); no stats; traits-as-tags dropped.
- Rules are free-form (tone, content, mechanics, check mechanics); no deterministic trait model.
- Checks are generator output, resolved deterministically at runtime from roll + difficulty + state-conditional modifiers.
- Script is structured data (JSON), hybrid storylet + branching.
- Story is one beat graph; a scene is an entry-to-exit subgraph.
- In-scene beats may reroute/reconverge; scene selection occurs only at exit nodes (committed scenes).
- In-scene beats/options may be quality-gated (additive, state-unlocked content), but every scene must retain a non-gated entry-to-exit path.
- Exit edges unify forced and gated via guard + type + priority.
- Extension points allow an outcome-neutral micro-loop (deeper vs proceed), preplanned by tension.
- Runtime extension is outcome-neutral only; anything affecting future outcomes is generated offline.
- Softlock checking is a generation-time deterministic reachability walk requiring marked endings and bounded state.
- Generation is a staged pipeline (outline → per-scene mini-graphs → checks/effects), each stage validated before the next; no global generate-then-repair loop.
- Softlock walk explores reachable states forward from the initial state (not full domain-product enumeration).
- LLM-as-judge harness is designed alongside quality targets; every target must be expressed as an objectively detectable property.
- Offline generation of unplayed branches is accepted cost (prose is not generated offline, which keeps that cost bounded).
- Structural framework is a minimal uniform set of primitives; narrative layering happens in generator usage and judged passes, not in new structural types.
- A check is a beat type with success/failure edges.
- Effects attach to beats only.
- Exit edges are { target_scene, guard, priority }; "forced" = guard always true; highest eligible priority wins; equal priorities at one exit node are a generation-time error.
- Exactly one input character carries a protagonist flag; kept after tag removal (POV anchor).
- Namespace is flat; per-character state via naming convention.
- Beat types: plain, check, choice, ending. A choice is a beat with labeled (optionally guarded) outgoing edges; an ending is a terminal beat with an ending label.
- Tags dropped entirely. Check modifiers are state-var conditions with values; earlier beats' effects modify later checks.
- Scenes carry prerequisites; available = prerequisites match state + visitedness.
- Scenes are once-only by default; `repeatable` flag opts out.
- Exits are directed (explicit edges) or open (runtime pool query); generator decides which.
- At open exits: forced scene priority preempts; otherwise player chooses among available scenes. Equal forced priorities = generation-time error.
- Visitedness is built-in runtime tracking per scene and beat (not state vars), exposed as a `visited(id)` condition; monotone false→true.
- Scenes carry an `intent` field (same semantics as beat intent). Open exits present available scenes' intents as ordinary choice options; scene selection is never exposed to the player.
- Roll model deferred to next version; prototype hardcodes a placeholder rule.
- Protagonist flag kept.
