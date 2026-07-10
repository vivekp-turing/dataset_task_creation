from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent

from swebench_like_gen.harbor_loader import HarborTask


class GradingTest(BaseModel):
    name: str
    file: str = ""
    selector: str = ""
    category: Literal["fail_to_pass", "pass_to_pass", "unknown"]
    confidence: Literal["high", "medium", "low"]
    evidence: str


class GradingTestsOutput(BaseModel):
    fail_to_pass: list[GradingTest]
    pass_to_pass: list[GradingTest]
    unknown: list[GradingTest]
    summary: str


GRADING_TEST_SYSTEM_PROMPT = """\
You extract FAIL_TO_PASS and PASS_TO_PASS grading tests from SWE-bench-like Harbor tasks.

Context:
- The task starts from a base commit.
- An agent receives the public instruction and edits source code.
- The verifier restores hidden tests, applies tests/test_patch.diff, then runs tests/test.sh.
- FAIL_TO_PASS tests are grading tests expected to fail on the base commit and pass after the correct fix.
- PASS_TO_PASS tests are regression or guard tests expected to pass before and after the fix.
- tests/test.sh comments often identify fail2pass/pass2pass sets directly.
- tests/test_patch.diff contains hidden grading tests. New tests added by the patch are often FAIL_TO_PASS.
- Existing suites/selectors named in test.sh are often PASS_TO_PASS guards.

Task:
Classify the grading tests/selectors into fail_to_pass, pass_to_pass, and unknown.
Prefer concrete test names when visible. If the verifier uses a pattern or suite selector, preserve that selector.
Use unknown instead of guessing when evidence is weak.
Every item must include concise evidence citing test.sh comments, verifier selectors, or test_patch.diff contents.
"""


def build_grading_test_prompt(task: HarborTask) -> str:
    return "\n\n".join(
        [
            f"Task slug: {task.task_slug}",
            f"Instance ID: {task.instance_id}",
            f"Repository: {task.repo}",
            f"Language: {task.language}",
            f"Category: {task.category}",
            f"=== PUBLIC INSTRUCTION ===\n{task.instruction}",
            f"=== VERIFIER SCRIPT: tests/test.sh ===\n{task.test_script}",
            f"=== HIDDEN TEST PATCH: tests/test_patch.diff ===\n{task.test_patch}",
            "Return structured FAIL_TO_PASS, PASS_TO_PASS, and UNKNOWN test/selectors for this task.",
        ]
    )


class GradingTestExtractor:
    def __init__(self, model: str) -> None:
        self.model = model

    def run(self, task: HarborTask) -> GradingTestsOutput:
        agent = Agent(
            model=self.model,
            output_type=GradingTestsOutput,
            system_prompt=GRADING_TEST_SYSTEM_PROMPT,
        )
        return agent.run_sync(build_grading_test_prompt(task)).output
