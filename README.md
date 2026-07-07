# Is the "cheap" model actually cheap?

A small, reproducible experiment measuring what Claude models **actually cost per task** — not per token. 40 headless Claude Code sessions, 4 models, 5 kinds of work, $11.45 total.

This repo accompanies a YouTube video (link coming when it's live). Everything here is exactly what ran: the harness, the prompts, the task fixtures, and the raw, unedited result files for all 40 runs.

## ⚠️ Before you run anything: this costs real money

- Reproducing runs requires the **Claude Code CLI** with **API billing** (pay-per-token), not a subscription plan.
- The **full 40-run sweep cost $11.45**. A single run costs between **$0.01 (Haiku Q&A) and ~$0.75 (Fable coding)**.
- Every run is budget-capped (`--max-budget-usd`, $2–15 depending on task), so a runaway session can't surprise you — but the caps are ceilings, not estimates.

## The question

Sonnet 5's sticker price is $3/$15 per million tokens (input/output) vs. Opus 4.8's $5/$25 — "40% off." But you don't pay per task, you pay per token, and models don't use the same number of tokens for the same work. Commenters reported Sonnet costing ~3× Opus in real use. Is the cheap model actually cheap?

## The verdict (short version)

**The inversion did not reproduce.** Sonnet 5 was cheaper than Opus 4.8 on every tool-using task (53–67% of Opus's cost), and only hit price parity on tiny one-shot Q&A. But two real effects erode its discount:

1. **Tokenizer tax** — Sonnet 5's tokenizer counts ~30–45% more tokens than Opus for identical text.
2. **Turn multiplier** — in agentic work, 92–96% of billed tokens are the session re-reading its own growing context each turn. Cost ≈ turns × context size. A run that flails on heavy context (e.g. repeatedly screenshotting its own work) *can* genuinely invert the ranking — that's variance, not a law.

Full analysis with tables and caveats: [REPORT.md](REPORT.md).

## What's in here

```
run_one.sh            # the harness — runs one (task × model × rep) cell
prompts/              # the 5 task prompts, verbatim
fixtures/             # task inputs: buggy Python lib + tests, parser spec tests, messy CSV
results/              # raw Claude Code result JSON per run (tokens, cost, turns, timing)
results_table.tsv     # all 40 runs, parsed into one table
manifest.jsonl        # verification outcome per run (did the task actually succeed)
analyze.py            # pricing math: input + cache writes (1.25×/2×) + cache reads (0.1×) + output
turns.py              # per-turn cache growth, parsed from session transcripts
REPORT.md             # the full writeup
```

## Run one cell

```bash
./run_one.sh <mode> <model> <rep>
# e.g.
./run_one.sh coding claude-sonnet-5 1
```

Modes: `qa`, `writing`, `data`, `coding`, `coding-hard`.
Models tested: `claude-sonnet-5`, `claude-opus-4-8`, `claude-fable-5`, `claude-haiku-4-5`.

The harness copies a fresh fixture into `runs/`, invokes `claude -p` headless with pinned settings (`--effort high --safe-mode --permission-mode acceptEdits`), writes the result JSON to `results/`, and verifies the task actually succeeded (tests pass / files produced).

Then price it:

```bash
python3 analyze.py
```

## Methodology fine print

- **Price basis:** standard tier ($3/$15 Sonnet, $5/$25 Opus, $10/$50 Fable, $1/$5 Haiku per MTok). Sonnet's intro rate ($2/$10 through 2026-08-31) would lower its numbers ~33%; standard rates used everywhere for fairness. Cache reads billed at 0.1× input, cache writes at 1.25× (5-min) / 2× (1-hour).
- **Controls:** identical prompt and fixture per mode; fresh workspace per run; one session per (model × task); same effort setting everywhere; `--safe-mode` so no local config contaminates context; all runs back-to-back on one machine, one afternoon (2026-07-05, Claude Code v2.1.201).
- **Caveats:** tasks are small (~15–40K context, minutes not hours). The cost inversion reported in the wild happened at ~115K tokens/turn × 101 turns — a regime these tasks don't reach. All 40 runs succeeded, so this measures cost-at-equal-success. Turn counts are noisy run-to-run; reps are limited (1–3 per cell).

## License

MIT — see [LICENSE](LICENSE). Use it, rerun it, prove me wrong in the comments.
