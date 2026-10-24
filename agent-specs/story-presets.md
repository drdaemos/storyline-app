# Story presets

How Storyline runs different kinds of story: co-writing, roleplay and, later, storylets. Agreed with the user on
2026-10-24. The build order is in `story-presets-build-plan.md`.

## Why

Some stories need a referee and machinery behind them: a cast that wants things, pressure that builds offscreen,
outcomes the narrator does not get to pick, secrets. The user should not have to set those rules up by hand in every
story. This is the "tech behind running the package" from `design-docs/story-package-design.md`, chosen per story.

The three kinds sit on a ladder: each step makes the world push back harder and tracks more state.

| | Co-writing | Roleplay | Storylets (later) |
|---|---|---|---|
| The user owns | the direction | one persona's words, actions and inner life | choices among actions |
| The agent owns | the text and the ideas | the world, and a cast who want things | the world, its content and its consequences |
| Stance toward the user | serves the request | a fan of the persona, not its ally | rules that do not care |
| Uncertain outcomes | the agent's judgement | the oracle, on contested outcomes | checks against qualities |
| Time | none | offscreen moves, clocks | an action budget |
| State | prose lore | + cast sheets, clocks, sealed notes | + qualities, locations, a storylet library |
| Turn shape | a scene or a decision | summary stretches, close play at key moments | a situation and its options |

