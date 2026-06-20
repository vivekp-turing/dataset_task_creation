# repo_summary.md — required output structure

Every `repo_summary.md` MUST use this exact section order. Replace bracketed text;
keep headings verbatim. Tables/snippets are expected, not optional.

```markdown
# {OWNER/REPO} - Repo Summary & Mental Model

**Summary:** {3-5 dense sentences: what it is, language/build system, core module
layout, test setup, and the key build/offline notes.}

## Overview
{What the project does, primary use cases, what it is NOT, current version + target
runtimes/frameworks.}

## Language, Build & Tooling
| Aspect | Details |
|--------|---------|
| Language | ... |
| Build system | ... |
| Solution/manifest files | ... |
| Key project files | ... |
| Test runner | ... |
| Linters / analyzers | ... |
| Key versions | {SDK/runtime + pinned package versions} |

{Key build/test commands as a fenced code block.}

## Architecture & Code Organization
| Module / Directory | Role |
|--------------------|------|
| ... | ... |

{Namespaces/packages. How things are wired (DI, factories, SPI, registration). The
**type/class hierarchy** when relevant, e.g. `A → B → C → D`.}

## Mental Model / How It Works
{End-to-end flow with concrete file paths. Convey the hierarchy/graph: the request/
data/render pipeline, parse→model→evaluate→serialize chain, state machines, etc.
Use sub-bullets or an ASCII flow when it helps.}

## Key Features & Important Implementations (with file paths)
| File | Role |
|------|------|
| path/to/file | ... |

## Testing (framework, location, how to run, sample test, network needs)
{Framework, where tests live, how to run, a short sample test snippet, and clearly
which test layers are **offline-safe (unit)** vs need **network/display/GPU/live
service/Docker**. Distinguish unit vs integration explicitly.}

## Offline / Containerization Notes
1. SDK/runtime version required.
2. Dependency restore + what to pre-cache (NuGet/pip/npm/Maven).
3. Native deps / system libs.
4. Submodules (init if build needs them); shallow-clone/tags caveat.
5. Smallest verify command (a single offline-safe test target).
6. Suggested base image.

## Good Surfaces for Original Tasks
{8-14 numbered items. Each: implementation file(s) + existing test file(s) that
anchor fail2pass + a ~100-LoC task idea + (feature | bug-fix) + (offline-safe | needs
X). Favor pure-logic, well-tested, offline surfaces.}

1. **{area}** — `path/impl`, `path/test`. {Task idea}. (feature, offline-safe)
2. ...

## Risks / Gotchas
{Numbered pitfalls: huge build, native/platform deps, display/GPU/live-service
needs, slow restore, flaky areas, warnings-as-errors, multi-target compilation,
breaking-version baselines, etc.}

*Explored from `{branch/tag}`.*
```
