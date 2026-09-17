# Adversarial gauntlet

This is a scored end-to-end evaluation, not a showcase fixture. Each trial builds a
real Git repository and agent transcript, runs the production analysis pipeline, and
checks both required detections and forbidden false positives.

The five advanced cases cover:

1. a corrected multi-turn request, renamed files, and a simultaneous human edit;
2. same-named files in different monorepo packages and an undisclosed lockfile;
3. staged plus untracked changes, a leaked token, a migration, weakened assertions,
   a failed destructive command, and a supported test claim;
4. noisy/malformed Codex JSONL, Windows-style tool paths, and a false test claim;
5. vague intent where Overscope must remain uncertain and avoid blaming human work.

Run it into a new directory:

```bash
uv run python evaluation/gauntlet.py \
  --output /Users/sandeep/Documents/claude/overscope-trials-advanced
```

The command exits non-zero on any missed expectation and leaves every trial repository
available for manual `overscope --session ...` inspection.
