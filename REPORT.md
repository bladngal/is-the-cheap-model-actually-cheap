# Is the "cheap" model actually cheap? — Experiment results

**Date:** 2026-07-05 · **Runtime:** Claude Code CLI v2.1.201 (headless `-p`, `--safe-mode`) · **Effort:** `high` (identical for every run) · **Machine:** Laura's Mac, all runs same afternoon · **Total spend:** $11.45 across 41 sessions

---

## TL;DR — the verdict

**The "Sonnet 5 is secretly more expensive than Opus" claim did NOT reproduce.** Across 40 runs, 5 task types, and 4 models — with every task completed successfully by every model — Sonnet 5 was cheaper than Opus 4.8 on every tool-using task, usually by *more* than its sticker discount. The one place it hit price parity with Opus was tiny one-shot Q&A.

**But the commenters aren't imagining things.** Two real effects can make Sonnet 5 more expensive than its sticker suggests, and in the right (wrong) conditions they can genuinely invert the ranking:

1. **The tokenizer tax.** Sonnet 5 uses a new tokenizer that produces ~30–45% more tokens than Opus *for identical text*. Same question, same system prompt, same answer length — more tokens on the meter. This is documented behavior, and we measured it directly.
2. **The turn multiplier.** In agentic work, ~94% of all billed tokens are the session re-reading its own growing context every turn. Cost scales with (number of turns) × (context size). A model that takes 4× the turns on a big codebase costs ~4× more, and no per-token discount survives that.

In *our* runs Sonnet 5 never spiraled — it actually took the **fewest** turns of any model on the hard coding task. But the mechanism is real, so a run where the cheaper model flails (like the one that prompted this investigation) can absolutely end up costing more than Opus. That's a variance story, not a law.

---

## What we tested

The seed observation: one real coding task where Sonnet 5 took ~101 agentic turns and ~11.6M tokens (~$6.14) while Opus 4.8 took ~24 turns and ~1.3M tokens (~$2.24). Question: is that a general property of Sonnet 5, a coding-specific quirk, or a fluke?

**Models:** Sonnet 5 ($3/$15 per MTok), Opus 4.8 ($5/$25), Fable 5 ($10/$50), Haiku 4.5 ($1/$5).

**Five task modes**, spanning the agentic-ness spectrum:

| Mode | What it was | Agentic-ness |
|---|---|---|
| **Q&A** | One-shot question (explain prompt caching), no tools | None — 1 turn |
| **Writing** | 900-word blog post from a brief, written to a file | Minimal — 2 turns |
| **Data work** | Clean a messy 285-row sales CSV (dupes, 4 date formats, missing values) + write summary | Moderate — 6–11 turns |
| **Coding** | Fix 7 planted bugs in a small Python library until 16 unit tests pass | Agentic — 10–17 turns |
| **Coding-hard** | Implement a mini query-language engine (tokenizer/parser/evaluator) from spec against 28 provided tests | Agentic — 5–12 turns |

**Controls:** identical prompt and fixture per mode; fresh workspace per run; one session per (model × task); `--effort high` everywhere; `--safe-mode` (no CLAUDE.md, MCP servers, skills, or hooks contaminating context); all runs back-to-back on the same day/machine; verified task success after every run (all 40 passed); zero permission denials; zero budget-cap terminations. Reps: 2 per mode (3 for coding), 1 for coding-hard.

**Cost accounting:** summed from each session's per-message usage (deduped by the CLI itself), priced at standard rates — cache reads at 0.1× input, cache writes at 1.25×/2× for 5m/1h TTL. Price basis is **standard tier** ($3/$15 for Sonnet); Sonnet's intro rate ($2/$10 through 2026-08-31) shown separately. Our computed costs matched the CLI's `/cost`-equivalent to the cent on every run.

---

## Results

Costs are per-run means across reps (spread in parentheses where it matters). Full per-run data: `results_table.tsv`.

### Q&A (one-shot, no tools) — the one place Sonnet ≈ Opus

| Model | Turns | Total tokens | Cost (cold / warm cache) |
|---|---|---|---|
| Haiku 4.5 | 1 | ~24K | $0.014 / $0.014 |
| **Sonnet 5** | 1 | **~32K** | $0.196 / **$0.060** |
| Opus 4.8 | 1 | ~23K | $0.219 / $0.058 |
| Fable 5 | 1 | ~24K | $0.464 / $0.137 |

