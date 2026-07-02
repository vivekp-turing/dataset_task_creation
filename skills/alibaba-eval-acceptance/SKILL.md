---
name: alibaba-eval-acceptance
description: >-
  Run model pilot evals and score trajectories for Alibaba Coding Evals acceptance.
  Documents the fixed agent setup, required models, output schemas for
  runs/model_runs.json and scoring/scoring_summary.json, and the acceptance
  checklist (opus ≤60%, model gaps ≥20%, 20+ turns, env-failure tagging).
  Use after rubric authoring when running pilots or checking if a task ships.
---

# Alibaba eval & acceptance

Run model pilots and determine whether a task meets Alibaba acceptance criteria.
Exact Harbor eval commands run on the client's harness — this skill defines
**process, schemas, and gates**.

Reference: [`Alibaba Coding Evals ask.md`](../../Alibaba%20Coding%20Evals%20ask.md)

## Required models (5 attempts each)

| Model | Role |
|-------|------|
| `claude-opus-4.6` | Primary frontier baseline; pass rate must be ≤ 60% |
| `claude-sonnet-4.6` | Discrimination target; gap vs opus ≥ 20% |
| `qwen-3.7-max` | Discrimination target; gap vs opus ≥ 20% |
| `glm-5.1` | Weak-spot finder (especially vs Claude) |

## Fixed agent setup

All models use the **same tools and agent configuration**:

- Agent: claudecode (exact config TBD with client — see sample10 scaffold)
- **Subagents: required** for final acceptance
- Same shell, search, file edit, and test tools for every model
- Record full trajectories (system prompt, tools, main + subagent turns)

Update `runs/model_runs.json` → `fixed_agent_setup` when pilot config is confirmed.

## Inputs / outputs

**Input:** `<root>/deliverables/<S>/test-assets/<S>/` (complete bundle)

**Outputs:**
- `runs/model_runs.json` — trajectories + per-attempt results
- `scoring/scoring_summary.json` — dual-reviewer rubric scores + agreement

### runs/model_runs.json schema

```json
{
  "status": "COMPLETE | NEEDS_REAL_MODEL_RUNS",
  "required_models": ["claude-opus-4.6", "claude-sonnet-4.6", "qwen-3.7-max", "glm-5.1"],
  "fixed_agent_setup": {
    "agent": "<claudecode config ref>",
    "subagents": "required",
    "same_tools_for_all_models": true
  },
  "models": {
    "claude-opus-4.6": {
      "attempts": [
        {
          "attempt": 1,
          "passed": true,
          "turns": 24,
          "env_failure": false,
          "trajectory_path": "<path or inline ref>",
          "reward": 1,
          "notes": ""
        }
      ],
      "pass_rate": 0.4,
      "mean_turns": 22.4
    }
  }
}
```

Tag `env_failure: true` when the run failed due to Docker/build/network/tooling —
these do **not** count toward difficulty assessment.

### scoring/scoring_summary.json schema

```json
{
  "status": "COMPLETE | NEEDS_SECOND_SCORING",
  "rubric_test_alignment": true,
  "scorer_agreement": 0.85,
  "reviewers": ["reviewer_a", "reviewer_b"],
  "models": {
    "claude-opus-4.6": {
      "attempts": [
        {
          "attempt": 1,
          "rubric_scores": {
            "correctness": 5,
            "code_quality": 4,
            "reasoning": 4,
            "tool_usage": 4,
            "efficiency": 3
          },
          "weighted_total": 4.15
        }
      ]
    }
  },
  "note": ""
}
```

Score trajectories with [`alibaba-rubric-authoring`](../alibaba-rubric-authoring/SKILL.md)
rubric.md. Two independent reviewers; record agreement (Cohen's kappa or % within 1 point).

## Acceptance checklist

A task **ships** only when ALL pass:

| # | Criterion | How to check |
|---|-----------|--------------|
| 1 | claude-opus-4.6 pass rate ≤ 60% | `models.claude-opus-4.6.pass_rate` |
| 2 | qwen vs opus gap ≥ 20% | `opus.pass_rate - qwen.pass_rate ≥ 0.20` |
| 3 | sonnet vs opus gap ≥ 20% | `opus.pass_rate - sonnet.pass_rate ≥ 0.20` |
| 4 | Mean turns ≥ 20 (opus attempts) | `models.claude-opus-4.6.mean_turns` |
| 5 | Failures are task-hardness | Review failures; exclude `env_failure: true` |
| 6 | Rubric/exec aligned | `scoring_summary.rubric_test_alignment == true` |
| 7 | Dual-reviewer scoring done | `scorer_agreement` recorded |
| 8 | All 4 models × 5 attempts | `runs/model_runs.json` complete |
| 9 | Subagents used where flagged | Check trajectories if `requires_subagents` |
| 10 | Distribution cap | ≤100 in this `code_lang × task_type × application` |

## Workflow

```
- [ ] Confirm bundle passes verify.sh
- [ ] Confirm rubric.md passes conflict check (rubric skill)
- [ ] Run 5 attempts × 4 models on Harbor harness
- [ ] Record trajectories in runs/model_runs.json
- [ ] Two reviewers score each trajectory → scoring/scoring_summary.json
- [ ] Run acceptance checklist
- [ ] If fail: classify failure (too easy / env / rubric / instruction) → harden → rebuild
- [ ] If pass: set task.toml [alibaba].status = "accepted"
```

## Hardening guidance (when acceptance fails)

| Symptom | Action |
|---------|--------|
| Opus pass > 60% | Underspecify instruction; add edge cases to verifier; force cross-subsystem reasoning |
| Gap < 20% | Task may be too easy or too hard for all; adjust difficulty levers |
| Env failures | Fix Dockerfile/workspace.tar.gz; don't count as task failures |
| Turns < 20 | Task may be too easy or instruction too leading; expand scope slightly |
| Rubric conflict | Fix rubric.md or verifier — must align before re-scoring |

## Distribution tracking

Maintain a manifest of accepted tasks by `code_lang × task_type × application`.
Stop authoring in a bucket when it reaches 100 tasks.
