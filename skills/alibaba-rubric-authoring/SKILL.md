---
name: alibaba-rubric-authoring
description: >-
  Author or refine rubric.md for an Alibaba Harbor task bundle. Generates
  per-task rubrics from the overall rubric spec + task_spec rubric seeds, with
  a hard gate that correctness criteria must align with the exec verifier.
  Use after alibaba-harbor-task-build or when asked to write/review rubrics
  for Alibaba Coding Evals tasks.
---

# Alibaba rubric authoring

Generate or refine `rubric.md` for a built Harbor bundle. The rubric supplements
human/LLM trajectory scoring; **correctness must not conflict with the exec verifier**.

References:
- [`docs/alibaba/rubrics_overall.yaml`](../../docs/alibaba/rubrics_overall.yaml)
- [`docs/alibaba/sample_task/rou3-repeated-regex-modifier-constraints/rubric.md`](../../docs/alibaba/sample_task/rou3-repeated-regex-modifier-constraints/rubric.md)

## Inputs

- Built bundle: `<root>/deliverables/<S>/test-assets/<S>/`
- Spec (optional): `<root>/tasks/<S>/task_spec.md` — rubric seeds section
- Overall rubric: `docs/alibaba/rubrics_overall.yaml`

## Output

- `test-assets/<S>/rubric.md` — finalized per-task rubric
- Update `scoring/scoring_summary.json`: set `rubric_test_alignment: true` after check

## rubric.md structure

```markdown
# Rubric

Scores are 1 to 5. A score of 3 is the lowest passing score. The automated verifier and this rubric define the same correctness target.

## Correctness - 35%

- <general correctness bullets from overall spec for this task_type>
- <must mirror what test.sh checks — no extra bar, no weaker bar>

## Code Quality - 25%
...

## Reasoning - 15%
...

## Efficiency - 15%
...

## Tool Usage - 10%
...

## Task-specific focus

Bucket: `<task_type>` / `<domain>`.

<why_worth_using one-liner from task.toml>

## Task-specific scoring points

### Correctness
- <from spec rubric seeds — restate verifier pass conditions>

### Code Quality
- ...

### Reasoning
- ...

### Efficiency
- ...

### Tool Usage
- ...
```

Weights follow `task_type_weights` in rubrics_overall.yaml. Map taxonomy task_type
via `taxonomy_to_rubric_type` (e.g. `compatibility-fix` → bug_fix weights).

For `code_qa` tasks, add an **Explanation** section.

## Conflict check (mandatory gate)

Before marking rubric complete, verify:

1. **No extra correctness requirements** — every rubric correctness bullet must be
   satisfied when `test.sh` passes. If the rubric demands something the verifier
   doesn't check, remove or move it to code_quality/reasoning.
2. **No weaker bar** — if `test.sh` passes, rubric correctness must be ≥ 3 (pass).
   If the verifier checks edge cases, rubric must mention them.
3. **Alignment statement** — first paragraph must state verifier and rubric share
   the same correctness target (see sample10 rubric).
4. **Cross-check** — read `instruction.md`, `tests/test.sh` embedded patch assertions,
   and rubric Correctness sections side by side.

Run the alignment checklist:

```
- [ ] List each fail2pass assertion in test.sh / embedded patch
- [ ] Map each to a rubric Correctness bullet (1:1 or grouped)
- [ ] Confirm no rubric Correctness bullet lacks a verifier counterpart
- [ ] Confirm pass2pass / regression preservation is stated in both
- [ ] Set scoring_summary.json rubric_test_alignment: true
```

## Workflow

```
- [ ] Read task.toml (task_type, domain, why_worth_using)
- [ ] Read instruction.md + tests/test.sh (embedded patch + run command)
- [ ] Read spec rubric seeds (if available)
- [ ] Draft rubric.md from template + overall spec weights
- [ ] Run conflict check; fix mismatches
- [ ] Update scoring/scoring_summary.json
```

## Anti-patterns

- Rubric requiring docstrings/tests the verifier doesn't run
- Rubric omitting edge cases the hidden tests assert
- Different task_type weights than rubrics_overall.yaml without justification
- Correctness bullets that reference file paths or test names (use behavior language)
