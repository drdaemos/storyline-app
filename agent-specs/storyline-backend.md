# Storyline backend architecture

Backend is composed of Python packages, each serving a different responsibility.

src/
    storyline/
        agent/              - writer agent, its core prompt and skills, the per-run assembly of a story's preset, per-turn story snapshot, model resolution, and WritingSession (one story's conversation: history repair, remembered model, running turns)
        mechanics/          - the Mechanic contract and the mechanics (`sealed`, `persona`, `cast`, `clocks`, `oracle`, `review`): prompt section, toolset, skills and snapshot section a story can run with, chosen per story
        presets/            - bundled story presets (<id>/preset.md plus optional skills/): the relationship layer of the prompt for each kind of story
        workspace/          - stories in a workspace (one package per subdirectory), story selection, script and lore operations
        evals/              - scenario evaluations of the writer: runner, mechanical checks, behaviour and craft judges
        room/               - the interface-agnostic layer: the room protocol (operations, events, snapshot) and StoryRoom, which runs one story's conversation for any interface
        tui/                - terminal interface; maps commands and keys to room operations and draws room events
        web/                - hosted web API: the room protocol over HTTP and server-sent events, Clerk auth, one workspace per user
        registry.py         - `MECHANICS`, the registry of every mechanic, composed above `mechanics/` and `agent/` (the review mechanic is given the agent layer's reviewer)
        observability.py    - Logfire tracing of agent runs
        cli.py              - main application entrypoint with CLI options

evals/                      - evaluation scenarios (scenarios/*.yaml) and the seed stories they start from (seeds/)
eval-runs/                  - output of `storyline eval` (git-ignored); each run directory is also a workspace

frontend/                   - Vue web interface (shelf, writing room); the look lives only in frontend/src/theme/

## Interface parity

- `room/protocol.py` is the single definition of what a person can do (`Operation`) and what an interface is told
  (`RoomEvent`, `RoomSnapshot`). `StoryRoom` owns the steering queue, follow-up turns and the mapping from agent
  events to room events; interfaces hold no conversation logic.
- A new capability is added to the protocol first. Each interface has a parity test that then fails until it offers
  the operation and renders the event: `tests/test_tui_parity.py`, `tests/test_web_parity.py` and
  `frontend/src/protocol/parity.test.ts`.
- The frontend is checked against `frontend/src/protocol/protocol.json`; regenerate it with
  `uv run python -m storyline.room.export` after changing the protocol (`tests/test_room_protocol.py` fails when it
  is out of date).
- A room keeps running a turn with no interface attached. A web client that connects to
  `GET /api/stories/{story}/events` first receives a snapshot, then events; reconnecting replaces its state with a
  new snapshot. The route for each operation is listed in `web/operations.py`.
- With `AUTH_ENABLED` off the web serves the ordinary local workspace as one user; with it on, each Clerk user gets
  `STORYLINE_DATA_DIR/users/<id>`.

## Writer prompt conventions

- The writer prompt is a small core (`agent/prompts/writer.md`: identity, files, the turn loop, trust, reply shape) plus
  skills (`agent/skills/<name>/SKILL.md`: assess-request, research, develop-element, outline, write-scene, revise) that
  the model loads through `load_capability` via the harness `Skills` capability. A skill's frontmatter `name` equals its
  directory and its `description` says when to load it. `prompt_version()` hashes an instruction text and
  `writer_prompt_version()` hashes the core prompt together with a preset's layer, so runs and traces can name the
  variant. Skill files ship as package data.
- How the writer and the user share the work depends on the story's preset (`presets/<id>/preset.md`: frontmatter id,
  title, description and mechanics, then the relationship layer as Markdown; default `co-writing`). The agent itself
  carries only the core prompt. `agent/assembly.py` builds a `RunAssembly` per story, once, when the `WritingSession`
  opens: the preset's layer, passed as run `instructions` after the core, and the skill catalog, passed as run
  `capabilities`: the core `Skills` library minus any skill the preset overrides by name, plus the preset's own
  `skills/` library. Every turn passes both to the agent run.
- A story's kind is recorded in `story.json` beside `script.md` (`StorySetup`: preset id and mechanics, read and
  written through `Story.read_setup` / `write_setup`). A story without one is a default co-writing story; an unreadable
  file or an unknown preset raises `StorySetupError` when the story's room opens: the terminal UI reports it and stays
  on the story list, and the web answers 422. Presets are listed with `BUNDLED_PRESETS.summaries()` (web:
  `GET /api/presets`, `LIST_PRESETS`). A story is created as a preset with
  `StoryLibrary.create(name=..., setup=setup_for(BUNDLED_PRESETS.get(id)))`, which writes `story.json` with the
  preset's mechanics resolved in full; an unknown id is refused before anything is created (web: 400).
- Mechanics (`mechanics/`, one `Mechanic` subclass per unit, registered in `registry.py` `build_mechanics`) add to a story's runs:
  `assemble(preset, mechanics)` appends each mechanic's prompt section after the preset layer, adds its skills as
  further `Skills` capabilities and its toolset as run `toolsets`; the snapshot lists the mechanics in use and the
  others available, then each mechanic's `snapshot_section` lines before the agenda. The setup is re-read when every
  turn starts and re-assembled only if it changed (`WritingSession.refresh_setup`), so a mechanic enabled during one
  turn (the `enable_mechanic` tool, after the user agrees) applies from the next. A setup that has become unusable
  fails that turn only. A mechanic's `toolset` is a class attribute when its tools need nothing from an instance, or
  built per instance (`oracle`, `review`) so a test can inject the die or the reviewer.
- The registry (`storyline.registry.MECHANICS`) sits above `mechanics/` and `agent/`: it gives `ReviewMechanic` a
  `StoryReviewer` (`agent/reviewer.py`) bound to the same registry, so `mechanics/` never imports `agent/`. Everything
  below it takes the registry as an argument (`resolve_mechanics`, `setup_for`, `turn_prompt` / `story_snapshot`,
  `WritingSession.open`); `StoryRoom.open`, the terminal UI, the web and the evals pass `MECHANICS`. A session adds
  `enable_mechanic` to every turn as its own toolset (`mechanic_toolset(registry)` in `agent/writer_tools.py`), so the
  tool enables mechanics from the session's registry. Tests build a registry with another reviewer model resolver
  through `build_mechanics(review_model_resolver=...)`.
- The `roleplay` preset (`presets/roleplay/`: mechanics persona, cast, sealed, clocks, oracle, review; its own
  `assess-request` and `write-scene` skills replace the core ones; `review.md` is its reviewer checklist, loaded as
  `Preset.review_checklist`, None for a preset without one). The mechanics:
  - `persona` and `cast` are prompt text; `cast` requires `sealed` and brings the `cast-sheet` skill
    (`mechanics/cast/skills/`).
  - `clocks` (requires `sealed`): `clocks.json` beside `script.md` (`Clock`: id, name, segments 2-12, filled, visible,
    when_full; `Story.read_clocks` / `change_clocks`, unreadable file -> `ClockError`). Tools `set_clock`,
    `tick_clock` (negative rolls back; result says when it filled and repeats `when_full`) and `remove_clock`; each
    result lists every clock with its id. The snapshot lists every clock for the writer. Calls to all three are sealed.
  - `oracle`: `roll(question, odds)` with odds almost certain 90, likely 75, even 50, unlikely 25, small chance 10;
    d100 <= chance is yes, strong in the outer fifth of the deciding range. Rolls are logged newest first (latest 50)
    in `sealed/rolls.json` (`Roll`; `Story.read_rolls` / `change_rolls`, `RollLogError`); the snapshot shows the latest 5.
    The call is sealed.
  - `review` (requires `sealed`): `request_review(plan: BeatPlan)` runs a separate read-only reviewer agent
    (`agent/reviewer.py`; instructions `mechanics/reviewer.md` + the preset's checklist; tools list_lore, read_lore,
    read_script; output `Verdict`) on the story snapshot, the user's latest message and the plan, and returns "Pass."
    or the objections. Its model is `STORYLINE_REVIEW_MODEL` (read per call, validated like `STORYLINE_MODEL`; an
    invalid name fails the tool) or else the narrator's model; its usage counts in the turn. The call is sealed.
- Clocks in the room protocol: after a successful clock tool the room re-reads `clocks.json` and, only when what the
  user sees changed, emits `ClocksChanged(clocks, hidden)` - the visible clocks as `ClockView` (id, name, segments,
  filled) and the count of hidden ones. `RoomSnapshot.clocks` / `hidden_clocks` carry the same. An unreadable
  `clocks.json` gives a `Notice` (error) and empty clocks.
- Sealed files: lore files in `sealed/` (`sealed/<name>.md`, exactly one level), through the same lore tools and
  `Story` methods; `LoreFile.sealed` marks them, `list_lore` returns the story's own lore first. The workspace always
  supports them; the `sealed` mechanic is what tells the writer to use them. Tool calls that touch hidden content are
  marked `sealed` on `ToolCallEntry`, `ToolCallStarted` and `ToolCallFinished` (`agent/sealing.py`
  `tool_call_is_sealed`: a core lore tool naming `sealed/...`, or a call one of the story's mechanics `seals`), live
  and in the restored transcript, so interfaces fold them. Lore tools on sealed files still emit `StoryFilesChanged`.
- `plan.md` (direction), `style.md` (lasting prose preferences) and `collaboration.md` (working agreement, trust table,
  what is learned about the user) are lore files with fixed roles. Their bodies travel in every turn's story snapshot
  together with the lore index, the agenda and the end of the story. The agenda lives in `agenda.json` and is edited
  with `set_agenda` / `update_agenda_item`.
- Model output per response is capped explicitly (`WRITER_MAX_OUTPUT_TOKENS`) so large tool calls are not truncated.
- Collaboration design: `agent-specs/writer-collaboration.md`.

## Evaluations

- `storyline eval run [SCENARIO...]` plays scenarios against the writer, then applies habit checks (assertions), prose
  diagnostics (EQ-Bench slop index, short-paragraph rate, stock vocabulary, "not X but Y", self-repetition) and the
  behaviour judge (yes / partly / no / n/a per criterion, with evidence). `--instructions FILE` tries a prompt variant.
- Scenarios may start from a seed story or, when seedless, name a bundled `preset`; the run records the story's preset.
  Roleplay runs add a sealed-content habit check, measured mechanics use (prose turns without a review, counts of
  review, roll and clock calls) and roleplay judge criteria. The run's prompt version hashes the core instructions, all
  bundled presets and all registered mechanics' prompts. See `evals/README.md`.
- `storyline eval compare RUN_A RUN_B` judges matching cases side by side on Agents' Room / EQ-Bench craft dimensions,
  in both orders, and reports per-dimension outcomes. There is no aggregate score by design.
- Evals call real models and are not part of `pytest`; tests use `FunctionModel` fakes.
