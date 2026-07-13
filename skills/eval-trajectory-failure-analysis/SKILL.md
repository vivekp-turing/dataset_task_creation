---
name: eval-trajectory-failure-analysis
description: Deep trajectory + failure-mode analysis of harbor eval trials, following a 3-stage pipeline. Stage 1 (per trial) judges the agent's exploration phase; Stage 2 (per trial) produces a structured failure-mode "verdict" JSON grounded in the verifier, tagging each failure agent-attributable or not; Stage 3 (across trials) aggregates all agent-attributable failures into a ranked, generalized failure taxonomy. Profiles where the agent struggled (time/tokens/planning/tool calls), segments exploration vs execution, does root-cause ("why" ladder) analysis with verbatim snippets, a reward-hacking/clean-trajectory check, and smart/dumb-move sections. The process is task-agnostic — the analysis prompts adapt to whatever task you point it at, but the intermediate-report → aggregation → taxonomy flow stays fixed. Use when asked to analyze, dig into, or post-mortem an eval trajectory / agent run / a low- or mixed-reward trial, or to build failure modes across a whole run.
---

# Eval trajectory & failure-mode analysis (3-stage pipeline)

Produce a deep, evidence-backed post-mortem of agent runs from a harbor eval. The output is a
written/structured report, not just numbers. Numbers exist to point you at the exact steps to
read; the analysis comes from reading those steps.

This skill mirrors a fixed **3-stage process** (per-trial exploration → per-trial verdict →
cross-trial taxonomy). The pipeline is **invariant**; only the *prompts* and the
verifier/domain specifics adapt to the task you're given. Whatever the task — ML competition,
code review, SLAM debugging, config dry-run — you follow the same stages and emit the same
report schemas, swapping in that task's instruction + grading as ground truth.

Two non-negotiables, in every stage:
- **Root cause, not symptoms.** For every failure keep asking "why did that happen?" until you
  hit something that, if changed, would have prevented it — a wrong assumption, a misread file,
  a missing check, a capability gap. "The test failed" is a symptom. "It reordered the
  quaternion but never validated heading against LiDAR, so a sign error survived to the end" is
  closer to root cause. Go one more "why" than feels necessary.
- **Show the evidence.** Every claim (struggle, failure, reward-hack, smart/dumb move) cites a
  `step_id` and quotes the relevant snippet (command, the agent's `Analysis:/Plan:`, or the
  observation). No snippet → don't assert it.

## Inputs & data layout

You're pointed at either a **single trial directory** (e.g.
`.../<run>/warehouse-slam-fusion-debug_7__Dh3UWjj/`) or a **whole run directory** containing
many `<task>__<trialid>/` trials. Inside each trial:

```
<trial>/
  result.json                 # agent_info, agent_result (tokens/cost), agent_execution (timing), verifier_result
  config.json                 # config.task.path -> the task source dir (instruction.md, verifier, solution)
  agent/
    trajectory.json           # PRIMARY source. {schema_version, agent, steps[], final_metrics}
    episode-<i>/              # one LLM call each: prompt.txt, response.txt, debug.json
    terminus_2.pane,*.cast    # raw terminal render (rarely needed)
  verifier/
    reward.json               # reward + components{score, weight, subscores}, raw_metrics, exit codes
    breakdown.json            # (some tasks) alt breakdown
    metrics.json, junit.xml, pytest.log, *.audit.json, test-stdout.txt   # ground truth of WHY the score is what it is
  analyzer/                   # <- THIS SKILL WRITES HERE (created if absent); see Outputs
```

**`agent/trajectory.json` → `steps[]`** is the spine. Each agent step:
- `step_id`, `timestamp`, `source` (`agent`/`user`), `message` (the agent's visible
  `Analysis: … Plan: …` — its planning/reasoning), `reasoning_content` (often empty),
  `tool_calls[]` (`function_name`, `arguments.keystrokes`, `arguments.duration`),
  `observation.results[].content` (terminal output), `metrics` (`prompt_tokens`,
  `completion_tokens`, `cached_tokens`, `cost_usd`).
