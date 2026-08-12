# Implement Workflow

**Workflow Name**: `implement`  
**Description**: Runs full SDLC implementation pipeline (Architect -> Engineer & Test Writer -> Reviewer) on unimplemented specs in `/sdlc/01_specs/`.

## Workflow Steps

1. **Find Unimplemented Specs**:
   - Locate files in `/sdlc/01_specs/NNNN_short-name.md` without matching `/sdlc/02_implementation_plans/NNNN_short-name.md`.

2. **Architect Stage**:
   - Run `architect` agent ([`.agents/agents/architect/prompt.md`](../agents/architect/prompt.md)).
   - Writes `/sdlc/02_implementation_plans/NNNN_short-name.md` and task breakdowns in `/sdlc/03_tasks/NNNN_short-name/`.

3. **Parallel Execution Stage**:
   - Dispatch `engineer` and `test_writer` subagents concurrently via `invoke_subagent`.

4. **Reviewer Stage**:
   - Run `reviewer` agent ([`.agents/agents/reviewer/prompt.md`](../agents/reviewer/prompt.md)).
   - Executes tests, inspects diffs, writes `/sdlc/05_reviews/NNNN_short-name.md`, and reports back to user.
