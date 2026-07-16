# Task taxonomy (assign per the provided task requirements)

Assign each task the **single category + subcategory** that best describes the
**dominant engineering work** required to resolve the issue (choose by the main
objective of the fix, not incidental steps). Also assign **objective labels** and
**artifact labels** — those are **multi-label** (all that genuinely apply). These flow
into `task.toml` `[metadata]` (`category`, `subcategory`, `objective_labels`,
`artifact_labels`).

> A helper exists to draft these with an LLM judge: `scripts/tag_task.py` (outputs a
> confidence-scored JSON + a `final_decision`). Always human-review the result.

## Categories → subcategories

- **Software Engineering** — behavioral gap/regression in the software itself (app
  logic, library behavior, API contracts, CLI, service).
  Feature implementation · Refactoring and code modernization · Testing and quality
  engineering · Compilers, interpreters, and programming languages · Porting and
  migration · Scripting and automation · Web, API, and networking software · Version
  control and repository operations
- **Debugging and Repair** — central challenge is root-causing a failure.
  Runtime bug repair · Test failure repair · Build failure repair · Configuration
  repair · Performance debugging · Concurrency and synchronization debugging ·
  Pipeline and orchestration debugging
- **Build, Dependency, and Release Management** — build/packaging/deps are the
  objective.
  Build system configuration · Dependency and lockfile resolution · CI/CD pipelines ·
  Container builds · Cross-compilation and platform targeting · Package publishing ·
  Release artifacts
- **Systems, Infrastructure, and Operations** — how software runs/deploys.
  OS, process, and service management · Users, permissions, and access control · Shell
  and environment configuration · Networking configuration · Containers and
  orchestration · Storage and filesystem administration · Scheduling and automation
  infrastructure · Logging, monitoring, and observability
- **Data Processing and ETL** — reshaping/parsing/validating data.
  ETL pipelines · File format parsing and serialization · Tabular transformation ·
  Text processing · Data validation · Streaming data processing · Media data
  processing
- **Data Querying and Databases** — query correctness/performance or DB admin.
  SQL querying · Analytical queries · Query optimization · Database administration ·
  NoSQL and document stores · Graph and semantic queries
- **Machine Learning and AI** — model-facing logic (not training infra).
  Model inference and prediction · Model evaluation and benchmarking · Feature
  engineering · NLP and language models · ML serving and deployment · Interpretability
  and model inspection
- **Model Training and ML Infrastructure** — the training run / training infra.
  Training loops · Fine-tuning · Data loading and training pipelines · Checkpointing
  and resumption · Distributed training · Evaluation infrastructure
- **Security** — security correctness / vulnerability remediation / investigation.
  Cryptography · Authentication and authorization · Vulnerability analysis · Security
  hardening
- **Scientific Computing and Domain Science** — numerical simulation / scientific
  modeling.
  Numerical methods · Differential equations and simulation · Biology and
  bioinformatics · Signal processing · Statistical modeling
- **Mathematics and Formal Reasoning** — exact math / symbolic / formal verification.
  Symbolic computation · Number theory and exact arithmetic · Computational linear
  algebra · Algorithms and optimization theory · Formal verification

## Objective labels (multi-label)

Fix · Implement · Refactor · Test · Optimize · Migrate · Configure · Debug · Validate ·
Build or package · Analyze · Secure or harden

## Artifact labels (multi-label)

Codebase · Single script or program · Test suite or benchmark · Build system or package
metadata · Configuration file · Service or daemon · Container or virtual environment ·
Database or structured store · Dataset or tabular file · Text or log file · Binary
executable or library · Model or checkpoint · Network endpoint or protocol artifact ·
Repository history or version-control state · Security artifact · Mathematical or
scientific model · Generated output artifact

## Source type (single)

**net-new** — these tasks are **strictly net-new**: an original feature/capability or a
real edge-case gap that is **genuinely absent at the pinned base SHA**, authored fresh
from the repo. Do **not** derive tasks from existing PRs/commits/issues in the repo, and
do not seed regressions.

## Distribution targets (reconciled batch-wise, not per-task)

- Aim for **uniform, diverse coverage** across categories and subcategories — spread
  tasks so no bucket dominates and as many categories/subcategories as feasible are
  represented. Any hard caps/quotas come from the **provided task requirements** if it
  specifies them.
- **Language distribution** is likewise kept diverse/uniform across buckets and
  reconciled at the batch/dataset level (with cosine-similarity diversity) — not the
  job of a single spec.
