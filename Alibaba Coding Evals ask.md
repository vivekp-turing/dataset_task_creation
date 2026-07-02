# **20260526-Annotation**

## **Requirements — Benchmark Task Construction**

| IDX | Requirement | Deliverables | Acceptance Criteria |
| :---- | :---- | :---- | :---- |
| 0 | Annotators create tasks on their own, used to evaluate model performance. •   The harder the better. •   Evenly distributed; the goal is to find the model's weak spots (especially weaknesses relative to GLM and Claude). | •   **Task:** ◦   harbor data structure: query, env (codebase, dockerfile), eval (exec-based), plus other required data. ◦   rubrics: ▪   Format: overall spec \+ per-task spec; format reference: [《20260526-Annotation》](https://alidocs.dingtalk.com/i/nodes/Gl6Pm2Db8DMGQKRat9xl5pbOWxLq0Ee4?utm_scene=person_space&iframeQuery=anchorId%3Duu_mpm8xdd2wk5pj3xn3l) ▪   In particular, the correctness part must not conflict with the exec-based part. •   **Trajectory (claudecode) and scores (incl. rubrics):** ◦   claude-opus-4.6 / sonnet-4.6 trajectories ◦   qwen-3.7-max trajectory ◦   glm-5.1 trajectory •   **Meta info:** ◦   Tags: [《\[Public\] taxonomy\_v1》](https://alidocs.dingtalk.com/i/nodes/dpYLaezmVNRMGX56CGALwvEjVrMqPxX6) \+ tech stack ◦   One-sentence description (what this task does, and why it is worth using as an evaluation task). ◦   Difficulty assessment: ▪   The annotator's professional background (which industry, how many years of experience). ▪   How long it would take you to complete this task. ◦   Rubrics and the agreement score of their scoring. •   **Ground-truth answer** | •   The data structure conforms to the harbor format; eval code \+ rubrics can accurately distinguish good answers from bad ones. •   Both the main agent and subagents are required, including system prompt, tools, etc. •   Adequate difficulty and discriminative power: ◦   Difficulty: ▪   20+ turns on average. ▪   claude-opus-4.6's pass rate must not exceed 60%. ▪   Tasks that claude-opus-4.6 fails should fail because the task is hard, not due to external causes such as environment failures. ◦   Discrimination: ▪   The pass-rate gap between qwen-3.7-max and claude-opus-4.6 is ≥ 20%. ▪   The pass-rate gap between claude-sonnet-4.6 and claude-opus-4.6 is ≥ 20%. •   Within each program\_lang × task\_type × application-domain combination, each set contains at most 100 tasks. |
| 1 | The requester proposes the desired evaluation dimensions; annotators create the tasks, used to evaluate model performance. The following dimensions are parallel; prioritize the supply of \[High-priority\] tasks. •   \[High-priority\] Long-horizon tasks: problems the agent may need to work on continuously for 3h+ to solve. •   \[High-priority\] Tasks that strongly require compliance with claude.md. •   \[High-priority\] Tasks requiring web search tools to look up docs and codebases. •   \[High-priority\] Multi-turn user interactions: the user raises progressive requirements, modifies earlier requirements, etc. •   Tasks requiring the use of skills. •   Tasks requiring context management for context compression. •   Tasks requiring the use of MCP. •   Tasks requiring subagents to complete subtasks. •   Tasks requiring custom tools. •   Tasks requiring adherence to coding conventions implicit in the codebase. | — |   |
| 2 | (On hold for now; pending kickoff) The requester provides the tasks: •   Sources may be (1) high-quality tasks from qoder/aone, or (2) tasks rewritten from free-style tasks. •   Each contains at least the query, and may contain an env. Annotators fill in the remaining deliverables: •   especially the rubrics. |   |   |

# **Annotation Guidelines**

## **Rubrics**

•   **Overall spec:**

◦   The following is for reference only and may be adjusted to fit the actual situation.

