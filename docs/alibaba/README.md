# Alibaba reference materials

Canonical references for the Alibaba Coding Evals task pipeline.

| Path | Source | Purpose |
|------|--------|---------|
| [`harbor_case/`](harbor_case/) | `harbor_case.zip` | Official Harbor layout: `test/<id>.json` + `test-assets/<id>/` |
| [`sample_task/`](sample_task/) | `alibaba_sample10_ready_for_model_runs_share.zip` | Worked Alibaba-complete task (`rou3-repeated-regex-modifier-constraints`) |
| [`rubrics_overall.yaml`](rubrics_overall.yaml) | Alibaba Coding Evals ask.md | Overall rubric dimensions and weights |
| [`taxonomy_v1.yaml`](taxonomy_v1.yaml) | Parsed enums + mappings from official PDF |
| [`[Public] taxonomy_v1 (English).pdf`]([Public]%20taxonomy_v1%20(English).pdf) | Official taxonomy source document |

## Shipped bundle layout (authoritative)

```
deliverables/<slug>/
  test/<slug>.json                    # query (description == instruction.md)
  test-assets/<slug>/
    instruction.md
    task.toml                         # [metadata] + [alibaba]
    environment/Dockerfile
    environment/workspace.tar.gz
    tests/test.sh                     # exec verifier (embedded fail2pass patch)
    tests/test_outputs.py             # patch artifact mirror
    solution/solve.sh                 # ground-truth (embedded gold patch)
    rubric.md
    metadata/author_self_assessment.json
    runs/model_runs.json
    scoring/scoring_summary.json
```

See [`../Alibaba Coding Evals ask.md`](../Alibaba%20Coding%20Evals%20ask.md) for acceptance criteria.

## Validated reference bundle

[`deliverables/rou3-repeated-regex-modifier-constraints/`](../deliverables/rou3-repeated-regex-modifier-constraints/)
is a reference bundle assembled from sample10 in the harbor_case layout. Validate with:

```bash
bash skills/alibaba-harbor-task-build/scripts/verify.sh rou3-repeated-regex-modifier-constraints
bash skills/alibaba-harbor-task-build/scripts/validate_reference.sh
bash skills/alibaba-rubric-authoring/scripts/check_rubric_alignment.sh rou3-repeated-regex-modifier-constraints
python3 docs/alibaba/scripts/validate_taxonomy.py deliverables/rou3-repeated-regex-modifier-constraints/test-assets/rou3-repeated-regex-modifier-constraints/task.toml
```
