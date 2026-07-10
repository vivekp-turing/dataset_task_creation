from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent

from swebench_like_gen.grading_test_extractor import GradingTestsOutput
from swebench_like_gen.harbor_loader import HarborTask


class PerTestVerdict(BaseModel):
    test_name: str
    in_spec: bool
    in_hints: bool
    tests_good: bool
    verdict: Literal["Fair", "Unfair"]
    notes: str


class FairnessOutput(BaseModel):
    per_test_verdicts: list[PerTestVerdict]
    overall_verdict: Literal["Fair", "Unfair"]
    summary: str


class RubricEntry(BaseModel):
    score: int
    label: str
    reasoning: str


class TestAlignmentEntry(RubricEntry):
    failure_test_case: str = ""
    failure_category: str = ""


class AnnotationOutput(BaseModel):
    issue_clarity: RubricEntry
    gold_patch_clarity: RubricEntry
    gold_patch_to_issue_alignment: RubricEntry
    test_clarity: RubricEntry
    test_to_issue_alignment: TestAlignmentEntry
    fairness: RubricEntry
    instruction_leakage: RubricEntry
    test_robustness: RubricEntry
    is_hint_needed: bool
    hint_reasoning: str
    hint_value: str


@dataclass(frozen=True)
class AnnotationResult:
    verdict: str
    score: float
    rejection_reasons: list[str]
    fairness: FairnessOutput
    annotation: AnnotationOutput
    summary_markdown: str


FAIRNESS_SYSTEM_PROMPT = """\
You are an expert evaluator assessing whether a sourced software task is fair for engineers to solve.

You are given:
- A public instruction/problem statement describing the issue
- Optional hints that engineers receive alongside the issue
- The extracted fail-to-pass (F2P) test names/selectors that must pass for the task to be considered solved
- The extracted pass-to-pass (P2P) regression tests/selectors as context
- The gold patch (reference solution)
- The hidden test patch (test implementation, if available)
- The verifier script used by the Harbor task to apply and run the hidden tests

For each F2P test, decide whether it is **Fair** or **Unfair**:
- **Fair**: an engineer could reasonably implement a solution that passes this test given only the
  public instruction, hints, and source code — without access to the gold patch or hidden test implementation
- **Unfair**: the test asserts behaviour not described in the public instruction or hints, or pins
  internal implementation details an engineer cannot reasonably infer

For each verdict also note:
- `in_spec`: is the tested requirement explicitly stated in the public instruction?
- `in_hints`: is the tested requirement covered or inferable from the hints?
- `tests_good`: is the test itself well-formed, focused, and not relying on magic values or internals?

## Classification rules

### UNFAIR when (tag each verdict with one of these):
- Spec gap: the tested requirement is completely absent from the public instruction and hints
- Ambiguous spec: the problem area is mentioned but too vague; the test enforces one interpretation
- Test too coupled to implementation: asserts an internal detail only visible in the gold patch
- Test contradicts spec: enforces behaviour that contradicts what the public instruction states
- Hidden requirement: the feature tested is not mentioned in the public interface or public instruction
- Test quality flaw: malformed, hard-codes magic values not in the spec, or asserts internals

### FAIR when:
1. The public instruction explicitly states the requirement the test checks
2. The test checks observable public behaviour any correct implementation must satisfy
3. The return type, field name, error message, or specific value is visible in the public instruction
4. Standard coding practice (error handling, status codes, empty returns)
5. The requirement is covered or reasonably inferable from the hints

### THRESHOLD (BINARY — overall is ALWAYS exactly Fair or Unfair):
- ALL F2P tests Fair → Overall: Fair
- ONE OR MORE F2P tests Unfair → Overall: Unfair
- If there are no F2P tests, set per_test_verdicts to an empty list and overall_verdict to 'Unfair'
  with summary explaining there are no tests to validate.
"""


