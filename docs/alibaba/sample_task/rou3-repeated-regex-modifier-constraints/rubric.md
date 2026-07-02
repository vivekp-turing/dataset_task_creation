# Rubric

Scores are 1 to 5. A score of 3 is the lowest passing score. The automated verifier and this rubric define the same correctness target.

## Correctness - 35%

- Fully implements the requested behavior across the normal and adversarial cases described in the prompt.
- Preserves existing behavior covered by the original project tests.
- Rejects partial fixes that only satisfy the easiest visible case.

## Code Quality - 25%

- Keeps the change localized to the relevant subsystem without broad rewrites.
- Follows the style, naming, and abstractions already used by the project.
- Avoids hardcoding verifier inputs or one-off special cases.

## Reasoning - 15%

- Identifies the real behavioral invariant instead of patching symptoms.
- Explains edge cases and why plausible wrong fixes are insufficient.

## Efficiency - 15%

- Uses the smallest relevant test/build commands while iterating.
- Avoids scanning or rebuilding unrelated parts of the repository when focused checks are available.

## Tool Usage - 10%

- Uses code search, tests, and subagents/tooling where appropriate for the selected dimensions.
- Maintains a clean workspace and validates the final solution with the verifier.

## Task-specific focus

Bucket: `compatibility-fix` / `Backend`.

Router grammar behavior spans parser, compiled matcher, and find-all paths with plausible partial fixes.

## Task-specific scoring points

### Correctness

- Implements the behavior requested in `instruction.md` for this exact codebase, not just the simplest visible case.
- Preserves the existing public behavior that the original project tests already covered.
- Handles the edge cases implied by this task's bucket and focus: Router grammar behavior spans parser, compiled matcher, and find-all paths with plausible partial fixes.

### Code Quality

- Uses the project's existing abstractions and style instead of broad rewrites.
- Keeps the solution maintainable for future changes in the same subsystem.
- Avoids hardcoded values that only satisfy the sample verifier.

### Reasoning

- Identifies the underlying invariant or missing branch that makes the task difficult.
- Explains why plausible partial fixes would still fail important cases.
- Connects the implementation change to the public behavior requested in the prompt.

### Efficiency

- Uses focused project tests and targeted code search before running broader checks.
- Avoids unnecessary dependency, build-system, or formatting churn.

### Tool Usage

- Uses the available shell, search, and test tools to inspect the relevant subsystem.
- Uses subagents or structured decomposition when the selected Alibaba dimensions call for it.
