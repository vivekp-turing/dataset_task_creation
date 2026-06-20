# Exploration brief (give this to each explore subagent)

Use one **read-only `explore` subagent per repo**, thoroughness **"very thorough"**.
Fill the `{...}` placeholders. The subagent must **return a single markdown document
as its final message** — it does not write files or clone.

---

Thoroughness: very thorough.

You are deeply exploring a cloned {LANGUAGE} repository to produce a comprehensive
"mental model" summary that will be used later to design original SWE-bench-style
coding tasks (bug fixes / feature implementations with **~100 LoC gold patches
across multiple files**, **fail2pass tests**, and an **offline-buildable Docker
image with a <100MB git source image**).

Repo location (already cloned, shallow): {ABSOLUTE_CLONE_PATH}
Repo: {OWNER/REPO} ({1-2 line description of what it is}).

Explore the repo thoroughly using read-only tools (read files, glob, grep, semantic
search). Examine, at minimum:
- README, CONTRIBUTING, and any docs/ that explain architecture.
- Build/project/manifest files (e.g. package.json, pyproject.toml/setup.cfg,
  pom.xml/build.gradle, *.sln/*.slnx/*.csproj, Directory.Build.props,
  Directory.Packages.props, global.json, go.mod, Cargo.toml) and pinned
  SDK/runtime/tool versions.
- The core source directories and the most important abstractions/files.
- The **type/class hierarchy** and **module dependency graph** (how things wire
  together: DI, factories, plugin/registration, service locators, SPIs).
- The end-to-end runtime flow (request/data/render pipeline, parse→model→evaluate→
  serialize chain, state machines — whatever shape the system has).
- Test projects: framework, where tests live, how to run them, a representative
  test, and **what each test layer needs** (offline-safe unit vs network/display/
  GPU/live-service/Docker integration). This is critical for the task spec: a task
  surface is only usable if its tests run deterministically offline.

Then produce a SINGLE markdown document following EXACTLY the structure in the
output template you were given (the section list is fixed). Requirements:

- Be concrete: every architecture/flow claim must cite a **real file path** you
  actually opened. No hand-waving or invented paths.
- The **Mental Model** section must convey the repo's hierarchy/graph, not just
  prose — describe the type hierarchy, module graph, and the main pipeline(s),
  referencing concrete files.
- **Good Surfaces for Original Tasks**: 8-14 numbered items. Each must cite the
  implementation file(s), the existing test file(s) that would anchor fail2pass, a
  brief ~100-LoC task idea, whether it's a **feature** or **bug-fix** surface, and
  whether it is **offline-safe** (no network/display/GPU/live service). Strongly
  favor pure-logic, well-tested, offline surfaces.
- **Testing** and **Offline / Containerization Notes** must be concrete enough to
  write a Dockerfile and a smallest passing test command from.
- Keep it dense and useful for task authors (~120-180 lines is typical).

Do NOT write files — you are read-only. Return the markdown as your final message.
