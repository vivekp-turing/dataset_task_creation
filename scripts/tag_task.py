#!/usr/bin/env python3
"""Tag a SWE-Bench-style / Harbor-format task with a category, subcategory, and language.

Given a task (a PR, an issue, a commit, or a Harbor-format task folder), this script
uses an LLM (Anthropic Claude) as a judge to classify the *dominant engineering work*
required to resolve the issue into the category / subcategory taxonomy defined in the
batch task-requirements spec, plus the primary programming language.

Output is a JSON object with:
  - ``categories``:    confidence score (0-1) for EVERY category.
  - ``subcategories``: for every category, its TOP-3 subcategories with scores.
  - ``languages``:     confidence score (0-1) for the candidate languages.
  - ``objective_labels`` / ``artifact_labels``: (optional taxonomy metadata, multi-label).
  - ``final_decision``: the single chosen ``category``, ``subcategory``, and ``language``
    (highest-scoring category, its highest-scoring subcategory, and the top language).
  - ``rationale``: a short free-text justification.

Input can be:
  * a Harbor-format task FOLDER  (instruction.md, environment/problem_statement.md,
    task.toml, solution/golden.patch, tests/...);
  * a SWE-Bench-style JSON file  (fields: problem_statement, patch, test_patch,
    hints_text, repo, instance_id, ...);
  * a plain problem-statement text/markdown file.

Usage:
  python tag_task.py <path-to-task> [--output result.json] [--model claude-sonnet-5]
  python tag_task.py ./tasks/django__django-11099 --output tagged.json
  python tag_task.py ./instance.json --model claude-opus-4-8

Requires ANTHROPIC_API_KEY (read from the environment or a nearby .env file).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Taxonomy (from the batch task-requirements spec, "Distribution
# requirements" section). category -> ordered list of subcategories.
# ---------------------------------------------------------------------------
TAXONOMY: Dict[str, List[str]] = {
    "Software Engineering": [
        "Feature implementation",
        "Refactoring and code modernization",
        "Testing and quality engineering",
        "Compilers, interpreters, and programming languages",
        "Porting and migration",
        "Scripting and automation",
        "Web, API, and networking software",
        "Version control and repository operations",
    ],
    "Debugging and Repair": [
        "Runtime bug repair",
        "Test failure repair",
        "Build failure repair",
        "Configuration repair",
        "Performance debugging",
        "Concurrency and synchronization debugging",
        "Pipeline and orchestration debugging",
    ],
    "Build, Dependency, and Release Management": [
        "Build system configuration",
        "Dependency and lockfile resolution",
        "CI/CD pipelines",
        "Container builds",
        "Cross-compilation and platform targeting",
        "Package publishing",
        "Release artifacts",
    ],
    "Systems, Infrastructure, and Operations": [
        "OS, process, and service management",
        "Users, permissions, and access control",
        "Shell and environment configuration",
        "Networking configuration",
        "Containers and orchestration",
        "Storage and filesystem administration",
        "Scheduling and automation infrastructure",
        "Logging, monitoring, and observability",
    ],
    "Data Processing and ETL": [
        "ETL pipelines",
        "File format parsing and serialization",
        "Tabular transformation",
        "Text processing",
        "Data validation",
        "Streaming data processing",
        "Media data processing",
    ],
    "Data Querying and Databases": [
        "SQL querying",
        "Analytical queries",
        "Query optimization",
        "Database administration",
        "NoSQL and document stores",
        "Graph and semantic queries",
    ],
    "Machine Learning and AI": [
        "Model inference and prediction",
        "Model evaluation and benchmarking",
        "Feature engineering",
        "NLP and language models",
        "ML serving and deployment",
        "Interpretability and model inspection",
    ],
    "Model Training and ML Infrastructure": [
        "Training loops",
        "Fine-tuning",
        "Data loading and training pipelines",
        "Checkpointing and resumption",
        "Distributed training",
        "Evaluation infrastructure",
    ],
    "Security": [
        "Cryptography",
        "Authentication and authorization",
        "Vulnerability analysis",
        "Security hardening",
    ],
    "Scientific Computing and Domain Science": [
        "Numerical methods",
        "Differential equations and simulation",
        "Biology and bioinformatics",
        "Signal processing",
        "Statistical modeling",
    ],
    "Mathematics and Formal Reasoning": [
        "Symbolic computation",
        "Number theory and exact arithmetic",
        "Computational linear algebra",
        "Algorithms and optimization theory",
        "Formal verification",
    ],
}

CATEGORY_DESCRIPTIONS: Dict[str, str] = {
    "Software Engineering": (
        "Fix or implementation touches application logic, library behavior, API "
        "contracts, CLI behavior, or service functionality. Use when the issue is a "
        "behavioral gap or regression in the software itself, not the build or infra."
    ),
    "Debugging and Repair": (
        "The central challenge is root-causing a failure rather than adding new "
        "functionality. Use when something is broken and the fix requires investigation "
        "before any code change."
    ),
    "Build, Dependency, and Release Management": (
        "The build, packaging, or dependency-resolution process is itself the main "
        "objective, not the application logic it produces."
    ),
    "Systems, Infrastructure, and Operations": (
        "Most of the work is system or environment configuration rather than "
        "application code. Use when the issue is about how software runs/deploys."
    ),
    "Data Processing and ETL": (
        "The goal is correctly reshaped, parsed, or validated data. Use for data "
        "transformation or serialization correctness, not query logic."
    ),
    "Data Querying and Databases": (
        "The main work is query correctness, query performance, or database "
        "administration - how data is retrieved or stored."
    ),
    "Machine Learning and AI": (
        "ML model behavior, inference pipelines, evaluation, or ML system integration - "
        "model-facing logic rather than training infrastructure."
    ),
    "Model Training and ML Infrastructure": (
        "The training run, fine-tuning process, or training infrastructure is central."
    ),
    "Security": (
        "The core goal is security correctness, vulnerability remediation, or security "
        "investigation."
    ),
    "Scientific Computing and Domain Science": (
        "Numerical simulation, scientific modeling, or domain-specific scientific "
        "workflows."
    ),
    "Mathematics and Formal Reasoning": (
        "Exact mathematical computation, symbolic manipulation, or formal verification."
    ),
}

# Canonical languages we target (spec "Languages" section). Order is not significant.
LANGUAGES: List[str] = [
    "JavaScript / TypeScript",
    "Python",
    "C / C++",
    "Java",
    "C#",
    "PHP",
    "Go",
    "Ruby",
    "Rust",
]

# Multi-label taxonomies (spec: task-objective + artifact-type). Each label that
# genuinely applies to the end goal / central artifacts should be assigned.
OBJECTIVE_LABELS: List[str] = [
    "Fix", "Implement", "Refactor", "Test", "Optimize", "Migrate",
    "Configure", "Debug", "Validate", "Build or package", "Analyze",
    "Secure or harden",
]
ARTIFACT_LABELS: List[str] = [
    "Codebase", "Single script or program", "Test suite or benchmark",
    "Build system or package metadata", "Configuration file", "Service or daemon",
    "Container or virtual environment", "Database or structured store",
    "Dataset or tabular file", "Text or log file", "Binary executable or library",
    "Model or checkpoint", "Network endpoint or protocol artifact",
    "Repository history or version-control state", "Security artifact",
    "Mathematical or scientific model", "Generated output artifact",
]

# Map common file extensions -> canonical language (used only as a *hint* to the LLM).
EXT_TO_LANG: Dict[str, str] = {
    ".ts": "JavaScript / TypeScript", ".tsx": "JavaScript / TypeScript",
    ".js": "JavaScript / TypeScript", ".jsx": "JavaScript / TypeScript",
    ".mjs": "JavaScript / TypeScript", ".cjs": "JavaScript / TypeScript",
    ".py": "Python", ".pyi": "Python", ".pyx": "Python",
    ".c": "C / C++", ".h": "C / C++", ".cc": "C / C++", ".cpp": "C / C++",
    ".cxx": "C / C++", ".hpp": "C / C++", ".hh": "C / C++", ".hxx": "C / C++",
    ".java": "Java",
    ".cs": "C#",
    ".php": "PHP", ".phtml": "PHP",
    ".go": "Go",
    ".rb": "Ruby", ".rake": "Ruby", ".erb": "Ruby",
    ".rs": "Rust",
}

# Truncation limits (characters) per input section, to keep token usage bounded.
MAX_PROBLEM_CHARS = 40_000
MAX_PATCH_CHARS = 60_000
MAX_TESTS_CHARS = 20_000
MAX_MISC_CHARS = 10_000

DEFAULT_MODEL = "claude-sonnet-5"


# ---------------------------------------------------------------------------
# .env loading (no dependency on python-dotenv)
# ---------------------------------------------------------------------------
def load_env_file(explicit: Optional[str], start_dirs: List[Path]) -> None:
    """Populate os.environ from the first .env found, without overriding existing vars."""
    candidates: List[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    seen = set()
    for start in start_dirs:
        d = start.resolve()
        for parent in [d, *d.parents]:
            env = parent / ".env"
            if env not in seen:
                seen.add(env)
                candidates.append(env)
    for env in candidates:
        if not env.is_file():
            continue
        for raw in env.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
        return


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------
def _read_text(path: Path, limit: Optional[int] = None) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if limit is not None and len(text) > limit:
        text = text[:limit] + f"\n\n... [truncated, {len(text) - limit} more chars] ..."
    return text


def _truncate(text: str, limit: int) -> str:
    if text and len(text) > limit:
        return text[:limit] + f"\n\n... [truncated, {len(text) - limit} more chars] ..."
    return text


def _find_first(base: Path, patterns: List[str]) -> Optional[Path]:
    for pat in patterns:
        matches = sorted(base.glob(pat))
        if matches:
            return matches[0]
    return None


def load_task(path: Path) -> Dict[str, str]:
    """Return a dict of task sections: repo, problem, patch, tests, misc."""
    if path.is_dir():
        return _load_harbor_dir(path)
    if path.suffix.lower() == ".json":
        return _load_json_task(path)
    # Fallback: treat any other file as a raw problem statement.
    return {
        "repo": "",
        "problem": _truncate(_read_text(path), MAX_PROBLEM_CHARS),
        "patch": "",
        "tests": "",
        "misc": f"source_file: {path.name}",
    }


def _load_harbor_dir(base: Path) -> Dict[str, str]:
    sections: Dict[str, str] = {"repo": "", "problem": "", "patch": "", "tests": "", "misc": ""}

    # Problem statement: prefer environment/problem_statement.md, then instruction.md.
    problem_parts: List[str] = []
    ps = _find_first(base, ["environment/problem_statement.md", "problem_statement.md"])
    if ps:
        problem_parts.append(f"# problem_statement.md\n{_read_text(ps)}")
    instr = base / "instruction.md"
    if instr.is_file():
        problem_parts.append(f"# instruction.md\n{_read_text(instr)}")
    sections["problem"] = _truncate("\n\n".join(problem_parts), MAX_PROBLEM_CHARS)

    # Golden patch.
    patch = _find_first(base, ["solution/golden.patch", "solution/*.patch",
                               "solution/patch.diff", "*.patch"])
    if patch:
        sections["patch"] = _truncate(_read_text(patch), MAX_PATCH_CHARS)

    # Tests (test.sh + any grade/config). Do NOT over-weight; used as signal only.
    tests_dir = base / "tests"
    test_parts: List[str] = []
    if tests_dir.is_dir():
        for f in sorted(tests_dir.glob("*")):
            if f.is_file():
                test_parts.append(f"# tests/{f.name}\n{_read_text(f, MAX_TESTS_CHARS)}")
    sections["tests"] = _truncate("\n\n".join(test_parts), MAX_TESTS_CHARS)

    # task.toml -> repo name + keywords + description (NOT existing category/subcategory,
    # to avoid biasing the judge with a prior label).
    toml_path = base / "task.toml"
    misc_parts: List[str] = []
    if toml_path.is_file():
        meta = _parse_toml(toml_path)
        repo = _dig(meta, "metadata", "repo") or _dig(meta, "task", "name") or ""
        sections["repo"] = str(repo)
        desc = _dig(meta, "task", "description")
        if desc:
            misc_parts.append(f"description: {desc}")
        kws = _dig(meta, "task", "keywords")
        if kws:
            misc_parts.append(f"keywords: {kws}")
        st = _dig(meta, "metadata", "source_type")
        if st:
            misc_parts.append(f"source_type: {st}")
    sections["misc"] = _truncate("\n".join(misc_parts), MAX_MISC_CHARS)
    return sections


def _load_json_task(path: Path) -> Dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"Failed to parse JSON task {path}: {exc}")
    if isinstance(data, list):
        if not data:
            sys.exit(f"JSON task file {path} is an empty list.")
        data = data[0]  # take the first instance
    if not isinstance(data, dict):
        sys.exit(f"JSON task file {path} must contain an object (or list of objects).")

    def g(*keys: str) -> str:
        for k in keys:
            v = data.get(k)
            if v:
                return v if isinstance(v, str) else json.dumps(v)
        return ""

    problem = g("problem_statement", "problem", "issue", "description",
                "text", "instruction", "prompt")
    hints = g("hints_text", "hints")
    if hints:
        problem = f"{problem}\n\n## Hints\n{hints}"
    patch = g("patch", "golden_patch", "gold_patch", "solution_patch")
    tests = g("test_patch", "tests", "fail_to_pass", "FAIL_TO_PASS", "PASS_TO_PASS")
    repo = g("repo", "repository", "repo_name")
    misc_bits = []
    for k in ("instance_id", "source_type", "language", "base_commit", "version"):
        v = data.get(k)
        if v:
            misc_bits.append(f"{k}: {v}")
    return {
        "repo": repo,
        "problem": _truncate(problem, MAX_PROBLEM_CHARS),
        "patch": _truncate(patch, MAX_PATCH_CHARS),
        "tests": _truncate(tests, MAX_TESTS_CHARS),
        "misc": _truncate("\n".join(misc_bits), MAX_MISC_CHARS),
    }


def _parse_toml(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        import tomllib  # py3.11+
        return tomllib.loads(text)
    except ModuleNotFoundError:
        pass
    try:
        import tomli
        return tomli.loads(text)
    except ModuleNotFoundError:
        pass
    try:
        import toml
        return toml.loads(text)
    except ModuleNotFoundError:
        return {}
    except Exception:
        return {}


def _dig(d: Dict[str, Any], *keys: str) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


# ---------------------------------------------------------------------------
# Language hint from patch / repo
# ---------------------------------------------------------------------------
_DIFF_FILE_RE = re.compile(r"^(?:diff --git a/|\+\+\+ b/|--- a/)([^\s]+)", re.MULTILINE)


def language_hint(sections: Dict[str, str]) -> str:
    counts: Dict[str, int] = {}
    blob = "\n".join([sections.get("patch", ""), sections.get("tests", "")])
    for m in _DIFF_FILE_RE.finditer(blob):
        fname = m.group(1)
        ext = os.path.splitext(fname)[1].lower()
        lang = EXT_TO_LANG.get(ext)
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return "no strong extension signal found in the patch"
    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return ", ".join(f"{lang} ({n} changed file paths)" for lang, n in ordered)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------
def build_taxonomy_block() -> str:
    lines: List[str] = []
    for cat, subs in TAXONOMY.items():
        lines.append(f"### {cat}")
        lines.append(CATEGORY_DESCRIPTIONS.get(cat, ""))
        for sub in subs:
            lines.append(f"  - {sub}")
        lines.append("")
    return "\n".join(lines)


SYSTEM_PROMPT = (
    "You are an expert software-engineering taxonomist. You classify SWE-Bench-style "
    "coding tasks into a fixed category/subcategory taxonomy and identify the primary "
    "programming language. You reason about the DOMINANT engineering work required to "
    "resolve the issue - if multiple categories apply, you pick the one matching the "
    "MAIN objective of the fix, not incidental supporting steps. You always respond "
    "with a single, strictly valid JSON object and nothing else."
)


def build_user_prompt(sections: Dict[str, str], lang_hint: str) -> str:
    taxonomy_block = build_taxonomy_block()
    langs = "\n".join(f"  - {l}" for l in LANGUAGES)
    objectives = ", ".join(OBJECTIVE_LABELS)
    artifacts = ", ".join(ARTIFACT_LABELS)

    task_ctx_parts: List[str] = []
    if sections.get("repo"):
        task_ctx_parts.append(f"REPOSITORY: {sections['repo']}")
    if sections.get("misc"):
        task_ctx_parts.append(f"METADATA:\n{sections['misc']}")
    if sections.get("problem"):
        task_ctx_parts.append(f"PROBLEM STATEMENT / ISSUE:\n{sections['problem']}")
    if sections.get("patch"):
        task_ctx_parts.append(f"GOLDEN PATCH (the reference fix):\n{sections['patch']}")
    if sections.get("tests"):
        task_ctx_parts.append(f"TESTS / VERIFIER (signal only):\n{sections['tests']}")
    task_ctx = "\n\n".join(task_ctx_parts) or "(no task content found)"

    return f"""Classify the following coding task.

