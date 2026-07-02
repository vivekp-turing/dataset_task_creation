---
name: seed-repo-exploration
description: >-
  Deeply explore SEED REPOS (already selected) and write a high-detail
  repo_summary.md per repo — overview, build/test/tooling, architecture, a
  hierarchical mental model, key implementation files, testing + OFFLINE
  containerization notes, and concrete "Good Surfaces for Original Tasks" tailored
  to Alibaba task requirements (~100 LoC multi-file patches, fail2pass tests,
  workspace.tar.gz env + offline Docker build). Flag surfaces that could target
  Alibaba high-priority dimensions (long-horizon, subagents, web search, etc.). Use
  after picking seed repos (e.g. from seed-repo-selection / seed_repos.csv) when
  asked to explore repos deeply, build a mental model, summarize a repo for task
  authoring, or set up a tasks/ folder with one summary per repo. Runs the
  exploration in parallel.
disable-model-invocation: true
---

# Seed-Repo Exploration

Take a set of already-selected seed **repositories** and produce, for each one, a
dense `repo_summary.md` that a task author can use to invent **original**
tasks that meet the Alibaba task spec. The summary must include a real **mental
model** of the repo: how it works end-to-end, its type/module hierarchy, and where
~100-LoC fail2pass tasks naturally live.

This skill is the step **after** `seed-repo-selection`. Selection picks
the repos; this explores them.

## Key intent (do not violate)

- One folder + one `repo_summary.md` **per repo**, inside the user's `tasks/` dir.
- Goal is **task-authoring intelligence**, not docs: every summary ends with
  concrete, file-cited "Good Surfaces for Original Tasks" + "Risks/Gotchas".
- Tailor everything to the task constraints (see below). Especially flag what is
  **offline-safe** vs needs network/display/GPU/live services — this gates whether
  a surface is usable for a containerized fail2pass task.
- Flag surfaces that could target Alibaba high-priority dimensions when applicable.
- Explore in **parallel** (one read-only subagent per repo). The main agent does
  `git clone` and writes files; subagents only analyze and return markdown.

## Task constraints the exploration serves

- **~100 LoC gold patch across multiple files** → find surfaces with that natural
- **fail2pass + pass2pass tests** → prefer code with dense, deterministic, fast
  **unit** tests that don't need network/display/GPU/live services.
- **`workspace.tar.gz` env, offline Docker build** → record SDK/runtime versions,
  what to pre-cache (NuGet/pip/npm/Maven), native deps, submodules, and the
  smallest verify command.
- **Feature implementation AND bug fixes** → identify both kinds of surfaces.
- **Difficulty mix** → note which surfaces are subtle vs simple; flag candidates for
  Alibaba Hard band (opus ≤60%, 20+ turns).

## Workflow

```
- [ ] 1. Confirm inputs: which repos (subset of the candidate CSV), how many per
        language, and the target tasks/ dir. Don't assume — read the CSV.
- [ ] 2. Make tasks/<repo-slug>/ folders and a clones/ dir (slug = short repo name).
- [ ] 3. Shallow-clone each repo in parallel (git clone --depth 1).
- [ ] 4. Launch one read-only explore subagent per repo, in parallel batches
        (e.g. per language group), each given the Exploration brief below.
- [ ] 5. Write each subagent's returned markdown to tasks/<slug>/repo_summary.md.
- [ ] 6. Verify every folder has a non-trivial repo_summary.md (line count check).
- [ ] 7. Report picks grouped by language with the standout task surfaces.
```

### Step 2-3: setup + clone (main agent)

```bash
mkdir -p "<tasks_dir>" "<base>/clones"
cd "<base>/clones"
git clone --depth 1 https://github.com/<owner>/<repo>.git <slug>   # one per repo, in parallel
```

Use a stable `<slug>` (e.g. `ssh-net` for `sshnet/SSH.NET`, `ical-net` for
`ical-org/ical.net`). Keep clones out of `tasks/` so summaries stay clean.

Clone gotchas to handle: **git submodules** (init them if the build needs vendored
code, e.g. Avalonia's `external/XamlX`); shallow clones drop tags (note to pin a
release tag for a reproducible baseline).

### Step 4: parallel exploration (subagents)

Launch one **read-only `explore` subagent per repo**, with thoroughness
**"very thorough"**. Subagents cannot clone or write — they read the already-cloned
repo and **return a single markdown document** as their final message. Give each
subagent the full Exploration brief (see `exploration_brief.md`) plus the exact
output template (`repo_summary_template.md`), the cloned path, and 1-2 lines on
what the repo is.

Batch the launches (e.g. 5 at a time per language) so multiple Task calls go out in
one message.

### Step 5: write summaries (main agent)

For each subagent result, write its markdown verbatim to
`<tasks_dir>/<slug>/repo_summary.md`. Fix only the H1 title if needed.

### Step 6: verify

```bash
cd "<tasks_dir>" && for d in */; do f="${d}repo_summary.md"; \
  [ -f "$f" ] && printf "%-22s %5s lines\n" "${d%/}" "$(wc -l < "$f")" \
  || printf "%-22s MISSING\n" "${d%/}"; done
```

A good summary is typically ~120-180 lines. Re-run a subagent for anything thin or
missing the task-surface / offline sections.

## The output: `repo_summary.md`

Every summary uses the fixed structure in
[repo_summary_template.md](repo_summary_template.md). Non-negotiable sections:

1. **Summary** — 3-5 dense sentences (what, language/build, module layout, test
   setup, offline notes).
2. **Overview** — what it does, use cases, what it is NOT, version/target runtimes.
3. **Language, Build & Tooling** — table + key build/test commands.
4. **Architecture & Code Organization** — table of modules/dirs → role; namespaces;
   how things are wired; **type/class hierarchy** when relevant.
5. **Mental Model / How It Works** — end-to-end flow with **concrete file paths**;
   the hierarchical/graphical model of the system (pipelines, trees, state machines).
6. **Key Features & Important Implementations** — table of file → role.
7. **Testing** — framework, location, how to run, a sample test, and **network/
   display/GPU/live-service needs** (the offline gate).
8. **Offline / Containerization Notes** — numbered: SDK/runtime version, restore/
   pre-cache, native deps, submodules, smallest verify command, base image.
9. **Good Surfaces for Original Tasks** — 8-14 numbered items, each citing real
   files + existing tests + a ~100-LoC task idea, marked feature vs bug-fix and
   offline-safe vs not.
10. **Risks / Gotchas** — numbered pitfalls (huge build, native deps, flaky tests,
    warnings-as-errors, live-service dependence, etc.).

## Quality bar (what makes a summary "deep")

- Every claim about architecture or flow cites a **real file path** the subagent
  actually opened — no hand-waving.
- The mental model explains the **hierarchy/graph**: type hierarchy, module
  dependency, the request/data/render pipeline, or the parse→model→evaluate→
  serialize chain — whatever shape the repo has.
- "Good Surfaces" are **actionable**: a task author could pick one and start. Each
  names the implementation file(s), the test file(s) that would anchor fail2pass,
  the change size, and whether it runs offline.
- Offline notes are concrete enough to write a Dockerfile from (exact SDK version,
  what to pre-cache, smallest passing test command).

## Subagent brief + template

- [exploration_brief.md](exploration_brief.md) — the verbatim instructions to give
  each explore subagent (read-only, very thorough, return markdown only).
- [repo_summary_template.md](repo_summary_template.md) — the exact output structure
  every summary must follow.