- Extended-thinking text is usually **empty/redacted** (`thinking:""` + signature) in
  `episode-*/debug.json`. When so, treat the `message` field + per-step wall-gap + completion
  tokens as the reasoning-effort proxy. `debug.json` still gives `llm_api_duration_ms`.

**Always read the task definition** at `config.json → config.task.path`: `instruction.md` (what
was asked), the verifier/tests, and `solution/` if present. You cannot judge "failure",
"reward hacking", "exploration gaps", or "smart/dumb" without knowing the intended task and how
it's graded. This is what makes the analysis task-agnostic: the task def + verifier ARE the
rubric you analyze against, whatever the domain.

## Supporting scripts (use for reading, not concluding)

```bash
# Effort/struggle profile: totals, phase table (exploration↔execution map), hotspots, repeated commands.
python3 skills/eval-trajectory-failure-analysis/scripts/trajectory_stats.py \
    <trial_dir> [--phases 8] [--top 12] [--json prof.json]

# Pull full content of specific steps / ranges / grep matches (read agent thought + cmd + observation together).
python3 skills/eval-trajectory-failure-analysis/scripts/show_steps.py <trial_dir> 35 82 143 194
python3 skills/eval-trajectory-failure-analysis/scripts/show_steps.py <trial_dir> --range 120-140
python3 skills/eval-trajectory-failure-analysis/scripts/show_steps.py <trial_dir> --grep "Traceback|FAILED|Error"
```

The profile and step dumps drive *where you read*. They do not write the report — you do, from
the steps.

---

# The 3-stage process

## Stage 0 — Preprocess (per trial, no LLM judgment yet)

Split the trajectory into the two lenses the later stages consume, and load ground truth:

1. **Exploration view** — the read-only / inspection actions: reading files, `ls`/`cat`/`grep`/
   `find`/`nl`, listing dirs, diagnostic commands, searching the tree. This is "what the agent
   looked at."
2. **Implementation view** — everything that mutates or commits: edits, file writes, running
   tests, installs, the final submit. This is "what the agent did."
   (`trajectory_stats.py`'s tool mix + `show_steps.py --grep` help you separate the two; a single
   step can contribute to both.)
3. **Task + verifier bundle** — `instruction.md`, the tests/verifier, `solution/` if present,
   and `verifier/reward.json` + logs + `*.audit.json`. Note which parts were **never visible to
   the agent** (gold solution, held-out tests, hidden metrics) — Stage 2 reasons against these
   as "verifier-only" ground truth.

Then run `trajectory_stats.py` to form hypotheses about where the run was hard/slow/repetitive.
Don't conclude yet.

## Stage 1 — Exploration analysis (per trial → intermediate report)

Judge the **exploration phase only**, against the task (you know the task; the agent only had
the repo + task text). Produce a written narrative covering:

- **What it inspected** — the files/dirs/areas the agent effectively looked at (infer paths from
  commands/outputs), clustered by area.
- **Per cluster: why it looked, what it concluded, and a verdict label** — one of
  `helpful / correct / wrong / unnecessary / waste_of_time` — with a rationale tied to the task.
  Cite `step_id`s.
- **Gaps** — important areas it *should* have explored but didn't, given the task and where the
  points actually were.
- **(Adapt to the task)** add a domain line where useful: e.g. data/distribution understanding
  for ML tasks, threat-surface coverage for security/review tasks, repro of the baseline failure
  for debugging tasks. The *axes* change with the task; the shape (inspected → per-cluster
  verdict → gaps) does not.

Write this as **`<trial>/analyzer/stage1_exploration.md`** (free-text). This is an intermediate
report; Stage 2 reads it back as context.

## Stage 2 — Verdict (per trial → structured failure-mode JSON)

Now judge the **whole run**, feeding in: your Stage-1 narrative + the implementation view + the
verifier-only ground truth. This is where root-cause and reward-hacking analysis happen.