◦   The overall scale is 5 points; 3 is the borderline score at which a solution is barely acceptable.

 

metadata:  
  name: "code-agent-rubrics"  
  version: "1.0.0"  
  description: "Multi-dimensional rubric scoring criteria for Code Agents"  
  scoring\_scale: 5  \# 1-5 scale  
  supported\_task\_types:  
	\- code\_generation  
	\- bug\_fix  
	\- code\_qa  
	\- refactor  
   
\# \=============================================================================  
\# Scoring dimension definitions  
\# \=============================================================================  
dimensions:  
   
  \# \---------------------------------------------------------------------------  
  \# 1\. Correctness  
  \# \---------------------------------------------------------------------------  
  correctness:  
	name: "Correctness"  
    description: "Whether the final output correctly and completely achieves the task goal"  
    applicable\_to: \[code\_generation, bug\_fix, code\_qa, refactor\]  
	scale:  
  	5:  
    	label: "Excellent"  
        criteria: \>  
          Solves the problem completely and correctly. The code runs and passes all  
      	test cases (including edge cases). The output contains no functional errors.  
  	4:  
    	label: "Good"  
        criteria: \>  
      	Core functionality is correct, but a few edge cases are mishandled or there  
      	are minor omissions that do not affect the main flow.  
  	3:  
    	label: "Pass"  
        criteria: \>  
      	The overall direction is correct and the core logic is basically feasible,  
      	but there are obvious defects that require further changes to reach the  
          expected result.  
  	2:  
    	label: "Insufficient"  
        criteria: \>  
          Partially understood the intent of the problem, but the output contains  
      	major errors or is missing key functionality and cannot be used directly.  
  	1:  
    	label: "Very poor"  
        criteria: \>  
          Completely fails to solve the problem; the output deviates severely from  
          expectations, or the code fails to run/compile.  
    task\_specific\_focus:  
      code\_generation:  
    	\- "Does the generated code implement all requirements?"  
    	\- "Are input validation and edge conditions handled?"  
    	\- "Is it consistent with the project's existing code style and architecture?"  
  	bug\_fix:  
    	\- "Is the bug truly fixed (root cause vs. surface symptom)?"  
    	\- "Does the fix introduce new problems (regression risk)?"  
    	\- "Is the fix precisely scoped, without affecting unrelated code?"  
  	code\_qa:  
    	\- "Is the answer consistent with the code's actual behavior?"  
    	\- "Are the cited code snippets accurate?"  
    	\- "Does it cover all aspects involved in the question?"  
  	refactor:  
    	\- "Is the refactored code fully equivalent to the original code?"  
    	\- "Does it pass the original tests?"  
    	\- "Does it introduce new edge-case issues?"  
   
  \# \---------------------------------------------------------------------------  
  \# 2\. Code Quality  
  \# \---------------------------------------------------------------------------  
  code\_quality:  
	name: "Code Quality"  
    description: "The code's readability, adherence to conventions, and compliance with best practices"  
    applicable\_to: \[code\_generation, bug\_fix, refactor\]  
	scale:  
  	5:  
    	label: "Excellent"  
        criteria: \>  
      	Clear code structure, meaningful and convention-compliant naming, follows  
          project/language coding standards. Appropriate abstraction and  
          modularization, no code smells.  
  	4:  
    	label: "Good"  
        criteria: \>  
          Overall good code quality, reasonable structure, mostly standard naming.  
      	A few areas could be improved, but maintainability is not affected.  
  	3:  
    	label: "Pass"  
        criteria: \>  
      	The code works but has some quality issues: unclear naming, somewhat messy  
          structure, some duplicated code.  
  	2:  
    	label: "Insufficient"  
        criteria: \>  
      	Low code quality: confusing naming, loose structure, lots of duplicated  
      	code, does not follow basic coding conventions.  
  	1:  
    	label: "Very poor"  
        criteria: \>  
      	The code is nearly unmaintainable: no structure, arbitrary naming, follows  
      	no conventions, contains obvious anti-patterns.  
	checklist:  
  	\- "Naming: are variable/function/class names clear, meaningful, and conventional?"  
  	\- "Structure: is the code well organized, with single-responsibility functions/classes?"  
  	\- "Conventions: does it follow the project's existing coding style and language idioms?"  
  	\- "DRY: is unnecessary duplication avoided?"  
  	\- "Security: are there security risks (injection, unvalidated input, etc.)?"  
  	\- "Error handling: is there appropriate exception/error handling?"  
   
  \# \---------------------------------------------------------------------------  
  \# 3\. Reasoning  
  \# \---------------------------------------------------------------------------  
  reasoning:  
	name: "Reasoning"  
    description: "The agent's ability to analyze problems, plan solutions, gather information, and make decisions"  
    applicable\_to: \[code\_generation, bug\_fix, code\_qa, refactor\]  
	scale:  
  	5:  
    	label: "Excellent"  
        criteria: \>  
          Demonstrates excellent problem analysis: accurately understands the essence  
      	of the problem, formulates a clear solution, decomposes subtasks sensibly,  
      	and adjusts strategy effectively when encountering difficulties.  
  	4:  
    	label: "Good"  
        criteria: \>  
      	The analysis is generally clear and reasonable; correctly understands the  
          problem and forms a feasible plan; occasionally some redundant thinking,  
      	but the overall direction is correct.  
  	3:  
    	label: "Pass"  
        criteria: \>  
          Roughly understands the direction of the problem, but the analysis is not  
      	deep enough or is biased; planning is not systematic; sometimes multiple  
          attempts are needed to find the right path.  
  	2:  
    	label: "Insufficient"  
        criteria: \>  
      	Clear misunderstanding of the problem; chaotic or jumpy analysis; plans  
      	lack logic; frequently wastes time in wrong directions.  
  	1:  
    	label: "Very poor"  
        criteria: \>  
      	Fails to understand the essence of the problem; no effective analysis;  
          arbitrary or irrelevant decisions; the entire reasoning process is  
          disordered.  
	checklist:  
  	\- "Problem understanding: accurately grasps the core of the task requirements"  
  	\- "Solution planning: has a clear approach before starting"  
  	\- "Information gathering: proactively collects necessary contextual information"  
  	\- "Hypothesis validation: verifies when facing uncertainty"  
  	\- "Adaptability: adjusts strategy promptly when blocked, instead of blindly retrying"  
   
  \# \---------------------------------------------------------------------------  
  \# 4\. Tool Usage  
  \# \---------------------------------------------------------------------------  
  tool\_usage:  
	name: "Tool Usage"  
    description: "Whether available tools (file read/write, search, terminal, code execution, etc.) are used appropriately and efficiently"  
    applicable\_to: \[code\_generation, bug\_fix, code\_qa, refactor\]  
	scale:  
  	5:  
    	label: "Excellent"  
        criteria: \>  
          Precise tool selection; every call has a clear purpose. Flexibly combines  
          multiple tools to complete the task efficiently, with no redundant or  
          erroneous tool calls.  
  	4:  
    	label: "Good"  
        criteria: \>  
      	Tool usage is generally reasonable and efficient; occasional suboptimal  
          choices that do not affect task completion.  
  	3:  
    	label: "Pass"  
        criteria: \>  
      	Can complete the task with tools, but with unreasonable aspects: choosing  
          unnecessary tools, missing better-suited tools, or making extra calls.  
  	2:  
    	label: "Insufficient"  
        criteria: \>  
          Inefficient tool usage; frequently picks the wrong tool or makes  
          ineffective calls; wastes many steps on tool usage.  
  	1:  
    	label: "Very poor"  
        criteria: \>  
          Barely able to use tools, or uses them entirely incorrectly; cannot  
          effectively leverage the available tools to advance the task.  
	checklist:  
  	\- "Tool selection: is the most suitable tool chosen for each subtask?"  
  	\- "Call efficiency: are repeated and redundant tool calls avoided?"  
  	\- "Parameter accuracy: are tool call parameters correct and complete?"  
  	\- "Result utilization: is the information returned by tools used effectively?"  
  	\- "Error recovery: is the response sensible when tool calls fail?"  
   
  \# \---------------------------------------------------------------------------  
  \# 5\. Efficiency  
  \# \---------------------------------------------------------------------------  
  efficiency:  
	name: "Efficiency"  
    description: "Overall efficiency of completing the task, including number of steps, time utilization, and redundant operations"  
    applicable\_to: \[code\_generation, bug\_fix, code\_qa, refactor\]  
	scale:  
  	5:  
    	label: "Excellent"  
        criteria: \>  
          Completes the task efficiently with the fewest steps, no redundant  
          operations; the path is nearly optimal.  
  	4:  
    	label: "Good"  
        criteria: \>  
      	The path to completing the task is generally efficient, with a few  
          skippable steps, but overall smooth.  
  	3:  
    	label: "Pass"  
        criteria: \>  
          Completes the task, but the path is not direct; some detours or repeated  
          operations; efficiency has room for improvement.  
  	2:  
    	label: "Insufficient"  
        criteria: \>  
      	Low efficiency; many redundant steps, repeated attempts, or time wasted in  
          irrelevant directions.  
  	1:  
    	label: "Very poor"  
        criteria: \>  
          Extremely inefficient; many useless operations; spends a disproportionate  
          number of steps on simple tasks, or gets stuck in dead loops.  
	checklist:  
  	\- "Lean steps: is the task completed in a reasonable number of steps?"  
  	\- "No redundancy: are repeated file reads, searches, edits, etc. avoided?"  
  	\- "Direct to goal: does it advance along a sensible path rather than heavy trial-and-error?"  
  	\- "Parallelism: are parallel operations used to improve efficiency when possible?"  
   
  \# \---------------------------------------------------------------------------  
  \# 6\. Explanation — Q\&A tasks only  
  \# \---------------------------------------------------------------------------  
  explanation:  
	name: "Explanation"  
    description: "Accuracy, clarity, and completeness of the answer/explanation"  
    applicable\_to: \[code\_qa\]  
	scale:  
  	5:  
    	label: "Excellent"  
        criteria: \>  
      	The answer is accurate, comprehensive, and well structured. Cites key code  
      	as evidence; the explanation is deep yet easy to understand, helping the  
      	asker build a correct mental model.  
  	4:  
    	label: "Good"  
        criteria: \>  
      	The answer is mostly accurate and complete, with a clear explanation  
          citing relevant code, but slightly lacking in depth or comprehensiveness.  
  	3:  
    	label: "Pass"  
        criteria: \>  
      	The answer is in the right direction but not complete or deep enough; the  
          explanation is somewhat vague; code citations are insufficient.  
  	2:  
    	label: "Insufficient"  
        criteria: \>  
      	The answer contains clear errors or omissions; the explanation is vague or  
          misleading; lacks supporting code evidence.  
  	1:  
    	label: "Very poor"  
        criteria: \>  
      	The answer is completely wrong or irrelevant to the question; no effective  
          explanation; may mislead the asker.  
   
