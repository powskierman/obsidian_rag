---
name: Eval-Driven Design
description: A formal framework for defining success criteria (Evals) before implementation, and verifying them with pass@k metrics.
tools:
  - run_command
  - view_file
  - write_to_file
---

# Eval-Driven Design (EDD) Skill

A formal evaluation framework for Antigravity sessions, implementing eval-driven development (EDD) principles.

## Philosophy

Eval-Driven Development treats evals as the "unit tests of AI development":
- Define expected behavior **BEFORE** implementation (Capability Evals).
- Track regressions with each change (Regression Evals).
- Use `pass@k` metrics for reliability measurement.

## Directory Structure

All evals are stored in `.agent/evals/` in the workspace root.
- `*.md`: Eval definitions (the source of truth).
- `*.log`: Execution logs.

## 1. Defining Evals (The "Contract")

**When**: Before writing any code for a new feature or complex refactor.

**Action**: Create a file `.agent/evals/[feature-name].md` using this template:

```markdown
# EVAL: [feature-name]
Created: [YYYY-MM-DD]

## Capability Evals
*New things the system must do.*

- [ ] **[Cap-1]** [Short Title]
  - **Goal**: [Description of what needs to happen]
  - **Verification**: [Exact command or check to run]
  - **Success Criteria**: [What output indicates success?]

- [ ] **[Cap-2]** [Short Title]
  ...

## Regression Evals
*Existing things that must not break.*

- [ ] **[Reg-1]** [Short Title]
  - **Verification**: `pytest tests/path/to/test.py`
  - **Success Criteria**: Exit code 0

## Success Metrics
- **Capability**: pass@3 > 90% (Success within 3 attempts)
- **Regression**: pass^1 = 100% (Must pass every time)
```

## 2. Running Evals (The "Loop")

**When**: During implementation, after every significant code change.

**Action**: 
1. Run the verification commands specified in the Eval file.
2. Record the results.
3. If a check fails, refine the implementation and retry (counting attempts).

## 3. Reporting Results

**When**: Before marking a task as DONE.

**Action**: Append a report to the Eval file or create a summary artifact.

```text
EVAL REPORT: [feature-name]
========================
Capability:
  [Cap-1]: PASS (Attempt 1)
  [Cap-2]: PASS (Attempt 2)
  Overall: 2/2 Passed

Regression:
  [Reg-1]: PASS
  Overall: 1/1 Passed

Status: READY TO MERGE
```

## Grader Types (How to Verify)

1.  **Code-Based (Preferred)**:
    *   `grep -q "expected string" file.txt`
    *   `python -c "import module; assert module.check()"`
    *   `pytest tests/specific_test.py`

2.  **Model-Based (Subjective)**:
    *   Use `search_web` or `run_command` to get output, then analyze it.
    *   *Example*: "Run the query 'X' and confirm the response mentions 'Y'."

## Best Practices

1.  **Strictness**: If the Eval isn't automated, it probably won't get run. prioritizing shell commands over manual checks.
2.  **Isolation**: Tests should not depend on global state if possible.
3.  **Speed**: Evals should run in seconds, not minutes.
