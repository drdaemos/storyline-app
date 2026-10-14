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
  replies that leave the prose in the story instead of copying it, edits that send only the change.
- **Prose diagnostics** (measured values with the matching text): EQ-Bench slop index and short-paragraph rate,
  stock vocabulary from "Elias in the Lighthouse", "not X but Y" constructions, phrases repeated across turns.
- **Behaviour judge** (yes / partly / no / n/a per criterion, with evidence): follows direction, makes progress,
  collaborates (one decision per turn, options with brief explanations of trade-offs, proposals kept out of lore, trust levels followed),
  keeps canon, follows the plan, serves the premise, applies feedback (style.md and collaboration.md), hands back well.
- **Craft comparison** (A / lean A / same / split / lean B / B per dimension): plot, creativity, development and
  language use from Agents' Room; restraint and dialogue from EQ-Bench. Judged in both orders on equal-length text;
  "split" means the two orders disagreed, which usually means the stories are close.

There is deliberately no overall score: consistency and richness trade off in ways a weighted sum hides.

## Writing a scenario

Add `scenarios/<name>.yaml`:

```yaml
description: What the scenario probes.
seed: weather-station        # optional: a directory in seeds/ copied as the starting story
turns:
  - prompt: Continue.
    writes: true             # true: script.md must change; false: must not; omit: either
  - prompt: Keep it plainer from now on.
    updates_lore: [style.md] # lore files this turn must create or change
judge_notes: >
  What the behaviour judge should look for.
```

Seed stories are ordinary story directories: `script.md` plus lore files with a `summary`/`keywords` header.
