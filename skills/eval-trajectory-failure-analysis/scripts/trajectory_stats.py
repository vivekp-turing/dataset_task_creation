#!/usr/bin/env python3
"""Quantitative effort/difficulty profiler for a single harbor eval trial.

Reads a trial directory's trajectory.json (+ verifier + result.json, and optional
per-episode debug.json) and emits an effort map the analyst uses to decide WHERE
in the trajectory to read closely: token/cost/time/tool-call hotspots, phase
segmentation (exploration vs execution), command looping/repetition, tool-error
rate, and reasoning(thinking) volume & API latency.

It does NOT do the qualitative analysis (root cause, reward hacking, smart/stupid).
It tells you where to look; you read those steps and reason.

Usage:
    python3 trajectory_stats.py <trial_dir> [--top N] [--phases K] [--json OUT]
    python3 trajectory_stats.py <trajectory.json> [...]

<trial_dir> is a harbor trial dir (contains agent/trajectory.json, verifier/, result.json).
"""
import json, os, sys, argparse, re
from collections import Counter, defaultdict
from datetime import datetime


def _find_trajectory(path):
    if os.path.isfile(path):
        return path, os.path.dirname(os.path.dirname(path))
    cand = os.path.join(path, "agent", "trajectory.json")
    if os.path.isfile(cand):
        return cand, path
    cand2 = os.path.join(path, "trajectory.json")
    if os.path.isfile(cand2):
        return cand2, os.path.dirname(path)
    sys.exit(f"no trajectory.json found under {path}")


def _load_json(p):
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return None


def _parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


ERROR_SIGNATURES = [
    "command not found", "No such file or directory", "Traceback (most recent call last)",
    "SyntaxError", "ImportError", "ModuleNotFoundError", "AttributeError", "NameError",
    "TypeError", "ValueError:", "KeyError", "IndexError", "AssertionError",
    "Permission denied", "fatal:", "error:", "ERROR", "FAILED", "Segmentation fault",
    "cannot ", "Exception", "panic:", "undefined reference", "not defined",
]


def _obs_text(step):
    obs = step.get("observation") or {}
    parts = []
    for r in (obs.get("results") or []):
        c = r.get("content")
        if isinstance(c, str):
            parts.append(c)
    return "\n".join(parts)


def _keystrokes(step):
    ks = []
    for tc in (step.get("tool_calls") or []):
        args = tc.get("arguments") or {}
        k = args.get("keystrokes")
        if isinstance(k, str):
            ks.append(k.strip())
    return ks


def _enrich_thinking(agent_dir, n_agent_steps):
    """Map episode-i/debug.json -> thinking char-count & api latency, in episode order.
    Returns list aligned to episode index (0-based)."""
    out = []
    if not os.path.isdir(agent_dir):
        return out
    eps = []
    for d in os.listdir(agent_dir):
        m = re.fullmatch(r"episode-(\d+)", d)
        if m:
            eps.append((int(m.group(1)), os.path.join(agent_dir, d)))
    eps.sort()
    for idx, ep in eps:
        dbg = _load_json(os.path.join(ep, "debug.json")) or {}
        think_chars, latency = 0, dbg.get("llm_api_duration_ms")
        orr = dbg.get("original_response")
        if isinstance(orr, str):
            try:
                orr = json.loads(orr)
            except Exception:
                orr = None
        if isinstance(orr, dict):
            for block in (orr.get("content") or []):
                if isinstance(block, dict) and block.get("type") == "thinking":
                    think_chars += len(block.get("thinking") or "")
            usage = orr.get("usage") or {}
        else:
            usage = {}
        out.append({"episode": idx, "thinking_chars": think_chars,
                    "latency_ms": latency, "usage": usage})
    return out


