---
name: implement
description: >-
  Orchestrates end-to-end SDLC implementation for pending specs in /sdlc/01_specs/.
  Executes architect decomposition, parallel engineer and test_writer subagents, and reviewer validation.
---

# Implement Workflow Skill

The `implement` workflow skill automates technical design, parallel coding and test writing, and final code review for specs created in `/sdlc/01_specs/`.

## Execution Protocol

### Step 1: Scan for Unimplemented Specs
1. List all spec files in `/sdlc/01_specs/*.md` (excluding `.gitkeep`).
2. For each spec `sdlc/01_specs/NNNN_short-name.md`, check if a corresponding implementation plan exists at `sdlc/02_implementation_plans/NNNN_short-name.md`.
3. Select the unimplemented spec(s) to process. If all specs are implemented, notify the user.

### Step 2: System Architecture & Decomposition (`architect`)
1. Adopt the `architect` agent persona defined in [`.agents/agents/architect/prompt.md`](../../agents/architect/prompt.md).
2. Inspect the spec and codebase to design a modular architecture.
3. Generate the main implementation plan file at `/sdlc/02_implementation_plans/NNNN_short-name.md`.
4. Create individual parallel task files under `/sdlc/03_tasks/NNNN_short-name/task_XX.md`.

### Step 3: Parallel Coding & Testing (`engineer` + `test_writer`)
1. Identify all tasks in `/sdlc/03_tasks/NNNN_short-name/`.
2. For each task, dispatch a dedicated subagent via `invoke_subagent`:
   - For developer tasks: Invoke an `engineer` subagent using [`.agents/agents/engineer/prompt.md`](../../agents/engineer/prompt.md).
   - For test tasks: Invoke a `test_writer` subagent using [`.agents/agents/test_writer/prompt.md`](../../agents/test_writer/prompt.md).
3. Run all independent developer and test writer subagents concurrently in parallel.
4. Monitor subagent outputs until all subtasks complete.

### Step 4: Verification & Code Review (`reviewer`)
1. Adopt the `reviewer` agent persona defined in [`.agents/agents/reviewer/prompt.md`](../../agents/reviewer/prompt.md).
2. Execute project test suites and newly added tests in `/sdlc/04_tests/NNNN_short-name/` or the root test suite.
3. Inspect `git status` and `git diff` for quality, security, and spec compliance.
4. Write the review report to `/sdlc/05_reviews/NNNN_short-name.md`.
5. Report the final review verdict and summary back to the user.