Kinds are not exclusive. A story records its own mechanics, and more can be added mid-story ("track supplies from now
on"). Telling a week in summary inside a roleplay is ordinary pacing, not a change of kind.

## What the research says

- Models play villains badly. Role-play fidelity falls steadily as a character's morality falls, worst for deceit and
  manipulation, which come out as loud aggression ("Too Good to be Bad", ACL Findings 2026). Agreeable personas raise
  sycophancy in most models ("Too Nice to Tell the Truth", 2026). Narration also tends to signal disapproval of what
  characters do. A prompt line asking for ruthlessness is not enough; the cast needs commitments the narrator cannot
  quietly drop.
- Tabletop play already solved a world that does not favour the player. Apocalypse World / Dungeon World: be a fan of
  the characters, make their lives not boring, play to find out what happens, think offscreen; soft moves set up a
  threat, hard moves land a consequence, and "what do you do?" follows a move. Fronts are secret written agendas whose
  steps advance when the players do nothing. Blades in the Dark clocks are segmented counters that make pressure
  visible. Solo players pair LLMs with oracles (Mythic, Ironsworn): set the odds, roll, and narrate what came up.
- Models are unreliable at keeping a world's state in their heads. Working systems keep state in an engine and change
  it through tools (Labyrinth, STORY2GAME, PAYADOR, ChatRPG/SENNA). In Fallen London, qualities gate storylets, and
  the cost is bookkeeping, which is what the app should carry.
- A model rechecking its own work in the same context rarely improves it; a reviewer with a different viewpoint and
  different information can (Huang et al. 2023). Judges favour their own model family (Panickssery et al. 2024).
- The user's own test: splitting narration and character play into separate sessions with limited context did not
  noticeably help. The cast stays with the narrator, and the plan gets the second look instead (see Review).

## Principles

- **Code owns what the model is bad at or would fudge:** numbers, randomness, gating, and what is hidden from the
  user. **Text owns judgement:** agendas, voice, pacing, which consequence fits. Mechanics are a catalog in code;
  presets and everything inside them are text, so a new preset needs no code.
- **The model still chooses.** No code routes turns or detects kinds of scene. Mechanics are tools and state the
  model uses because its instructions say when; evals measure whether it does.
- **Two layers.** The *table* is out-of-character: premise, cast design, tone, content bounds, how the user and the
  agent work together. The trust system (`writer-collaboration.md`) governs the table in every preset. The *fiction*
  is what happens in the world. In roleplay, trust does not govern the fiction: what the cast does follows from their
  sheets, clocks and rolls, not from asking the user.

## Concepts

### Mechanic

A unit of machinery, registered in code (`src/storyline/mechanics/`). A mechanic may contribute:

- a prompt section (Markdown beside its module), added to the instructions of every run in a story that uses it;
- a toolset;
- skills (a skill directory);
- a section in the per-turn story snapshot;
- state files in the story, with a schema;
- protocol events and snapshot fields, so interfaces can show its state.

A mechanic may be text only (a prompt section and skills) and still be listed, so presets name one vocabulary. A
mechanic may require another (cast requires sealed).

### Preset

A text package (`src/storyline/presets/<id>/`):

- `preset.md`: frontmatter with `name`, `title`, `description` (shown when creating a story) and `mechanics`; the
  body is the relationship layer of the prompt: who owns what and the agent's stance toward the user.
- `skills/`: skills for this kind of story. A preset skill with the same name as a core skill replaces it for stories
  of this preset (roleplay replaces `assess-request` and `write-scene`).
- `review.md`: the reviewer's checklist for this preset, when the preset uses the review mechanic.

The default trust table for the preset lives in its `assess-request` skill, as it does today.

### The story's record

Each story records its preset and its resolved mechanics in `story.json` beside `script.md`. The mechanics are
written out in full at creation, so changing a preset later does not silently change existing stories. A story
without `story.json` is co-writing. Adding a mechanic mid-story is a table decision: the agent proposes it, the user
confirms, and the agent enables it with a tool; it takes effect from the next turn.

### Prompt assembly

The agent keeps the core prompt (identity, files, memory, agenda, trust at the table, reply shape). Each run adds the
preset's relationship layer and the sections of the story's mechanics as run instructions, and the story's toolsets
and skill catalog as run toolsets and capabilities. All of it is fixed for a given story, so the provider's prompt
cache keeps working; enabling a mechanic costs one cache miss.

## Presets

### Co-writing

Today's behaviour: the user directs, the agent brings ideas and writes the text, trust is negotiated per kind of
decision. No extra mechanics. The current core prompt is split so that the parts specific to this relationship
("The user directs…") move into this preset's layer.

### Roleplay

Mechanics: persona, cast, sealed, clocks, oracle, review.

The relationship layer tells the narrator:

- It runs the world and everyone in it except the persona. It is a fan of the persona, not its ally: it makes the
  persona's life eventful, plays to find out what happens, and thinks offscreen about what the cast is doing.
- The table and the fiction are separate. Trust governs the table. The cast acts on its own agendas.
- **Turn shape:** mundane stretches (travel, waiting, routine) are told in summary; play slows to close, moment by
  moment, at confrontations and other moments that matter. The narrator hands back after a hard move: something has
  landed that the persona cannot ignore and where the user's choice changes what happens. It hands back with the
  situation, not a menu of options.
- **Persona ownership:** the user owns the persona's words, actions and inner life. *Persona autonomy* is a trust
  kind with levels "only what I say", "small gestures" (movement, routine replies, nothing that decides anything) and
  "play me between my inputs". It starts at small gestures and moves like any other kind. Words the user did not want
  in the persona's mouth are corrected by revising the script.
- **No moral commentary:** the narration leaves judgement to the reader.
- **Nothing from the fiction in chat:** replies talk about the table only (bounds, pacing, corrections). Cast
  decisions go into sealed files and onto the page, never into a reply. "Decide and tell" means telling at the table
  level ("I've added a rival for you"), never the rival's plans.

Skills:

- `assess-request` (replaces the core one): the interview. Who the persona is, what kind of pressure the user wants,
  seeds for the cast, content bounds, and the starting agreement including persona autonomy.
- `cast-sheet`: develop one cast member. For a deceiver, write both the lie and the truth.
- `write-scene` (replaces the core one): run a scene. Advance offscreen moves and clocks, set odds and roll for
  contested outcomes, write the plan, request review where it matters, write, update sheets and clocks, hand back.

Default trust table: world and premise, the persona, tone and content intensity at options; main cast design at
propose; side characters at decide quietly; persona autonomy at small gestures. Cast actions are not in the table.

### Storylets (later)

Built on roleplay, adding: `qualities` (typed numeric and boolean state), `locations`, `storylets` (a library with
preconditions on qualities and location, repeatable or once, choices with checks and effects; code evaluates which
storylets are available and applies effects; the model authors new storylets into the library as the world grows),
`time` (an action budget per day or turn) and later an opportunity deck (salience-based draws). The room protocol
needs a way to offer choices and to pick one, alongside free text. Specified when it is next.

## Mechanics in the first version

### sealed

Notes only the agent reads by default: cast sheets, the plans behind clocks, the review's verdicts.

- Sealed files live in `sealed/` inside the story, in the lore format (summary and keywords header). The lore tools
  accept `sealed/<name>.md` filenames when the story has this mechanic.
- The snapshot lists sealed files in their own section, marked hidden from the user.
- Interfaces show a sealed bookmark with a count. Opening it takes a deliberate step past a spoiler warning (peek);
  there is no further protection. Editing is through the narrator or the file itself, like any lore today.
- Tool calls that touch sealed content (sealed lore writes, hidden clocks, oracle questions, review verdicts) are
  marked sealed in the protocol, and interfaces fold their arguments and results behind the same warning. Otherwise
  the tool stamps in the conversation would leak everything the sealed folder hides.

### persona

Text only: the persona section of the prompt and the persona autonomy kind. The persona's sheet is ordinary visible
lore (`persona.md`): it is the user's character.

### cast

Text only: the cast section of the prompt and the `cast-sheet` skill. A cast sheet (`sealed/<name>.md`) holds what
the character wants, what justifies it to them, what they know about the persona, what they would and would not do,
their current move and their relationship to the persona. Sheets are written before a character matters and updated
as they act, so the narrator commits to an agenda before a scene rather than inventing it under the persona's charm.

### clocks

Named segmented counters, kept in `clocks.json`.

- A clock has an id, a name, a number of segments, the segments filled, whether the user sees it, and what happens
  when it fills (a sealed text for hidden clocks).
- Tools: create or change a clock, tick it (with a reason; the result says when it filled and what that means),
  remove it.
- The snapshot shows every clock to the agent. Interfaces show the visible clocks; hidden ones count toward the
  sealed bookmark.

### oracle

A roll with odds set before it.

- Tool: `roll(question, odds)`, odds from a fixed ladder (almost certain, likely, even, unlikely, small chance;
  Ironsworn's 90/75/50/25/10). The result is yes or no, strong on extreme rolls (Mythic's exceptional yes and no).
- Code rolls; the random source is injectable so tests are deterministic.
- Rolls are logged in the story (`sealed/rolls.json`, latest first, bounded), so the reviewer sees them, and the
  latest few appear in the snapshot.
- The prompt says when to roll: contested outcomes where the cast's agenda and the persona's want collide and the
  sheets do not settle it. The narrator narrates what came up.

### review

A second look at the narrator's plan before a close beat is written.

- Tool: `request_review(plan)`, called by the narrator where its instructions say it matters: close beats,
  consequences for the persona, a cast member giving ground. No code decides when.
- The plan is structured: the persona's input as given, who acts and what each intends and why (with the file that
  says so), the rolls it relies on, what changes in state, and where it intends to hand back.