ANNOTATION_SYSTEM_PROMPT = """\
You are an expert AI judge scoring a sourced software task on eight quality rubrics.
Lower scores are better (0 = best, 3 = worst).

These rubrics encode the task-quality bar for this dataset: tasks must be fair,
clearly specified without leaking the solution, and guarded by a comprehensive,
reward-hacking-resistant test suite (the target is ~10-20 fail-to-pass tests that
verify observable behaviour).

You are given the public instruction/problem statement, hints, gold patch, hidden test patch,
extracted F2P/P2P tests, the Harbor verifier script, and a fairness analysis summary from a prior
evaluation step.

**1. ISSUE CLARITY** (0-3): How clear is the public instruction/problem statement?
- 0 = Clear: success criteria and expected behaviour explicit.
- 1 = Mostly Clear: some gaps but a sensible fix is still inferable.
- 2 = Vague: success criteria missing or ambiguous.
- 3 = Extremely Unclear: unsolvable without major external information.

Strict rules (first match wins):
- Issue body does NOT explicitly describe expected behaviour → score ≥ 2.
- Motivation / screenshots / links only → score == 2.
- Crash log with guessable fix → score == 1.
- Nothing actionable → score == 3.

Reasoning must cite specific evidence from the public instruction: quote or name the concrete
requirements, acceptance criteria, field names, component names, or expected behaviours that
drove the score. Do not write generic observations like "the issue is clear" without
identifying what specifically makes it clear or unclear.

**2. GOLD PATCH CLARITY** (0-3): Is the reference solution readable?
- 0 = Clear: clean, focused, easy to follow.
- 1 = Understandable: takes effort but figurable.
- 2 = Vague: hard to follow, poor structure.
- 3 = Unclear: unreadable.

Reasoning must name specific files, classes, or functions from the gold patch and explain
what makes them clear or hard to follow. Do not write generic observations like "the patch
is well-structured" without referencing what you actually saw.

**3. GOLD PATCH ↔ ISSUE ALIGNMENT** (0-3): Does the gold patch match the problem?
- 0 = Aligned: fully and exactly addresses the issue, nothing extra.
- 1 = Over-scoped: solves the issue but adds non-essential changes.
- 2 = Under-scoped: only partially addresses the issue.
- 3 = Non-atomic: doesn't address the issue, bundles unrelated changes, or
  chains multiple unrelated sub-tasks into one (a "bad difficult task").

Reasoning must connect specific requirements stated in the issue to specific changes in
the patch. If over/under-scoped, name the extra or missing change explicitly.

**4. TEST CLARITY** (0-3): Are the tests understandable and free of hidden assertions?
- 0 = Clear: focused, well-named, intent obvious.
- 1 = Understandable: weak naming but readable.
- 2 = Vague: confusing setup, poor naming, or hidden assertions.
- 3 = Unclear: unreadable noise.

Reasoning must name at least one specific test function, test class, or verifier selector from
the hidden test patch and explain what makes it clear or problematic.

**5. TEST ↔ ISSUE ALIGNMENT** (0-3): Do the F2P tests correctly validate what the issue requires?
- 0 = Comprehensive: tests directly check the exact behaviour the issue requires.
- 1 = Mostly Comprehensive: tests cover the majority of correct solutions.
- 2 = Partial: tests work but some valid implementations may be missed (False Negative) or
  the tests are too lenient (False Positive).
- 3 = Out-of-scope: tests check something unrelated to the issue.

Strict rules for TEST ↔ ISSUE ALIGNMENT (first match wins):
- Tests do NOT exercise the main behaviour described in the issue → score == 3.
- Tests would PASS for a solution that does not actually fix the issue → lean toward 3.
- Tests over-specify beyond issue scope but still validate the fix → score == 2.

For test_to_issue_alignment provide failure_test_case (specific test id when score ≥ 2, else "")
and failure_category ("False Negative" or "False Positive" when score == 2, else "").

Reasoning must reference at least one specific F2P test name/selector and explain what behaviour it
validates relative to the issue. If misaligned, name the specific test and what it checks
vs. what the issue actually requires.

**6. FAIRNESS** (0-3): Is this task solvable without privileged information?
- 0 = Fair: all tests are clearly grounded in the spec/hints; solvable from public information.
- 1 = Minor concerns: some tests have slight ambiguity but task is generally fair.
- 2 = Significant concerns: multiple tests require knowledge not present in spec or hints.
- 3 = Unfair: task cannot reasonably be solved from the given information alone.

Reasoning must address the F2P tests by name. For each test (or at minimum the key ones),
state whether it is fair or unfair and briefly explain why — e.g. what specific behaviour
it asserts and whether that behaviour is present in the public instruction or hints.

**7. INSTRUCTION LEAKAGE** (0-3): Does the public instruction over-specify or leak the solution?
The problem statement must describe the problem/expected behaviour, NOT how to implement the
fix, and must not leak anything about the hidden tests.
- 0 = Clean: states expected behaviour only; no fix, files, algorithm, or test details leaked.
- 1 = Minor leak: mild over-specification (e.g. gently points at an area) but the core
  engineering work is still left to the solver.
- 2 = Significant leak: reveals the file(s) to edit ("Where to look: ..."), the root cause,
  the intended fix, or the algorithm to apply; or references hidden test names/assertions.
- 3 = Solution disclosed: effectively hands over the solution or the hidden test expectations,
  reducing the task to transcription.

Exception: information that was genuinely present in the ORIGINAL upstream issue is allowed
(PR/commit/issue-sourced tasks may legitimately quote the original report). Do not penalise
clarifications of test assumptions or edge cases — those are reasonable and encouraged.

Strict rules (first match wins):
- Names the specific source file(s)/function to change when the issue did not → score >= 2.
- States the root cause or the intended fix/algorithm not present in the original issue → score >= 2.
- Reveals hidden test names, assertions, or expected magic values → score == 3.

Reasoning must quote the specific leaking sentence/phrase from the instruction (or confirm none
exists) and say whether it was plausibly in the original issue.

**8. TEST ROBUSTNESS** (0-3): Are the F2P tests comprehensive and resistant to reward hacking?
Tests must verify observable behaviour by executing code, be hard to game, and be independent of
the reference solution. The dataset target is a comprehensive suite (~10-20 F2P tests).
- 0 = Robust: comprehensive behavioural coverage, includes a regression that reproduces the
  issue, executes real code paths, and cannot be passed by special-casing or hardcoding.
- 1 = Adequate: mostly behavioural and reasonably comprehensive, minor coverage gaps.
- 2 = Weak: too few tests for the scope, thin coverage, or partially gameable (e.g. asserts a
  single easy value) so a non-fix could plausibly pass.
- 3 = Hackable/structural: checks patch structure, diff text, line numbers, or source keywords
  instead of behaviour; depends on / imports the reference solution; or is trivially gameable.

Strict rules (first match wins):
- Tests assert on diff/patch structure, file names, or source-code keyword matching rather than
  runtime behaviour → score == 3.
- Tests call, import, or compare against the reference solution or solution-only artifacts → score == 3.
- A single narrow assertion guards a multi-part behavioural change (reward-hacking risk) → score >= 2.
- Coverage is materially thinner than the behaviours the issue requires → score >= 2.

Reasoning must reference specific tests and state (a) roughly how many F2P tests exist vs. the
behaviours required, (b) whether a regression test reproducing the issue is present, and
(c) whether any assertion is structural/gameable or solution-dependent.

**HINT ASSESSMENT**: After scoring, assess whether engineers need an additional hint:
- `is_hint_needed`: true if the task has clarity gaps that a targeted hint could remedy
- `hint_reasoning`: cite the specific test, the source-file change it depends on, and
  why that information is absent from the public instruction or hints; if no hint is needed,
  briefly confirm what makes the public information sufficient
- `hint_value`: the exact text of the recommended hint (meaningful only when is_hint_needed=true;
  leave empty string otherwise)
"""