\# \=============================================================================  
\# Task-type weight configuration  
\# \=============================================================================  
task\_type\_weights:  
   
  code\_generation:  
	name: "Code Generation"  
    description: "The agent generates code from scratch based on a requirements description"  
	weights:  
      correctness: 0.35  
      code\_quality: 0.25  
      reasoning: 0.15  
      tool\_usage: 0.10  
      efficiency: 0.15  
   
  bug\_fix:  
	name: "Bug Fix"  
    description: "Given defective code, the agent locates and fixes the bug"  
	weights:  
      correctness: 0.35  
      code\_quality: 0.25  
      reasoning: 0.15  
      tool\_usage: 0.10  
      efficiency: 0.15  
   
  code\_qa:  
	name: "Code Q\&A"  
    description: "The agent answers questions about the codebase (architecture, logic, APIs, etc.)"  
	weights:  
      correctness: 0.35  
      code\_quality: 0.25  
      reasoning: 0.15  
      tool\_usage: 0.10  
      efficiency: 0.15  
   
  refactor:  
	name: "Refactor / Optimization"  
    description: "The agent improves the structure, performance, or readability of existing code"  
	weights:  
      correctness: 0.35  
      code\_quality: 0.25  
      reasoning: 0.15  
      tool\_usage: 0.10  
      efficiency: 0.15

 

