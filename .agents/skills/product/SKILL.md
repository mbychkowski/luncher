---
name: product
description: >-
  Interactively gather product requirements from the user, refine feature specifications
  using the product_manager agent persona, create a new git branch, and save spec files with an auto-incremented index to /sdlc/01_specs/.
---

# Product Skill

The `product` skill initiates the SDLC process by running the `product_manager` agent interactively to build a feature spec with the user and start a new git branch.

## Execution Workflow

1. **Calculate Next Spec Index**:
   - Inspect `/sdlc/01_specs/` to find all existing spec files matching `NNNN_*.md`.
   - If no spec files exist, set `INDEX = "0001"`.
   - Otherwise, find the highest existing 4-digit prefix `NNNN`, increment it by 1, and zero-pad to 4 digits (e.g., `0002`).

2. **Interactive Requirement Gathering**:
   - Adopt the `product_manager` persona defined in [`.agents/agents/product_manager/prompt.md`](../../agents/product_manager/prompt.md).
   - Interview the user interactively to establish:
     - Feature goal and target problem
     - Core user stories
     - Acceptance criteria and success metrics
     - Non-functional requirements and out-of-scope boundaries

3. **Draft Specification**:
   - Format the specification using [`.agents/agents/product_manager/templates/spec_template.md`](../../agents/product_manager/templates/spec_template.md).

4. **Create Branch & Persist Spec**:
   - Automatically derive a short kebab-case name for the feature based on the specification goals (e.g. `add-dark-mode`). Do not prompt the user for the branch name.
   - Create and checkout a new git branch for the feature (e.g. `git checkout -b feature/NNNN_short-name` or `git checkout -b NNNN_short-name`).
   - Save the finalized spec document to `/sdlc/01_specs/NNNN_short-name.md` (e.g. `/sdlc/01_specs/0001_add-dark-mode.md`).
   - Confirm to the user that the branch and spec have been created and advise them that they can run the `implement` workflow next.