REJECT_SCORE_THRESHOLD = 2
REJECT_COUNT_THRESHOLD = 2
ALIGNMENT_HARD_GATE = 1
GATE_LINES = (
    "Any single rubric score >= 2.",
    "Two or more rubric scores >= 1.",
    "Gold Patch ↔ Issue Alignment >= 1.",
    "Test Clarity >= 2.",
    "Test ↔ Issue Alignment >= 2.",
    "Fairness analysis determined task is Unfair.",
    "Instruction Leakage >= 2 (solution/files/tests leaked).",
    "Test Robustness >= 2 (thin or reward-hackable tests).",
)
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def build_fairness_prompt(task: HarborTask, grading: GradingTestsOutput) -> str:
    f2p = format_grading_tests(grading.fail_to_pass)
    p2p = format_grading_tests(grading.pass_to_pass)
    unknown = format_grading_tests(grading.unknown)
    return "\n\n".join(
        [
            f"Task: {task.instance_id}",
            f"Repository: {task.repo}",
            f"Language: {task.language}",
            f"=== PUBLIC INSTRUCTION ===\n{task.instruction}",
            "=== HINTS ===\n(none provided)",
            f"=== EXTRACTED FAIL_TO_PASS TESTS ===\n{f2p}",
            f"=== EXTRACTED PASS_TO_PASS TESTS ===\n{p2p}",
            f"=== UNKNOWN TESTS/SELECTORS FROM EXTRACTION ===\n{unknown}",
            f"=== GRADING TEST EXTRACTION SUMMARY ===\n{grading.summary}",
            f"=== GOLD PATCH ===\n{task.gold_patch}",
            f"=== HIDDEN TEST PATCH ===\n{task.test_patch}",
            f"=== VERIFIER SCRIPT ===\n{task.test_script}",
            "Evaluate fairness for each extracted FAIL_TO_PASS test.",
        ]
    )