•   **Per-task spec**

 

\# \=============================================================================  
\# Per-task rubric template — fill in per task in the Harbor task definition  
\# \=============================================================================  
\# Below is the rubric definition template for a single task.  
\# Copy this template into each task's definition and fill in the  
\# task-specific scoring points.  
\#  
\# Usage notes:  
\# \- The task\_specific\_criteria field supplements the scoring criteria  
\#   specific to this task  
\# \- There is no need to redefine the general rubric; just specify task\_type  
\#   to inherit the general criteria  
\# \- override\_weights is optional, used to override the dimension weights  
\#   for this task  
\# \=============================================================================  
   
task\_rubric\_template:  
  \# \--- Template below; fill in per task \---  
  task\_id: "\<TASK\_ID\>"  
  task\_type: "\<code\_generation|bug\_fix|code\_qa|refactor\>"  
  task\_specific\_criteria:  
    correctness:  
  	\- "\<task-specific correctness scoring point 1\>"  
  	\- "\<task-specific correctness scoring point 2\>"  
    code\_quality:  
  	\- "\<task-specific code quality scoring point\>"  
	reasoning:  
  	\- "\<task-specific reasoning scoring point\>"  
	tool\_usage:  
  	\- "\<task-specific tool usage scoring point\>"  
	efficiency:  
  	\- "\<task-specific efficiency scoring point\>"  
    explanation:  \# only needed for code\_qa tasks  
  	\- "\<task-specific explanation quality scoring point\>"  
  \# Optional: override the dimension weights for this task  
  \# override\_weights:  
  \#   correctness: 0.50  
  \#   code\_quality: 0.20  
  \#   reasoning: 0.10  
  \#   tool\_usage: 0.10  
  \#   efficiency: 0.10  
   
