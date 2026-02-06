---
name: Implementation Planner
description: Generates detailed technical implementation plans from Feature Specs (Spec Kit) or user requirements.
tools:
  - view_file
  - write_to_file
  - task_boundary
---

# Implementation Planner Skill

This skill converts "What needs to be done" (Specs) into "How to do it" (Implementation Plans). 

It is the bridge between **Spec Kit** (Requirements) and **Execution** (Coding).

## Input
1.  **Feature Spec**: A `.specify/templates/spec-template.md` style document (or just requirements).
2.  **Codebase Context**: Understanding of the current architecture.

## Output
An `implementation_plan.md` artifact saved to the workspace `artifacts` (via `write_to_file` with `ArtifactType: implementation_plan`).

## Workflow

### 1. Analysis Phase
- Read the relevant Spec file (`specs/[feature]/spec.md` or similar).
- Explore the codebase to identify affected files and dependencies.
- Identify risks and edge cases not covered in the Spec.

### 2. Planning Phase
Create the `implementation_plan.md` using the standard format.

#### Plan Structure

```markdown
# Implementation Plan: [Feature Name]

## 1. Overview
[Brief summary of technical approach]

## 2. User Review Required
[Breaking changes, critical decisions, or risks]

## 3. Proposed Changes (The "How")
Grouped by component/layer. 

### [Component Name]
#### [MODIFY] [file path]
- Change A
- Change B
#### [NEW] [file path]
- Purpose of file

## 4. Verification Plan (Connection to Eval-Driven Design)
Define the **Evals** you will run.

### Capability Evals
- [ ] Command to verify Feature A
- [ ] Command to verify Feature B

### Regression Evals
- [ ] Existing tests to run
```

### 3. Review Phase
- Present the plan to the user via `notify_user` (or `task_boundary` summary).
- Wait for approval before moving to EXECUTION.

## Interaction with Spec Kit

If a Spec exists:
1.  **Verify**: Check that every "Functional Requirement" in the Spec has a corresponding technical task in the Plan.
2.  **Trace**: Ensure "Success Criteria" in the Spec are mapped to "Verification Plan" steps in the Plan.

## Best Practices
1.  **Granularity**: Steps should be small enough to be executed in 1-2 tool calls.
2.  **Files**: Always use absolute paths.
3.  **Dependencies**: List changes in dependency order (e.g., DB Schema -> API Model -> API Endpoint -> UI).