def build_annotation_prompt(
    task: HarborTask, grading: GradingTestsOutput, fairness_summary: str
) -> str:
    return "\n\n".join(
        [
            f"Task: {task.instance_id}",
            f"Repository: {task.repo}",
            f"Language: {task.language}",
            f"Category: {task.category}"
            + (f" / {task.subcategory}" if task.subcategory else ""),
            f"Source type: {task.source_type or '(unspecified)'} "
            "(PR/commit/issue-sourced tasks may legitimately quote the original "
            "upstream issue; net-new tasks have no upstream issue to quote)",
            f"Declared fail-to-pass test count (task.toml num_f2p_tests): "
            f"{task.num_f2p_tests or '(unspecified)'} — dataset target is ~10-20",
            f"=== PUBLIC INSTRUCTION ===\n{task.instruction}",
            "=== HINTS ===\n(none provided)",
            f"=== EXTRACTED FAIL_TO_PASS TESTS ===\n{format_grading_tests(grading.fail_to_pass)}",
            f"=== EXTRACTED PASS_TO_PASS TESTS ===\n{format_grading_tests(grading.pass_to_pass)}",
            f"=== UNKNOWN TESTS/SELECTORS FROM EXTRACTION ===\n{format_grading_tests(grading.unknown)}",
            f"=== GOLD PATCH ===\n{task.gold_patch}",
            f"=== HIDDEN TEST PATCH ===\n{task.test_patch}",
            f"=== VERIFIER SCRIPT ===\n{task.test_script}",
            f"=== PRIOR FAIRNESS ANALYSIS ===\n{fairness_summary or '(not available)'}",
            "Score this task on the six rubrics and assess the hint requirement.",
        ]
    )


def format_grading_tests(tests: list) -> str:
    if not tests:
        return "(none)"
    lines = []
    for test in tests:
        parts = [test.name]
        if test.file:
            parts.append(f"file={test.file}")
        if test.selector:
            parts.append(f"selector={test.selector}")
        parts.append(f"confidence={test.confidence}")
        parts.append(f"evidence={test.evidence}")
        lines.append("- " + " | ".join(parts))
    return "\n".join(lines)


def rubric_scores(annotation: AnnotationOutput) -> list[int]:
    return [
        annotation.issue_clarity.score,
        annotation.gold_patch_clarity.score,
        annotation.gold_patch_to_issue_alignment.score,
        annotation.test_clarity.score,
        annotation.test_to_issue_alignment.score,
        annotation.fairness.score,
        annotation.instruction_leakage.score,
        annotation.test_robustness.score,
    ]


def annotation_decision(
    annotation: AnnotationOutput, fairness_verdict: str
) -> tuple[str, list[str]]:
    scores = rubric_scores(annotation)
    reasons: list[str] = []
    if any(score >= REJECT_SCORE_THRESHOLD for score in scores):
        reasons.append(GATE_LINES[0])
    if sum(1 for score in scores if score >= 1) >= REJECT_COUNT_THRESHOLD:
        reasons.append(GATE_LINES[1])
    if annotation.gold_patch_to_issue_alignment.score >= ALIGNMENT_HARD_GATE:
        reasons.append(GATE_LINES[2])
    if annotation.test_clarity.score >= REJECT_SCORE_THRESHOLD:
        reasons.append(GATE_LINES[3])
    if annotation.test_to_issue_alignment.score >= REJECT_SCORE_THRESHOLD:
        reasons.append(GATE_LINES[4])
    if fairness_verdict == "Unfair":
        reasons.append(GATE_LINES[5])
    if annotation.instruction_leakage.score >= REJECT_SCORE_THRESHOLD:
        reasons.append(GATE_LINES[6])
    if annotation.test_robustness.score >= REJECT_SCORE_THRESHOLD:
        reasons.append(GATE_LINES[7])
    return ("reject" if reasons else "accept", reasons)