Sonnet's sticker says it should cost 60% of Opus. Measured: **89–104% of Opus.** Why: the session is almost all fixed overhead (Claude Code's ~23K-token system prompt), and Sonnet's tokenizer renders that same prompt as ~32K tokens — 40% more than Opus counts. The discount and the tokenizer tax almost exactly cancel. (Warm-cache numbers — second run of the day — are the realistic steady state.)

### Writing (single-pass, 2 turns)

| Model | Turns | Total tokens | Cost |
|---|---|---|---|
| Haiku 4.5 | 2 | ~50K | $0.034 |
| **Sonnet 5** | 2 | **~67K** | $0.103 |
| Opus 4.8 | 2 | ~49K | $0.166 |
| Fable 5 | 2 | ~52K | $0.366 |

Sonnet = 62% of Opus — the sticker ratio holds. Note the tokenizer again: ~67K tokens vs everyone else's ~50K for the same job.

### Data work (moderate agentic)

| Model | Turns | Total tokens | Cost |
|---|---|---|---|
| Haiku 4.5 | 9–11 | ~325K | $0.091 |
| **Sonnet 5** | 7–10 | ~301K | $0.237 |
| Opus 4.8 | 6–7 | ~174K | $0.354 |
| Fable 5 | 6–9 | ~193K | $0.681 |

Sonnet churned through ~1.7× the tokens of Opus (a few more turns × fatter tokenizer) — **exactly the effect the commenters described** — but at 0.1× cache-read pricing it still landed at 67% of Opus's cost.

### Coding (fix bugs until tests pass; 3 reps)

| Model | Turns | Total tokens | Cost (min–max) |
|---|---|---|---|
| Haiku 4.5 | 13–17 | ~323K | $0.077–0.100 |
| **Sonnet 5** | 10–12 | ~385K | $0.241–0.282 |
| Opus 4.8 | 14–16 | ~430K | $0.472–0.550 |
| Fable 5 | 13–14 | ~166K | $0.657–0.712 |

Sonnet = **53% of Opus** — *better* than sticker, because it consistently took fewer turns here. The seed observation's premise ("Sonnet churns 3–4× more turns") did not appear: across 3 reps its turn count never exceeded Opus's.

### Coding-hard (implement a parser/evaluator from spec, 28 tests)

| Model | Turns | Total tokens | Cost | Wall time |
|---|---|---|---|---|
| Haiku 4.5 | 12 | ~352K | $0.098 | 47s |
| **Sonnet 5** | 6 | ~192K | $0.270 | 66s |
| Opus 4.8 | 10 | ~275K | $0.482 | 107s |
| Fable 5 | 7 | ~180K | $0.761 | 79s |

The harder task *widened* Sonnet's advantage — it one-shotted most of the implementation (5 assistant messages; one of them was a single 5,912-token code write) while Opus took 9. Every model still passed all 28 tests.

---

## Why the numbers come out this way

**1. Agentic cost is turn count × context size, at 0.1× per token.** In the coding runs, cache reads were 92–96% of all billed tokens. Turn-by-turn data (from the session transcripts) shows the mechanism: Sonnet's coding session re-read 25K tokens on turn 1, growing to 43K by turn 10 — fresh input per turn was ~2 tokens. Every turn re-reads everything before it. This is why turn count is *the* cost multiplier: the per-turn re-read is cheap (0.1×), but it's charged again on every single turn, on an ever-growing context.

**2. Sonnet 5's tokenizer counts ~30–45% more.** Same text, more tokens — we saw it in every mode (Q&A: 32K vs Opus's 23K; writing: 67K vs 49K). This erodes the 40%-off sticker to roughly 25%-off in practice, and to ~nothing on tiny tasks dominated by fixed overhead. Anthropic documents this (~30% more tokens vs the previous Sonnet); per-token *prices* didn't change, but per-*task* token counts did.

**3. Model "style" matters more than sticker price.** Fable 5 is the mirror image of the cheap-model story: 2× Opus's per-token price, but it used the fewest tokens of any frontier model on agentic tasks (166K vs Opus's 430K on coding) — landing at only ~1.3× Opus's cost instead of 2×. Frugal expensive models and chatty cheap models both bend their effective price toward the middle.