# TAXONOMY (category -> subcategories)
{taxonomy_block}

# CANDIDATE LANGUAGES
{langs}

# OBJECTIVE LABELS (multi-label; assign all that apply to the end goal)
{objectives}

# ARTIFACT LABELS (multi-label; assign all that apply to the central artifacts)
{artifacts}

# LANGUAGE HINT (derived from file extensions in the patch - a hint, not ground truth)
{lang_hint}

# TASK CONTENT
{task_ctx}

# INSTRUCTIONS
1. Score EVERY one of the 11 categories with a confidence in [0.0, 1.0] reflecting how
   well it matches the dominant engineering work. Scores need not sum to 1.
2. For EVERY category, list its TOP 3 subcategories (chosen only from that category's
   own subcategory list above) each with a confidence in [0.0, 1.0].
3. Score the candidate languages that plausibly apply (0.0-1.0). Pick from the CANDIDATE
   LANGUAGES list exactly as written. If the language is not in the list, still use the
   closest listed grouping (e.g. TypeScript -> "JavaScript / TypeScript").
4. Assign the objective labels and artifact labels that genuinely apply (multi-label).
5. Give a 1-3 sentence rationale for the top category/subcategory choice.

Respond with ONLY this JSON object (no markdown, no prose, no code fences):
{{
  "categories": {{ "<category name>": <score>, ... all 11 categories ... }},
  "subcategories": {{
    "<category name>": [
      {{"name": "<subcategory>", "score": <score>}},
      {{"name": "<subcategory>", "score": <score>}},
      {{"name": "<subcategory>", "score": <score>}}
    ],
    ... one entry per category ...
  }},
  "languages": {{ "<language>": <score>, ... }},
  "objective_labels": ["<label>", ...],
  "artifact_labels": ["<label>", ...],
  "rationale": "<1-3 sentences>"
}}
"""


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------
def call_llm(system: str, user: str, model: str, max_tokens: int = 4096) -> str:
    try:
        import anthropic
    except ImportError:
        sys.exit("The 'anthropic' package is required: pip install anthropic")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY is not set (env var or .env file).")

    client = anthropic.Anthropic(api_key=api_key)
    kwargs: Dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    # Prefer temperature=0 for determinism, but some newer models reject sampling
    # params - fall back to a call without temperature on a 400.
    try:
        resp = client.messages.create(temperature=0, **kwargs)
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "temperature" in msg or "sampling" in msg or "unexpected" in msg or "400" in msg:
            resp = client.messages.create(**kwargs)
        else:
            sys.exit(f"Anthropic API call failed: {exc}")

    parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    return "".join(parts).strip()


def extract_json(text: str) -> Dict[str, Any]:
    """Robustly pull the first JSON object out of an LLM response."""
    text = text.strip()
    # Strip code fences if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Scan for a balanced top-level object.
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in model response.")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("Could not extract a balanced JSON object from model response.")


# ---------------------------------------------------------------------------
# Canonicalization + final decision
# ---------------------------------------------------------------------------
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _match_to_list(value: str, options: List[str]) -> Optional[str]:
    if not value:
        return None
    nv = _norm(value)
    for opt in options:
        if _norm(opt) == nv:
            return opt
    # substring containment either direction
    for opt in options:
        no = _norm(opt)
        if nv and (nv in no or no in nv):
            return opt
    return None


def _coerce_score(v: Any) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, f))


def canonicalize(raw: Dict[str, Any]) -> Dict[str, Any]:
    # Categories -> keep only valid canonical names.
    categories: Dict[str, float] = {}
    for k, v in (raw.get("categories") or {}).items():
        canon = _match_to_list(str(k), list(TAXONOMY.keys()))
        if canon:
            categories[canon] = max(categories.get(canon, 0.0), _coerce_score(v))
    for cat in TAXONOMY:
        categories.setdefault(cat, 0.0)

    # Subcategories -> validate each belongs to its category; keep top 3.
    subcategories: Dict[str, List[Dict[str, Any]]] = {}
    raw_subs = raw.get("subcategories") or {}
    for cat, subs in TAXONOMY.items():
        entries = raw_subs.get(cat)
        if entries is None:
            # try fuzzy category key match
            for k, v in raw_subs.items():
                if _match_to_list(str(k), list(TAXONOMY.keys())) == cat:
                    entries = v
                    break
        scored: Dict[str, float] = {}
        if isinstance(entries, list):
            for e in entries:
                if isinstance(e, dict):
                    name, score = e.get("name") or e.get("subcategory"), e.get("score")
                elif isinstance(e, (list, tuple)) and len(e) == 2:
                    name, score = e[0], e[1]
                else:
                    name, score = e, None
                canon = _match_to_list(str(name), subs) if name else None
                if canon:
                    scored[canon] = max(scored.get(canon, 0.0), _coerce_score(score))
        elif isinstance(entries, dict):
            for name, score in entries.items():
                canon = _match_to_list(str(name), subs)
                if canon:
                    scored[canon] = max(scored.get(canon, 0.0), _coerce_score(score))
        top3 = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)[:3]
        subcategories[cat] = [{"name": n, "score": s} for n, s in top3]

    # Languages -> canonical.
    languages: Dict[str, float] = {}
    for k, v in (raw.get("languages") or {}).items():
        canon = _match_to_list(str(k), LANGUAGES)
        if canon:
            languages[canon] = max(languages.get(canon, 0.0), _coerce_score(v))

    objective_labels = [
        m for m in (_match_to_list(str(x), OBJECTIVE_LABELS)
                    for x in (raw.get("objective_labels") or [])) if m
    ]
    artifact_labels = [
        m for m in (_match_to_list(str(x), ARTIFACT_LABELS)
                    for x in (raw.get("artifact_labels") or [])) if m
    ]
    # dedupe preserving order
    objective_labels = list(dict.fromkeys(objective_labels))
    artifact_labels = list(dict.fromkeys(artifact_labels))

    # ---- Final decision ----
    best_cat = max(categories.items(), key=lambda kv: kv[1])[0] if categories else None
    best_sub = None
    if best_cat and subcategories.get(best_cat):
        best_sub = subcategories[best_cat][0]["name"]
    best_lang = None
    if languages:
        best_lang = max(languages.items(), key=lambda kv: kv[1])[0]

    return {
        "categories": dict(sorted(categories.items(), key=lambda kv: kv[1], reverse=True)),
        "subcategories": subcategories,
        "languages": dict(sorted(languages.items(), key=lambda kv: kv[1], reverse=True)),
        "objective_labels": objective_labels,
        "artifact_labels": artifact_labels,
        "final_decision": {
            "category": best_cat,
            "subcategory": best_sub,
            "language": best_lang,
        },
        "rationale": str(raw.get("rationale", "")).strip(),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tag a SWE-Bench-style / Harbor task with category, subcategory, "
                    "and language using an LLM judge.",
    )
    parser.add_argument("task", help="Path to a Harbor task folder, SWE-Bench JSON file, "
                                     "or a problem-statement text/markdown file.")
    parser.add_argument("--output", "-o", help="Write result JSON to this file "
                                                "(default: stdout).")
    parser.add_argument("--model", default=os.environ.get("TAG_TASK_MODEL", DEFAULT_MODEL),
                        help=f"Anthropic model id (default: {DEFAULT_MODEL}).")
    parser.add_argument("--env-file", help="Explicit path to a .env file with "
                                            "ANTHROPIC_API_KEY.")
    parser.add_argument("--max-tokens", type=int, default=4096,
                        help="Max output tokens for the LLM call.")
    parser.add_argument("--print-prompt", action="store_true",
                        help="Print the assembled prompt and exit (no API call).")
    args = parser.parse_args()

    task_path = Path(args.task).expanduser()
    if not task_path.exists():
        sys.exit(f"Task path does not exist: {task_path}")

    load_env_file(args.env_file, [task_path if task_path.is_dir() else task_path.parent,
                                  Path(__file__).parent, Path.cwd()])

    sections = load_task(task_path)
    if not any(sections.get(k) for k in ("problem", "patch", "tests")):
        sys.exit(f"Could not extract any task content from: {task_path}")

    lang_hint = language_hint(sections)
    user_prompt = build_user_prompt(sections, lang_hint)

    if args.print_prompt:
        print(SYSTEM_PROMPT)
        print("\n" + "=" * 80 + "\n")
        print(user_prompt)
        return 0

    raw_text = call_llm(SYSTEM_PROMPT, user_prompt, args.model, args.max_tokens)
    try:
        raw = extract_json(raw_text)
    except ValueError as exc:
        sys.stderr.write(f"Failed to parse model output as JSON: {exc}\n")
        sys.stderr.write("--- raw model output ---\n" + raw_text + "\n")
        return 2

    result = canonicalize(raw)
    result["_meta"] = {
        "task_path": str(task_path),
        "model": args.model,
        "language_hint": lang_hint,
    }

    out = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).expanduser().write_text(out + "\n", encoding="utf-8")
        fd = result["final_decision"]
        sys.stderr.write(
            f"Wrote {args.output}\n  category    = {fd['category']}\n"
            f"  subcategory = {fd['subcategory']}\n  language    = {fd['language']}\n"
        )
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