def rubric_score(annotation: AnnotationOutput) -> float:
    scores = rubric_scores(annotation)
    mean_0_3 = sum(scores) / len(scores)
    return round((1 - mean_0_3 / 3) * 5, 1)


def render_fairness_report(output: FairnessOutput, task_label: str) -> str:
    lines = [
        f"## Fairness Report — {task_label}",
        f"**Overall:** {output.overall_verdict}",
        f"**Summary:** {output.summary}",
    ]
    if output.per_test_verdicts:
        lines += [
            "",
            "| Test | In Spec? | In Hints? | Tests Good? | Verdict | Notes |",
            "|------|----------|-----------|-------------|---------|-------|",
        ]
        for test in output.per_test_verdicts:
            lines.append(
                f"| `{test.test_name}` | {'Yes' if test.in_spec else 'No'} "
                f"| {'Yes' if test.in_hints else 'No'} "
                f"| {'Yes' if test.tests_good else 'No'} | **{test.verdict}** | {test.notes} |"
            )
    return "\n".join(lines)


def render_annotation_report(
    annotation: AnnotationOutput,
    task_label: str,
    final_verdict: str,
    rejection_reasons: list[str],
    score: float,
) -> str:
    entries = {
        "Issue Clarity": annotation.issue_clarity,
        "Gold Patch Clarity": annotation.gold_patch_clarity,
        "Gold Patch ↔ Issue Alignment": annotation.gold_patch_to_issue_alignment,
        "Test Clarity": annotation.test_clarity,
        "Test ↔ Issue Alignment": annotation.test_to_issue_alignment,
        "Fairness": annotation.fairness,
        "Instruction Leakage": annotation.instruction_leakage,
        "Test Robustness": annotation.test_robustness,
    }
    lines = [
        f"## Annotation Rubrics — {task_label}",
        f"**Verdict:** {final_verdict.capitalize()}  |  **Quality Score:** {score}/5",
    ]
    if rejection_reasons:
        lines += ["", "**Rejection reasons:**"]
        lines += [f"- {reason}" for reason in rejection_reasons]
    lines += [
        "",
        "| Rubric | Score | Label | Reasoning |",
        "|--------|-------|-------|-----------|",
    ]
    for name, entry in entries.items():
        lines.append(
            f"| {name} | {entry.score}/3 | {entry.label} | {entry.reasoning} |"
        )
    if annotation.is_hint_needed:
        lines += [
            "",
            f"**Hint needed:** Yes — {annotation.hint_reasoning}",
            f"**Suggested hint:** {annotation.hint_value}",
        ]
    else:
        lines += ["", f"**Hint needed:** No — {annotation.hint_reasoning}"]
    return "\n".join(lines)


class AiAnnotationService:
    def __init__(self, model: str) -> None:
        self.model = model

    def run(self, task: HarborTask, grading: GradingTestsOutput) -> AnnotationResult:
        fairness = self.run_fairness(task, grading)
        annotation = self.run_annotation(task, grading, fairness)
        final_verdict, rejection_reasons = annotation_decision(
            annotation, fairness.overall_verdict
        )
        score = rubric_score(annotation)
        fairness_report = render_fairness_report(fairness, task.instance_id)
        annotation_report = render_annotation_report(
            annotation, task.instance_id, final_verdict, rejection_reasons, score
        )
        return AnnotationResult(
            verdict=final_verdict,
            score=score,
            rejection_reasons=rejection_reasons,
            fairness=fairness,
            annotation=annotation,
            summary_markdown=f"{fairness_report}\n\n---\n\n{annotation_report}",
        )

    def run_fairness(
        self, task: HarborTask, grading: GradingTestsOutput
    ) -> FairnessOutput:
        agent = Agent(
            model=self.model,
            output_type=FairnessOutput,
            system_prompt=FAIRNESS_SYSTEM_PROMPT,
        )
        return agent.run_sync(build_fairness_prompt(task, grading)).output

    def run_annotation(
        self, task: HarborTask, grading: GradingTestsOutput, fairness: FairnessOutput
    ) -> AnnotationOutput:
        agent = Agent(
            model=self.model,
            output_type=AnnotationOutput,
            system_prompt=ANNOTATION_SYSTEM_PROMPT,
        )
        return agent.run_sync(
            build_annotation_prompt(task, grading, fairness.summary)
        ).output
