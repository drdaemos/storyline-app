# Storyline backend architecture

Backend is composed of Python packages, each serving a different responsibility.

src/
    storyline/
        agent/              - writer agent, its prompt and skills, per-turn story snapshot, model resolution, and WritingSession (one story's conversation: history repair, remembered model, running turns)
        workspace/          - stories in a workspace (one package per subdirectory), story selection, script and lore operations
        evals/              - scenario evaluations of the writer: runner, mechanical checks, behaviour and craft judges
        tui/                - terminal interface for writing stories; presentation only, turns run through WritingSession
        web/                - web server for the Storyline UI
        observability.py    - Logfire tracing of agent runs
        cli.py              - main application entrypoint with CLI options

evals/                      - evaluation scenarios (scenarios/*.yaml) and the seed stories they start from (seeds/)
eval-runs/                  - output of `storyline eval` (git-ignored); each run directory is also a workspace

## Writer prompt conventions

- The writer prompt is a small core (`agent/prompts/writer.md`: identity, files, the turn loop, trust, reply shape) plus
  skills (`agent/skills/<name>/SKILL.md`: assess-request, research, develop-element, outline, write-scene, revise) that
  the model loads through `load_capability` via the harness `Skills` capability. A skill's frontmatter `name` equals its
  directory and its `description` says when to load it. `prompt_version()` hashes the core prompt so runs and traces can
  name the variant. Skill files ship as package data.
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
- `storyline eval compare RUN_A RUN_B` judges matching cases side by side on Agents' Room / EQ-Bench craft dimensions,
  in both orders, and reports per-dimension outcomes. There is no aggregate score by design.
- Evals call real models and are not part of `pytest`; tests use `FunctionModel` fakes.
