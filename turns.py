#!/usr/bin/env python3
"""Per-assistant-message usage from a run's session transcript.

Finds the transcript via the run's result JSON (session_id) and the
project-slug directory derived from the run workdir. Dedupes by message.id
(brief's gotcha: streaming partials log the same message multiple times).

Usage: turns.py <mode> <model> <rep>
"""
import json, os, sys, glob

EXP = os.path.dirname(os.path.abspath(__file__))
mode, model, rep = sys.argv[1], sys.argv[2], sys.argv[3]

with open(os.path.join(EXP, "results", f"{mode}__{model}__rep{rep}.json")) as f:
    result = json.load(f)
sid = result["session_id"]

matches = glob.glob(os.path.expanduser(f"~/.claude/projects/*/{sid}.jsonl"))
if not matches:
    sys.exit(f"no transcript for session {sid}")

seen = {}
order = []
with open(matches[0]) as f:
    for line in f:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("type") != "assistant":
            continue
        msg = rec.get("message", {})
        u = msg.get("usage")
        mid = msg.get("id")
        if not u or not mid:
            continue
        if mid not in seen:
            order.append(mid)
        seen[mid] = u  # keep last record for the id

print(f"{'turn':>4} {'input':>8} {'cache_w':>9} {'cache_r':>10} {'output':>7}")
tot_r = 0
for i, mid in enumerate(order, 1):
    u = seen[mid]
    cw = u.get("cache_creation_input_tokens", 0)
    cr = u.get("cache_read_input_tokens", 0)
    tot_r += cr
    print(f"{i:>4} {u.get('input_tokens',0):>8} {cw:>9} {cr:>10} {u.get('output_tokens',0):>7}")
print(f"assistant messages: {len(order)}; total cache reads: {tot_r}")
