# Story presets: build plan

How `story-presets.md` gets built. Each phase ends green on the quality gates in `AGENTS.md` and is reviewed before
the next starts. Implementation is delegated to Sonnet subagents with disjoint file ownership; contracts (the
`Mechanic` protocol, preset format, protocol changes) are written in the main session first. Delete this file once
the roleplay preset ships; `story-presets.md` stays.

## Phase 1: split the prompt (no behaviour change)

Goal: today's writer, assembled from a core plus a co-writing preset.

- `src/storyline/presets/co-writing/preset.md`: the co-writing relationship layer, moved out of `writer.md` (the
  opening paragraph's "The user directs…" and anything else specific to co-writing). Core skills stay where they are.
- `src/storyline/presets/__init__.py`: `Preset` (id, title, description, mechanic ids, layer text, skills directory,
  review checklist) and a loader for the bundled presets; package data in `pyproject.toml` like the skills.
- `writing_session.py`: each run passes the story's preset layer as run `instructions`, and the story's skill
  catalog as a run capability, instead of the agent carrying `Skills` itself. To verify first: how two skill
  libraries with an overriding name combine in one `Skills` capability (the harness rejects duplicate names within
  one instance, so the catalog is resolved by name before it is built).
- `story.json` read on the `Story` boundary (`read_story_type` / `write_story_type`); missing means co-writing.
- Tests: the assembled instructions for a co-writing story contain everything the core tests check today; a story
  without `story.json` is co-writing; prompt version covers core plus layer.
- Before/after: the user runs `storyline eval run` on main and on the branch and `eval compare`s them (real LLM
  calls; not run by agents).

## Phase 2: presets and mechanics infrastructure

Goal: a story can be created as any bundled preset, mechanics plug in, and sealed files work end to end. Ships with
a stub roleplay preset (layer text only) so the path is exercised.

Contracts (main session):

- `src/storyline/mechanics/__init__.py`: the `Mechanic` protocol (id, requires, prompt section, toolset or none,
  skills directory or none, `async snapshot_section(story) -> list[str]`, which tool names change which state) and
  the registry.
- Protocol (`room/protocol.py`): `CREATE_STORY` takes a preset id; `LIST_PRESETS` returns id, title, description;
  `RoomSnapshot.preset`; `LoreFile.sealed`; `ToolCallStarted`, `ToolCallFinished` and `ToolCallEntry` carry `sealed`.
  Regenerate `protocol.json`.

Backend (one agent):

- `workspace/`: `sealed/` files through the lore operations (path rule widened to `sealed/<name>.md` when allowed),
  `LoreFile.sealed`, `story.json` with preset and resolved mechanics written at creation, `StoryLibrary.create(name,
  preset)`.
- `agent/`: per-run assembly from the story's record (layer, mechanic sections, toolsets, skills); story snapshot gets
  a sealed index and each mechanic's section; an `enable_mechanic` tool.
- `room/`: sealed marking on tool events (decided by the tool and its arguments, e.g. a lore write under `sealed/`),
  create with preset, list presets.
- `web/`: routes for the new operation and fields.
- `mechanics/sealed.py` as the first mechanic.

Interfaces (one agent each, after the backend lands):

- TUI: `/new <name>` takes a preset (`/new <name> --as roleplay`, tab completion), `/presets`, sealed bookmark in
  `/lore` with a confirm step, sealed tool stamps folded.
- Frontend: preset picker in the shelf's new-story form, sealed bookmark with a spoiler warning, folded sealed tool
  stamps, parity test updates. Theme tokens only.

Tests: create with each preset; sealed files listed as sealed and hidden from the visible lore index; sealed tool
calls marked in events and the transcript; snapshot sections from mechanics; an unknown preset is refused; parity
tests for both interfaces.

## Phase 3: roleplay

Goal: the roleplay preset as specified.

- Preset text: `presets/roleplay/preset.md` (relationship layer), `skills/assess-request`, `skills/cast-sheet`,
  `skills/write-scene`, `review.md`.
- Mechanics, one agent each where files do not overlap:
  - `persona` and `cast`: prompt sections only.
  - `clocks`: `clocks.json` on the `Story` boundary, tools, snapshot section, `ClocksChanged` event and
    `RoomSnapshot.clocks` (visible only), clocks panel in the TUI and the web UI.
  - `oracle`: `roll` tool with an injectable random source, the odds ladder, the bounded roll log, snapshot section.
  - `review`: `request_review` tool, the plan model, the reviewer agent (its own short prompt plus the preset
    checklist, read-only story tools, structured verdict), `STORYLINE_REVIEW_MODEL` in `.env.default` and settings.
- Core: content bounds (lines, veils, intensity) in the core prompt and the core `assess-request`. Held behind the
  open question in the spec: ship with roleplay or separately.
- Tests (FunctionModel fakes throughout): clock ticking and filling; rolls distributed by the odds with a fixed
  source; the review tool passes the latest user message and the package to the reviewer and returns its verdict
  sealed; the roleplay preset assembles with all six mechanics; prompt structure tests for the roleplay layer and
  skills (behaviour and structure, not phrasing).

## Phase 4: roleplay evals

- A roleplay seed story: persona, two cast sheets (one deceiver), a hidden clock, a few rolls, an agreed opening.
- Scenarios: the interview from a bare request; the persona tries to talk the villain down; a mundane stretch; a
  table question whose answer must not leak sealed content; a plan that should draw an objection.
- `Scenario` learns the preset (from the seed's `story.json`, or a field for seedless scenarios).
- Checks: prose turns without a review (measured); sealed text in replies.
- Judge criteria for roleplay, applied when the scenario's preset is roleplay.
- The user runs them and judges the first results by hand before any prompt tuning.

## After

Storylets get their own spec once roleplay has been played for a while.