**4. So when CAN the inversion happen?** Our tasks were self-contained and well-specified, and every model solved them without flailing. The seed run's Sonnet took 101 turns on a real codebase with ~115K tokens of context per turn — roughly 3× our per-turn context and 8× our turn counts. The inversion needs (a) a big context, so each extra turn is expensive, times (b) a run where the cheaper model gets stuck retrying — wrong fix, re-run tests, wrong fix again. That's a *quality-gap-under-difficulty* phenomenon, and it's run-to-run variance, not a constant: the same model on the same task can take 10 turns or 100. One pathological run is a data point about variance, not proof the model is always more expensive. We could not induce it in 8 Sonnet agentic runs; every one beat Opus on cost.

---

## Practical takeaways (the video deliverable)

- **For chat-sized, one-shot use: the sticker is a lie in both directions — but the dollars are tiny.** Sonnet ≈ Opus per question (~6¢ each, warm), because fixed overhead + tokenizer swamp the discount. If your usage is Q&A-shaped, pick by *quality*, not price — or use Haiku, which really is 4× cheaper (1.4¢).
- **For writing and one-pass generation: stickers work.** Sonnet cost 62% of Opus, right on its sticker ratio.
- **For agentic work (coding, data): Sonnet 5 was genuinely the cheaper frontier model — in our runs.** 53–67% of Opus's cost, and it often took *fewer* turns. The "cheap model loops forever" failure mode is real but situational: it shows up on hard, messy, big-context tasks, not as a constant tax.
- **The number to watch is turns, not tokens-per-dollar.** If you see a session grinding past 30–50 turns without converging, that's when it's burning money — switch models or restart with a better-specified prompt. Cost ≈ turns × context; everything else is rounding.
- **Haiku 4.5 was the quiet winner of this whole experiment.** Cheapest in every mode by 3–7×, and it completed *every* task — including implementing the parser — successfully. For well-specified tasks, the cheapest sticker really was the cheapest in practice.
- **Sonnet's intro pricing ($2/$10 through Aug 31) makes all its numbers ~33% lower** — e.g. coding drops from ~$0.27 to ~$0.18/run. Every Sonnet figure above is at standard rates for fairness.

### Honest caveats

- Our tasks are small (minutes, not hours; ~15–40K context, not 100K+). The seed inversion happened at 3× the context and 8× the turns — we did not reach that regime, so we can't rule the inversion out there; we can only say it's not the norm.
- One run per cell for coding-hard, two for most modes, three for coding. Turn counts are noisy (Haiku coding: 13–17 across reps); the cross-model gaps we report are larger than the within-model spread, but modestly.
- All models succeeded at every task, so this measures cost-at-equal-success. On tasks where a cheaper model *fails* and you re-run it, its effective cost doubles — factor that in.
- Cache-warmth varied between rep1 and rep2 (first session of the day pays cache writes). We report both; it shifts small-task numbers a lot and agentic numbers barely.

---

## Reproducibility

- **Harness:** `run_one.sh` — headless Claude Code (`claude -p`), flags: `--effort high --safe-mode --permission-mode acceptEdits --allowedTools "Bash TodoWrite Task" --max-budget-usd <cap>`, fresh workdir per run, task success verified programmatically after each run.
- **Fixtures & prompts:** `fixtures/` and `prompts/` (buggy inventory lib, logquery skeleton + tests, messy CSV generator output, writing brief, Q&A prompt).
- **Raw data:** `results/*.json` (one Claude Code result JSON per run: turns, usage with cache-write TTL split, per-model usage, wall time), `manifest.jsonl` (verification outcomes), `results_table.tsv` (parsed table).
- **Analysis:** `analyze.py` (pricing formula: input×rate + 5m-writes×1.25 + 1h-writes×2.0 + reads×0.1 + output×out-rate), `turns.py` (per-turn cache growth from session transcripts, deduped by message id).
- Model IDs as reported by the CLI: `claude-sonnet-5`, `claude-opus-4-8`, `claude-fable-5`, `claude-haiku-4-5`. Date: 2026-07-05. CLI: 2.1.201.
