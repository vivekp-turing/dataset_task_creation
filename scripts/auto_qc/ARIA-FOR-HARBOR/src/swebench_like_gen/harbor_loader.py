from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class HarborLoaderError(Exception):
    """Raised when a Harbor task directory cannot be loaded."""


# Matches a shell heredoc body: `<< 'MARKER' ... MARKER`. Used to recover the
# fail2pass/pass2pass test patch that the shipped Harbor format embeds inline in
# tests/test.sh (the tests/ folder may hold only 3 files, so there is often no
# standalone tests/test_patch.diff).
_HEREDOC_RE = re.compile(
    r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*\n(.*?)\n\1\b",
    re.DOTALL,
)

# Languages the loader can recognise from task.toml keywords/tags. Generic
# keywords like "code"/"swe" are intentionally excluded so they never win.
KNOWN_LANGUAGES = {
    "python",
    "java",
    "javascript",
    "typescript",
    "csharp",
    "c#",
    "c",
    "c++",
    "cpp",
    "rust",
    "go",
    "golang",
    "ruby",
    "php",
    "kotlin",
    "scala",
    "swift",
    "shell",
    "bash",
}


@dataclass(frozen=True)
class HarborTask:
    task_slug: str
    task_dir: Path
    instance_id: str
    repo: str
    base_commit: str
    language: str
    category: str
    subcategory: str
    source_type: str
    difficulty: str
    num_f2p_tests: int
    instruction: str
    test_script: str
    test_patch: str
    gold_patch: str

    @property
    def has_test_patch(self) -> bool:
        return bool(self.test_patch.strip())


def load_harbor_task(task_dir: Path) -> HarborTask:
    resolved = task_dir.expanduser().resolve()
    if not resolved.is_dir():
        msg = f"Harbor task directory does not exist: {task_dir}"
        raise HarborLoaderError(msg)

    task_toml = read_required_text(resolved / "task.toml")
    data = tomllib.loads(task_toml)
    task_data = table(data, "task")
    metadata = table(data, "metadata")

    instruction = load_instruction(resolved)
    test_script = read_required_text(resolved / "tests" / "test.sh")
    test_patch = load_test_patch(resolved, test_script)
    gold_patch = load_gold_patch(resolved)

    keywords = string_list(task_data.get("keywords"))
    tags = string_list(metadata.get("tags"))
    language = detect_language(keywords, tags)

    return HarborTask(
        task_slug=resolved.name,
        task_dir=resolved,
        instance_id=str(task_data.get("name") or resolved.name),
        repo=str(metadata.get("repo") or ""),
        base_commit=str(metadata.get("base_commit") or ""),
        language=language,
        category=str(metadata.get("category") or ""),
        subcategory=str(metadata.get("subcategory") or ""),
        source_type=str(metadata.get("source_type") or ""),
        difficulty=str(metadata.get("difficulty") or ""),
        num_f2p_tests=coerce_int(metadata.get("num_f2p_tests")),
        instruction=instruction,
        test_script=test_script,
        test_patch=test_patch,
        gold_patch=gold_patch,
    )


def load_instruction(task_dir: Path) -> str:
    """Public problem statement.

    The shipped format keeps the agent-facing prompt in instruction.md and a
    mirror in environment/problem_statement.md. Prefer instruction.md; fall back
    to problem_statement.md when instruction.md is absent/empty.
    """
    instruction = read_optional_text(task_dir / "instruction.md")
    if instruction.strip():
        return instruction
    problem_statement = read_optional_text(
        task_dir / "environment" / "problem_statement.md"
    )
    if problem_statement.strip():
        return problem_statement
    msg = (
        "Required Harbor file is missing or empty: "
        f"{task_dir / 'instruction.md'} (and no environment/problem_statement.md)"
    )
    raise HarborLoaderError(msg)


def load_gold_patch(task_dir: Path) -> str:
    """Reference solution patch.

    Shipped format names it solution/golden.patch; older ARIA datasets used
    solution/gold_patch.diff. Support both.
    """
    for name in ("golden.patch", "gold_patch.diff"):
        text = read_optional_text(task_dir / "solution" / name)
        if text.strip():
            return text
    msg = (
        "Required reference solution is missing or empty: expected "
        f"{task_dir / 'solution' / 'golden.patch'} "
        f"or {task_dir / 'solution' / 'gold_patch.diff'}"
    )
    raise HarborLoaderError(msg)


def load_test_patch(task_dir: Path, test_script: str) -> str:
    """Hidden grading (fail2pass/pass2pass) test patch.

    Older datasets shipped a standalone tests/test_patch.diff. The current
    Harbor format embeds the patch inline in tests/test.sh (heredoc) because the
    tests/ folder may hold only grade.py, config.json, and test.sh. Prefer the
    standalone file; otherwise recover the embedded diff from the verifier.
    """
    standalone = read_optional_text(task_dir / "tests" / "test_patch.diff")
    if standalone.strip():
        return standalone
    return extract_embedded_test_patch(test_script)


def extract_embedded_test_patch(test_script: str) -> str:
    """Return the first heredoc body in the verifier that looks like a diff."""
    for _marker, body in _HEREDOC_RE.findall(test_script):
        stripped = body.lstrip()
        if "diff --git" in body or stripped.startswith(("--- ", "+++ ", "diff ")):
            return body
    return ""


def iter_harbor_tasks(dataset_dir: Path) -> list[Path]:
    resolved = dataset_dir.expanduser().resolve()
    if not resolved.is_dir():
        msg = f"Harbor dataset directory does not exist: {dataset_dir}"
        raise HarborLoaderError(msg)
    return sorted(
        path
        for path in resolved.iterdir()
        if path.is_dir() and (path / "task.toml").exists()
    )


def read_optional_text(path: Path) -> str:
    try:
        return path.read_text()
    except OSError:
        return ""


def read_required_text(path: Path) -> str:
    try:
        text = path.read_text()
    except OSError as exc:
        msg = f"Required Harbor file is missing or unreadable: {path}"
        raise HarborLoaderError(msg) from exc
    if not text.strip():
        msg = f"Required Harbor file is empty: {path}"
        raise HarborLoaderError(msg)
    return text


def table(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def coerce_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def detect_language(keywords: list[str], tags: list[str]) -> str:
    """Pick the primary language from task.toml keywords/tags.

    The current keyword convention is ["code", "swe", "<language>", ...], so the
    first keyword is a generic marker rather than the language. Scan keywords
    then tags for the first recognised language; fall back to the first
    non-generic keyword.
    """
    generic = {"code", "swe"}
    for item in keywords + tags:
        lowered = item.lower()
        if lowered in KNOWN_LANGUAGES:
            return lowered
    for item in keywords:
        lowered = item.lower()
        if lowered not in generic:
            return lowered
    return ""
