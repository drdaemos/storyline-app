# VN script self-improvement loop

Run the generate → review → regenerate loop for a visual-novel script until the judge says to stop.

**Input:** `$ARGUMENTS` — path to a VNInput JSON file (characters, setting, rules, premise). Optional overrides anywhere in the arguments: `target=<score>` (default 4.0), `max=<iterations>` (default 4), `processor=<type>` (default claude-sonnet).

## Setup

1. Derive a run name from the input filename (slug), e.g. `locked-granary`.
2. Create a working directory `runs/<run-name>/` for scripts and evaluations. Use `--user-id loop-<run-name>` on every command so DB rows from this loop are identifiable.
3. Maintain a small state table across iterations: iteration number, script path, evaluation JSON path, overall score, verdict, recommendation. Track which iteration is the **best so far** (highest overall score).

## Iteration 1

```bash
uv run main.py vn-generate <input-file> --user-id loop-<run-name> --output runs/<run-name>/iter-1.script.json
uv run main.py vn-review runs/<run-name>/iter-1.script.json --input <input-file> --user-id loop-<run-name> --output-dir runs/<run-name>/evals --target-score <target>
```

No `--baseline` on the first review. Note the evaluation files it reports: `<stem>.json` (baseline for next round), `<stem>.md` (human report), `<stem>.guidance.txt` (feed to the next generate).

## Iterations 2..max

```bash
uv run main.py vn-generate <input-file> --guidance <previous .guidance.txt> --user-id loop-<run-name> --output runs/<run-name>/iter-N.script.json
uv run main.py vn-review runs/<run-name>/iter-N.script.json --input <input-file> --user-id loop-<run-name> --output-dir runs/<run-name>/evals --baseline <previous evaluation .json> --target-score <target>
```

Always pass `--guidance` from the **best-so-far** iteration's review (not blindly the latest), and `--baseline` from the **previous** iteration's evaluation JSON so progress is measured step over step.

## Acting on the review

Read the recommendation from the review output (also stored under `"delta"` in the evaluation JSON):

- **`stop_target_reached`** — stop. The current iteration is the deliverable.
- **`stop_plateaued`** — stop. Scores moved less than the epsilon; further iterations will flip-flop, which is exactly what the numeric rule exists to prevent. Deliver the best-so-far iteration.
- **`continue`** — proceed to the next iteration with this review's guidance file.
- **`rollback`** — this iteration regressed. Discard it as a guidance source: next iteration reuses the best-so-far iteration's guidance file and baseline. Two rollbacks in a row → stop and deliver the best-so-far.

Hard caps regardless of recommendation: stop after `max` iterations.

## Failure handling

- If `vn-generate` fails, it prints `--resume <job-id>` and keeps a checkpoint. Resume once with `uv run main.py vn-generate --resume <job-id>`; if it fails again, stop and report the error.
- Generation can take several minutes per script — run it in the background and wait; do not kill it for being slow.
- If a review fails validation gates repeatedly (VNGenerationError), retry once; then stop and report.

## Final report

End with a table of all iterations (overall score, verdict, recommendation), the per-dimension score trajectory for any dimension that moved, the path to the best script JSON and its markdown review, and one paragraph summarizing what the judge's guidance changed between the first and best iteration.