Steps:
1. **Ground the outcome in the verifier.** Open `verifier/reward.json` (component scores +
   subscores + `raw_metrics` + exit codes), `pytest.log`/`junit.xml`/`test-stdout.txt`, and any
   `*.audit.json` (LLM-judge rubric axes). Map each lost-point component back to specific
   trajectory steps. A component at 0 with everything else passing is the loudest clue.
2. **Trace each failure to root cause (the "why" ladder).** For every component that lost points,
   build a why-chain, each link backed by a quoted trajectory/verifier snippet. Stop when the
   next "why" is "the model isn't capable of X" or "nobody told it Y" — that's the actionable
   root cause. Example shape:
   > pytest_all_gates = 0 ← `mean_nees` is 1.29e6 (gate wants ~1) ← EKF covariance far too small
   > for the residuals ← agent fixed quaternion order + ICP trimming but never recalibrated
   > measurement noise / never checked NEES ← it validated only position residuals (step 143) and
   > treated low residual as "done", **never reading the test's consistency gate** ← root cause:
   > inferred success criteria from the data instead of from the gate definition, so a whole
   > grading axis was invisible.
3. **Reward-hacking / integrity check.** Did it game the verifier (hardcoding expected outputs,
   special-casing test inputs, editing/peeking at tests or held-out data, faking metrics, writing
   the answer file directly, touching protected inputs)? State **clean** or describe the hack with
   step + snippet.
4. **Tag attribution.** For each failure mode decide `agent_attributable`: **true** if a competent
   agent given only the task + repo could reasonably have avoided it through better reading,
   reasoning, or implementation; **false** if it mainly reflects an unfair/ambiguous spec, tests
   requiring unknowable exact shapes, or hindsight only visible in verifier-only materials. This
   field is load-bearing — Stage 3 only aggregates the `true` ones.

Emit **`<trial>/analyzer/stage2_verdict.json`** with this **invariant schema** (keys in quotes
are fixed; pick `category` labels freely as short readable snake_case — it is NOT a closed set):

```json
{
  "instance_id": "<trial dir name>",
  "reward": 0.62,
  "implementation_summary": "what was implemented, which files, why and how",
  "failure_modes": [
    {
      "category": "ignored_grading_gate",
      "description": "…",
      "agent_attributable": true,
      "evidence_step_ids": [143, 188]
    }
  ],
  "failure_mode_summary": { "agent_attributable": 3, "not_agent_attributable": 1 },
  "<domain_analysis>": "…",
  "<domain_outcome>": "…"
}
```

The last two keys are the **only task-specific part of the schema** — name them for the domain,
e.g.:
- debugging / test-graded tasks → `"test_failure_analysis"` (string) + `"task_fairness"`
  (`{"fair": bool, "description": str}`)
- ML-competition tasks → `"modeling_analysis"` + `"reward_explanation"`
- code-review tasks → `"review_quality_analysis"` + `"reward_explanation"`

Always include `failure_mode_summary` and make its counts match `failure_modes`. Default a missing
`agent_attributable` to `true`.

> Single trial? Stop here and write the human report (see "Report sections"). The Stage-2 JSON is
> the structured core; the prose report is its readable rendering.

## Stage 3 — Failure-mode taxonomy (across trials → aggregate report)

Run only when you have **Stage-2 verdicts for multiple trials** (a whole run, or k attempts of a
task, or several tasks). It turns scattered per-trial `category` labels into one ranked,
generalized taxonomy.

1. **Collect** every `analyzer/stage2_verdict.json` under the run dir. From each, keep only
   `failure_modes[]` where `agent_attributable == true`. Keep `(instance_id, category,
   description)` for each.
2. **Build a generalized taxonomy.** Cluster the raw categories+descriptions into ~15–28
   generalized categories that describe *how the agent failed at the task class* (exploration
   strategy, analysis depth, missed the grading criterion, output/format errors, process
   efficiency, …) — language/repo/task-instance agnostic. Each category = `{id, name,
   definition}` where `definition` is 1–2 sentences applicable to any instance. Dedupe near-
   identical raw modes before clustering so frequency isn't double-counted.