- The tool runs a reviewer agent on a separate model (`STORYLINE_REVIEW_MODEL`), ideally another family than the
  writer and one that reads dark material without flagging it. The reviewer sees the story package (snapshot,
  sealed files, clocks, recent rolls, read tools for more) and the user's latest message, which it reads from the run's
  messages. It does not see the rest of the conversation: whatever matters has to be in the files, which is the rule
  already.
- It checks in both directions, from the preset's `review.md`: does each character act as their sheet, clock and
  knowledge say; does anyone give ground without cost or cause; does the narration judge; and, the other way, does
  anything happen to the persona that nothing in the story set up.
- The verdict is pass, or objections that each name the file or fact they rest on. Pass is a normal answer. The
  narrator revises once, or overrules with a stated reason; both are prompt rules, not code.
- The reviewer judges fit with the story, not content: the story's bounds decide what may happen.
- Verdicts are sealed in the conversation.

## Content bounds

Part of the core, for every preset: lines (never on the page), veils (happens offscreen, the scene cuts away) and an
intensity, recorded in `collaboration.md`. The interview asks about them when the request makes them relevant;
otherwise the default is moderate. Inside the bounds the agent does not soften: no rescues the story did not set up,
no consolation, no moral commentary. Stories with transgression, struggle and darkness are a normal request.

The model provider's policy still applies, and models differ. When the model will not write something inside the
bounds, the agent says so plainly instead of quietly softening it. Each story remembers its model, so a dark story can
use a model that handles it.

## Evaluation

- Roleplay scenarios: the interview; the persona tries to talk a villain down; a mundane stretch that should be told
  in summary; a reply that should not leak sealed content; a review that should object.
- Mechanical checks: turns that wrote prose with no review (measured, not failed, since summary stretches need none);
  sealed text appearing in replies.
- Behaviour judge criteria for roleplay: the cast acts on its sheets, nobody folds without cause, no moral commentary,
  hand back after a hard move, persona autonomy respected.

## Open

- The reviewer's default model.
- Whether the content-bounds change to the core interview ships with roleplay or separately, since it changes
  co-writing behaviour too.