def analyze(path, top=12, phases=8):
    traj_path, trial_dir = _find_trajectory(path)
    traj = _load_json(traj_path) or {}
    steps = traj.get("steps") or []
    agent_dir = os.path.dirname(traj_path)

    reward = _load_json(os.path.join(trial_dir, "verifier", "reward.json")) \
        or _load_json(os.path.join(trial_dir, "verifier", "breakdown.json"))
    result = _load_json(os.path.join(trial_dir, "result.json")) or {}
    metrics = _load_json(os.path.join(trial_dir, "verifier", "metrics.json"))

    agent_steps = [s for s in steps if s.get("source") == "agent"]
    n = len(agent_steps)

    rows = []
    prev_ts = None
    for i, s in enumerate(agent_steps):
        m = s.get("metrics") or {}
        ts = _parse_ts(s.get("timestamp"))
        gap = (ts - prev_ts).total_seconds() if (ts and prev_ts) else 0.0
        prev_ts = ts
        obs = _obs_text(s)
        ks = _keystrokes(s)
        err = sum(1 for sig in ERROR_SIGNATURES if sig in obs)
        rows.append({
            "i": i,
            "step_id": s.get("step_id"),
            "out_tok": m.get("completion_tokens") or 0,
            "in_tok": m.get("prompt_tokens") or 0,
            "uncached_in": (m.get("prompt_tokens") or 0) - (m.get("cached_tokens") or 0),
            "cost": m.get("cost_usd") or 0.0,
            "gap_s": gap,
            "msg_len": len(s.get("message") or ""),
            "reason_len": len(s.get("reasoning_content") or ""),
            "obs_len": len(obs),
            "tools": [tc.get("function_name") for tc in (s.get("tool_calls") or [])],
            "keystrokes": ks,
            "err_hits": err,
            # Defaults so every row always has these keys even when the
            # trajectory schema has no aligned episode / no extended-thinking
            # (claude-code & codex/ATIF variants differ); _enrich_thinking
            # overwrites them when an episode lines up. Avoids KeyError downstream.
            "thinking_chars": 0,
            "latency_ms": None,
        })

    think = _enrich_thinking(agent_dir, n)
    for i, t in enumerate(think):
        if i < len(rows):
            rows[i]["thinking_chars"] = t["thinking_chars"]
            rows[i]["latency_ms"] = t["latency_ms"]

    # ---- phase segmentation ----
    phase_data = []
    if n:
        size = max(1, (n + phases - 1) // phases)
        for p in range(0, n, size):
            chunk = rows[p:p + size]
            tc = Counter(t for r in chunk for t in r["tools"])
            phase_data.append({
                "range": (chunk[0]["step_id"], chunk[-1]["step_id"]),
                "steps": len(chunk),
                "out_tok": sum(r["out_tok"] for r in chunk),
                "thinking_chars": sum(r.get("thinking_chars", 0) for r in chunk),
                "wall_s": sum(r["gap_s"] for r in chunk),
                "cost": sum(r["cost"] for r in chunk),
                "tool_calls": sum(len(r["tools"]) for r in chunk),
                "err_hits": sum(r["err_hits"] for r in chunk),
                "top_tools": tc.most_common(4),
            })

    # ---- command repetition / looping ----
    cmd_counts = Counter()
    for r in rows:
        for k in r["keystrokes"]:
            norm = " ".join(k.split())[:160]
            if norm:
                cmd_counts[norm] += 1
    repeated = [(c, k) for k, c in cmd_counts.items() if c >= 3]
    repeated.sort(reverse=True)

    def hot(key, label, fmt):
        ranked = sorted(rows, key=lambda r: r[key], reverse=True)[:top]
        return label, [(r["step_id"], fmt(r[key]), len(r["tools"]),
                        (r["keystrokes"][0][:70] if r["keystrokes"] else "")) for r in ranked]

    report = {
        "trial_dir": trial_dir,
        "task": (result.get("task_name") or traj.get("agent", {}).get("name")),
        "model": (result.get("agent_info", {}).get("name", "") + "/" +
                  result.get("agent_info", {}).get("model_info", {}).get("name", "")),
        "n_agent_steps": n,
        "totals": {
            "out_tok": sum(r["out_tok"] for r in rows),
            "uncached_in": sum(r["uncached_in"] for r in rows),
            "cost": sum(r["cost"] for r in rows),
            "wall_min": sum(r["gap_s"] for r in rows) / 60.0,
            "tool_calls": sum(len(r["tools"]) for r in rows),
            "tool_mix": Counter(t for r in rows for t in r["tools"]).most_common(),
            "err_steps": sum(1 for r in rows if r["err_hits"]),
            "thinking_chars": sum(r.get("thinking_chars", 0) for r in rows),
        },
        "final_metrics": traj.get("final_metrics"),
        "reward": reward,
        "verifier_metrics": metrics,
        "phases": phase_data,
        "repeated_commands": repeated[:15],
        "hot_out_tok": hot("out_tok", "output tokens", lambda v: f"{v:,}"),
        "hot_cost": hot("cost", "cost $", lambda v: f"${v:.3f}"),
        "hot_gap": hot("gap_s", "wall gap (s)", lambda v: f"{v:.0f}s"),
        "hot_obs": hot("obs_len", "obs bytes", lambda v: f"{v:,}"),
        "hot_msg": hot("msg_len", "planning/message chars", lambda v: f"{v:,}"),
        "hot_think": hot("thinking_chars", "thinking chars", lambda v: f"{v:,}"),
    }
    return report, rows


def _print(report):
    r = report
    p = print
    p(f"# Trajectory effort profile\n")
    p(f"trial : {r['trial_dir']}")
    p(f"task  : {r['task']}")
    p(f"model : {r['model']}")
    p(f"steps : {r['n_agent_steps']} agent steps")
    t = r["totals"]
    p(f"\n## Totals")
    p(f"  output tokens   : {t['out_tok']:,}")
    p(f"  uncached input  : {t['uncached_in']:,}")
    p(f"  thinking chars  : {t['thinking_chars']:,}  (extended-thinking text across episodes)")
    p(f"  wall (step gaps): {t['wall_min']:.1f} min")
    p(f"  cost            : ${t['cost']:.2f}")
    p(f"  tool calls      : {t['tool_calls']}   mix={t['tool_mix']}")
    p(f"  steps w/ error-signature in output: {t['err_steps']}")
    if r["reward"]:
        p(f"\n## Reward")
        p(json.dumps(r["reward"], indent=2)[:1500])
    if r["verifier_metrics"]:
        p(f"\n## Verifier raw metrics")
        p(json.dumps(r["verifier_metrics"], indent=2)[:800])
    p(f"\n## Phases (exploration vs execution map)")
    p(f"{'steps':>13} {'n':>4} {'out_tok':>9} {'think_ch':>9} {'wall_s':>8} {'cost':>7} {'calls':>6} {'err':>4}  top_tools")
    for ph in r["phases"]:
        a, b = ph["range"]
        p(f"  {a:>4}-{b:<6} {ph['steps']:>4} {ph['out_tok']:>9,} {ph['thinking_chars']:>9,} "
          f"{ph['wall_s']:>8.0f} ${ph['cost']:>6.2f} {ph['tool_calls']:>6} {ph['err_hits']:>4}  "
          f"{[(x,c) for x,c in ph['top_tools']]}")
    if r["totals"]["thinking_chars"] == 0:
        p("\n  NOTE: extended-thinking text is empty/redacted for this agent — use the")
        p("        message field (Analysis:/Plan:) and wall-gap as the reasoning proxy.")
    for key in ("hot_gap", "hot_msg", "hot_out_tok", "hot_think", "hot_cost", "hot_obs"):
        label, items = r[key]
        p(f"\n## Hotspots by {label}  (step_id, value, #tools, first cmd)")
        for sid, val, nt, cmd in items:
            p(f"  step {sid:<5} {val:>10}  tools={nt}  {cmd}")
    if r["repeated_commands"]:
        p(f"\n## Repeated commands (>=3x — looping/struggle signal)")
        for c, k in r["repeated_commands"]:
            p(f"  {c:>3}x  {k}")
    p(f"\n# Next: read the hotspot steps in agent/trajectory.json (message + tool_calls + observation),")
    p(f"#       cross-check against verifier/ outputs and the task instruction.md, then write the analysis.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="trial dir or trajectory.json")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--phases", type=int, default=8)
    ap.add_argument("--json", help="write full report json here")
    a = ap.parse_args()
    report, rows = analyze(a.path, top=a.top, phases=a.phases)
    _print(report)
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"report": report, "rows": rows}, f, indent=2, default=str)
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