3. **Assign** every raw agent-attributable mode to exactly one category id (every mode gets one;
   no drops). For large sets, do this in batches.
4. **Rank** categories by frequency (count of modes mapped in), descending; collect the deduped
   set of `instance_ids` per category.

Write **`<run>/stage3_aggregate_report.json`**:

```json
{
  "taxonomy": [ { "id": "…", "name": "…", "definition": "…" } ],
  "ranked_modes": [
    {
      "generalized_category_id": "…",
      "name": "…",
      "definition": "…",
      "count": 12,
      "instance_ids": ["task__abc", "task__def"]
    }
  ],
  "metadata": {
    "dataset_root": "<run dir>",
    "instances_with_stage2": 40,
    "total_attributable_modes": 95,
    "total_attributable_modes_mapped": 95,
    "model": "<analyzer model / 'claude-code-skill'>",
    "generated_at_utc": "<ISO-8601 UTC>"
  }
}
```

And per trial, **`<trial>/analyzer/stage3_report.json`**:

```json
{
  "instance_id": "task__abc",
  "failure_modes_agent_attributable": [
    {
      "original_category": "ignored_grading_gate",
      "description": "…",
      "generalized_category_id": "missed_success_criterion",
      "generalized_category_name": "Did not read / optimize the actual grading criterion"
    }
  ]
}
```

Then present a **ranked failure-mode table** (rank, name, count, # instances, definition, one
illustrative example citing a real trial + its reward) — this is the headline deliverable for a
multi-trial run.

---

## Required report sections (the readable rendering)

For a **single trial**, write the prose report from the Stage-1/Stage-2 material with these
sections (use real `step_id`s + quoted snippets):

1. **TL;DR** — task in one line, final reward + component breakdown, the single root-cause
   sentence for the main point loss.
2. **Effort & difficulty map** — where it spent the most *time*, *tokens*, *planning/reasoning*,
   *tool calls*; which phase(s) carried the cost. Reference the phase table + hotspots.
3. **Easy vs hard** — what it nailed quickly/cheaply vs. ground on (looping, repeated commands,
   edit-rerun cycles). Cite the repeated-command list + slow steps.
4. **Exploration analysis (Stage 1)** — the inspected-areas / per-cluster verdict / gaps
   narrative; where exploration was useful vs. wasted, and the balance vs. execution.
5. **Failure-mode analysis / verdict (Stage 2, root cause)** — one subsection per failure:
   symptom → why → why → root cause, each link backed by a quoted snippet, each tagged
   agent-attributable or not. End each with the minimal change that would have prevented it.
6. **Reward hacking / trajectory integrity** — **clean** or the hack with step + snippet; check
   protected-input integrity if the task has it.
7. **Smart moves** — genuinely good decisions, each with a step cite.
8. **Dumb moves** — avoidable mistakes / wasted effort / wrong turns, each with a step cite.

For a **multi-trial run**, lead with the **Stage-3 ranked failure-mode table + taxonomy**, then
include per-trial Stage-2 summaries (and full single-trial reports for the most informative
trials — lowest reward, or a clear pass/fail pair).

## Outputs & scope

- This skill **writes intermediate reports** under each trial's `analyzer/` dir
  (`stage1_exploration.md`, `stage2_verdict.json`, and on a multi-trial run `stage3_report.json`)
  plus a run-level `stage3_aggregate_report.json`. These are the durable artifacts; the prose is
  their rendering. (This is distinct from the eval-summary-table skill, which is display-only.)
- Default to **one trial** (Stages 0–2) unless asked for run-wide failure modes or pointed at a
  whole run dir → then do Stage 3 too. If pointed at a run dir without a named trial, either run
  the full pipeline over all trials, or pick the most informative trial(s) for a deep dive and say
  which and why.
- If extended-thinking is redacted, say so and lean on `message` + wall-gaps; don't invent
  reasoning the agent didn't surface.
- Keep it concrete and skimmable — quoted snippets and `step N` references over adjectives.