\# \=============================================================================  
\# Example: rubric definition for a concrete task  
\# \=============================================================================  
example\_task\_rubric:  
  task\_id: "gen-001"  
  task\_type: "code\_generation"  
  task\_specific\_criteria:  
    correctness:  
  	\- "The function must handle edge cases such as an empty list, a  
         single-element list, fully overlapping intervals, and adjacent  
         intervals"  
  	\- "The return value must be sorted in ascending order by interval start"  
  	\- "Time complexity should be O(n log n)"  
    code\_quality:  
  	\- "The function signature should exactly match the requirement"  
  	\- "Python type annotations should be used"  
	reasoning:  
  	\- "Should first analyze the role of sorting in the merge"  
  	\- "Should consider whether an existing library function is available"  
	tool\_usage:  
  	\- "Should search the project for existing similar utility functions"  
	efficiency:  
  	\- "No need to search unrelated files"

## **Harbor Format Example**

[Please check the attachment 《harbor\_case.zip》 in DingTalk Docs.](https://alidocs.dingtalk.com/i/nodes/Gl6Pm2Db8DMGQKRat9xl5pbOWxLq0Ee4?cid=2297571182:4191019637&corpId=dingd8e1123006514592&iframeQuery=anchorId%3DX02mq5bowiy5aiq69sm8o5&utm_medium=im_card&utm_scene=person_space&utm_source=im)

