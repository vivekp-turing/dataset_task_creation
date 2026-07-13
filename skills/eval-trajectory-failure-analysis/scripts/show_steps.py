#!/usr/bin/env python3
"""Dump full detail for specific trajectory steps (message + tool calls + observation).

Use after trajectory_stats.py points you at hotspot/failure steps. Read the actual
content of those steps to do root-cause analysis and pull verbatim snippets.

Usage:
    python3 show_steps.py <trial_dir|trajectory.json> <step_id> [<step_id> ...]
    python3 show_steps.py <trial_dir> --range 120-140
    python3 show_steps.py <trial_dir> --grep "ValueError"     # steps whose obs/msg match
    python3 show_steps.py <trial_dir> 130 --obs-chars 4000    # widen observation cap
"""
import json, os, sys, argparse, re


def _find(path):
    if os.path.isfile(path):
        return path
    for c in (os.path.join(path, "agent", "trajectory.json"),
              os.path.join(path, "trajectory.json")):
        if os.path.isfile(c):
            return c
    sys.exit(f"no trajectory.json under {path}")


def _obs(step):
    out = []
    for r in ((step.get("observation") or {}).get("results") or []):
        if isinstance(r.get("content"), str):
            out.append(r["content"])
    return "\n".join(out)


def show(step, obs_chars):
    print("=" * 100)
    print(f"STEP {step.get('step_id')}  [{step.get('source')}]  {step.get('timestamp')}")
    msg = step.get("message") or ""
    if msg:
        print(f"\n--- message (planning/reasoning) ---\n{msg}")
    rc = step.get("reasoning_content") or ""
    if rc:
        print(f"\n--- reasoning_content ---\n{rc}")
    for tc in (step.get("tool_calls") or []):
        args = tc.get("arguments") or {}
        print(f"\n--- tool: {tc.get('function_name')} ---")
        if "keystrokes" in args:
            print(args["keystrokes"])
        else:
            print(json.dumps(args, indent=1)[:2000])
    obs = _obs(step)
    if obs:
        clip = obs if len(obs) <= obs_chars else obs[:obs_chars] + f"\n…[+{len(obs)-obs_chars} chars]"
        print(f"\n--- observation ---\n{clip}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("steps", nargs="*", type=int)
    ap.add_argument("--range", help="A-B inclusive step_id range")
    ap.add_argument("--grep", help="show steps whose message/observation match regex")
    ap.add_argument("--obs-chars", type=int, default=2500)
    a = ap.parse_args()

    traj = json.load(open(_find(a.path)))
    steps = traj.get("steps") or []
    want = set(a.steps)
    if a.range:
        lo, hi = map(int, a.range.split("-"))
        want |= {s.get("step_id") for s in steps if lo <= (s.get("step_id") or -1) <= hi}
    rx = re.compile(a.grep) if a.grep else None

    shown = 0
    for s in steps:
        sid = s.get("step_id")
        hit = sid in want
        if rx and not hit:
            if rx.search(s.get("message") or "") or rx.search(_obs(s)):
                hit = True
        if hit:
            show(s, a.obs_chars)
            shown += 1
    if not shown:
        print("no matching steps")


if __name__ == "__main__":
    main()
