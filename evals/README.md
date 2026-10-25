# Writer evaluations

Scenarios for checking changes to the writer prompt (`src/storyline/agent/prompts/writer.md`) and its skills
(`src/storyline/agent/skills/`). They call real models through OpenRouter, so each run costs money; they are not part of
`pytest`.

How the collaboration feels (trust levels, one decision per turn, whether the reasoning helps) is tested by hand, not
here. Scenarios keep the prose diagnostics and the checks for single moments that still fit, such as "the first reply
writes no prose". The design is in `agent-specs/writer-collaboration.md`.

## Iterating on the prompt

1. Run the current prompt as a baseline: `uv run storyline eval run --repeat 3`
2. Copy the prompt, edit the copy, and run it: `uv run storyline eval run --repeat 3 --instructions my-variant.md`
3. Compare craft side by side: `uv run storyline eval compare eval-runs/<baseline> eval-runs/<variant>`
4. Read `summary.md` in each run directory for habit checks, prose diagnostics and the behaviour judge's evidence.
   Open any case in the terminal UI to read it whole: `uv run storyline write --workspace eval-runs/<run> --story <case>`.
5. With `LOGFIRE_TOKEN` set, every model call is traced in Logfire with prompts, tool calls and token usage.

Options: `--model` sets the writer, `--judge-model` (or `STORYLINE_JUDGE_MODEL`) the judge, `--no-judge` skips the
LLM judge. Keep the judge in a different model family from the writer; judges favour their own family's writing.

## What is measured

- **Habit checks** (pass/fail, deterministic): prose written when expected, expected lore updated, a plan kept,
  replies that leave the prose in the story instead of copying it, edits that send only the change, and replies that
  keep sealed content out of the chat (no run of six words from a sealed file as it stood after the turn).
- **Prose diagnostics** (measured values with the matching text): EQ-Bench slop index and short-paragraph rate,
  stock vocabulary from "Elias in the Lighthouse", "not X but Y" constructions, phrases repeated across turns.
- **Mechanics use** (measured values, never failed, since summary stretches need no review or roll): prose turns
  without a `request_review` call in the same turn ("n of m prose turns"), and the number of `request_review`, `roll`
  and `tick_clock` calls across the run. Co-writing runs report zeros.
- **Behaviour judge** (yes / partly / no / n/a per criterion, with evidence): follows direction, makes progress,
  collaborates (one decision per turn, options with brief explanations of trade-offs, proposals kept out of lore, trust levels followed),
  keeps canon, follows the plan, serves the premise, applies feedback (style.md and collaboration.md), hands back well.
  A run whose story is a roleplay (the preset recorded on the run) gets the roleplay criteria instead: keeps canon,
  serves the premise, cast acts on its sheets, nobody folds without cause, no moral commentary, paces scenes, hands
  back at a hard move, respects persona autonomy, keeps secrets at the table, interviews before play. The judge is
  told which files are sealed and sees each turn's tool calls (with a roll's question and odds).
- **Craft comparison** (A / lean A / same / split / lean B / B per dimension): plot, creativity, development and
  language use from Agents' Room; restraint and dialogue from EQ-Bench. Judged in both orders on equal-length text;
  "split" means the two orders disagreed, which usually means the stories are close.

There is deliberately no overall score: consistency and richness trade off in ways a weighted sum hides.

## Writing a scenario

Add `scenarios/<name>.yaml`:

```yaml
description: What the scenario probes.
seed: weather-station        # optional: a directory in seeds/ copied as the starting story
preset: roleplay             # optional, seedless scenarios only: the bundled preset the new story is created as
turns:
  - prompt: Continue.
    writes: true             # true: script.md must change; false: must not; omit: either
  - prompt: Keep it plainer from now on.
    updates_lore: [style.md] # lore files this turn must create or change
judge_notes: >
  What the behaviour judge should look for.
```

Seed stories are ordinary story directories: `script.md` plus lore files with a `summary`/`keywords` header.

A seed carries its own `story.json`, so a scenario names a `preset` only when it has no seed (naming both is an error,
as is an unknown preset id). A seedless scenario without a preset starts a co-writing story. The runner records the
story's preset on the run, which decides the judge's criteria.

## Roleplay

`seeds/quarantine-port` is a roleplay story in progress: persona Ilse Marr, cast sheets in `sealed/` (one a deceiver),
one visible and one hidden clock, an agenda, and an agreed working agreement. The scenarios `roleplay-*` use it, except
`roleplay-kickoff`, which starts a seedless roleplay story from a bare request:

- `roleplay-kickoff`: the interview; one decision per turn, no prose, no cast secrets in the reply.
- `roleplay-talk-down`: the persona tries to talk the customs captain out of the search; he should not fold without cause, and the contested outcome should be rolled.
- `roleplay-mundane`: a stretch that should be told in summary while the world moves offscreen.
- `roleplay-table-question`: a table question whose answer must not leak sealed content.
- `roleplay-deceiver`: the persona presses the deceiver; she should lie on her own terms instead of confessing because she was asked.

The prompt version in a run's name and `run.json` covers the core instructions, every bundled preset (layer, review
checklist, skills) and every registered mechanic's prompt, so a change to any of them is a new version. Read the first
roleplay results by hand before tuning prompts.
