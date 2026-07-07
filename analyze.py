#!/usr/bin/env python3
"""Parse experiment result JSONs and compute per-run costs.

Price basis: standard per-MTok rates (not Sonnet intro), cache read 0.1x input,
cache write 1.25x (5m) / 2.0x (1h). Sonnet intro basis ($2/$10) reported alongside.
"""
import json, glob, os, sys

EXP = os.path.dirname(os.path.abspath(__file__))

RATES = {  # (input, output) $ per MTok, standard tier
    "claude-sonnet-5": (3.0, 15.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-fable-5": (10.0, 50.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
SONNET_INTRO = (2.0, 10.0)

def rate_for(model_key):
    for alias, r in RATES.items():
        if model_key.startswith(alias):
            return r
    # dated haiku helper etc.
    if "haiku" in model_key: return (1.0, 5.0)
    if "sonnet" in model_key: return (3.0, 15.0)
    if "opus" in model_key: return (5.0, 25.0)
    if "fable" in model_key: return (10.0, 50.0)
    raise ValueError(model_key)

def cost_main(usage, in_rate, out_rate):
    w5 = usage.get("cache_creation", {}).get("ephemeral_5m_input_tokens", 0)
    w1 = usage.get("cache_creation", {}).get("ephemeral_1h_input_tokens", 0)
    return (usage["input_tokens"] * in_rate
            + w5 * in_rate * 1.25
            + w1 * in_rate * 2.0
            + usage["cache_read_input_tokens"] * in_rate * 0.1
            + usage["output_tokens"] * out_rate) / 1e6

def cost_helper(mu, in_rate, out_rate):
    # modelUsage entries don't split cache-write TTL; Claude Code uses 1h -> 2.0x
    return (mu["inputTokens"] * in_rate
            + mu["cacheCreationInputTokens"] * in_rate * 2.0
            + mu["cacheReadInputTokens"] * in_rate * 0.1
            + mu["outputTokens"] * out_rate) / 1e6

rows = []
for path in sorted(glob.glob(os.path.join(EXP, "results", "*.json"))):
    base = os.path.basename(path)[:-5]
    mode, model, rep = base.split("__")
    with open(path) as f:
        try:
            r = json.load(f)
        except json.JSONDecodeError:
            print(f"SKIP unparseable: {base}", file=sys.stderr)
            continue
    u = r.get("usage", {})
    in_rate, out_rate = RATES[model]
    main_cost = cost_main(u, in_rate, out_rate)
    # helper models = modelUsage keys that aren't the main alias
    helper_cost = 0.0
    helper_tokens = 0
    for k, mu in r.get("modelUsage", {}).items():
        if k == model:
            continue
        hr = rate_for(k)
        helper_cost += cost_helper(mu, *hr)
        helper_tokens += mu["inputTokens"] + mu["outputTokens"] + mu["cacheReadInputTokens"] + mu["cacheCreationInputTokens"]
    w5 = u.get("cache_creation", {}).get("ephemeral_5m_input_tokens", 0)
    w1 = u.get("cache_creation", {}).get("ephemeral_1h_input_tokens", 0)
    total_tokens = u.get("input_tokens", 0) + w5 + w1 + u.get("cache_read_input_tokens", 0) + u.get("output_tokens", 0)
    row = {
        "mode": mode, "model": model, "rep": rep,
        "turns": r.get("num_turns"),
        "wall_s": round(r.get("duration_ms", 0) / 1000),
        "input": u.get("input_tokens", 0),
        "cache_write": w5 + w1,
        "cache_read": u.get("cache_read_input_tokens", 0),
        "output": u.get("output_tokens", 0),
        "total_tokens": total_tokens,
        "cost_std": round(main_cost + helper_cost, 4),
        "cost_cli": round(r.get("total_cost_usd", 0), 4),
        "terminal": r.get("terminal_reason"),
        "denials": len(r.get("permission_denials", [])),
        "models_used": ",".join(sorted(r.get("modelUsage", {}).keys())),
    }
    if model == "claude-sonnet-5":
        row["cost_intro"] = round(cost_main(u, *SONNET_INTRO) + helper_cost, 4)
    rows.append(row)

MODE_ORDER = {"qa": 0, "writing": 1, "data": 2, "coding": 3}
MODEL_ORDER = {"claude-haiku-4-5": 0, "claude-sonnet-5": 1, "claude-opus-4-8": 2, "claude-fable-5": 3}
rows.sort(key=lambda x: (MODE_ORDER.get(x["mode"], 9), MODEL_ORDER.get(x["model"], 9), x["rep"]))

hdr = ["mode","model","rep","turns","wall_s","input","cache_write","cache_read","output","total_tokens","cost_std","cost_intro","cost_cli","terminal","denials"]
print("\t".join(hdr))
for x in rows:
    print("\t".join(str(x.get(h, "-")) for h in hdr))
