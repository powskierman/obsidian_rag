---
description: Review current changes (git diff) for quality, security, and style issues.
---

# Review Changes Workflow

This workflow acts as an automated "Sr. Code Reviewer". It analyzes the uncommitted changes in your working directory against a set of strict guidelines.

## Steps

1.  **Analyze Diffs**
    - Run `git diff --cached` (for staged) or `git diff` (for unstaged).
    - Identify all modified files.

2.  **Safety Checks (CRITICAL)**
    - [ ] **Secrets**: Are there any hardcoded API keys or passwords?
    - [ ] **Destructive Actions**: Any unchecked `rm -rf` or file deletions?
    - [ ] **Injection**: Any raw SQL queries or unescaped user input?

3.  **Quality Checks (HIGH)**
    - [ ] **Console Logs**: Any `print()` or `console.log()` left behind?
    - [ ] **Types**: Any `Any` (Python) or `any` (TS) usage that clutters strict typing?
    - [ ] **Tests**: Did the tests get updated for the new code?
    - [ ] **Complexity**: Are there functions > 50 lines that could be split?

4.  **Style / Best Practices (MEDIUM)**
    - [ ] **Naming**: Do variables use descriptive names (no `x`, `tmp`, `data`)?
    - [ ] **Comments**: Are complex blocks commented?

## Output
Produce a markdown summary of the review:

```markdown
# Code Review Report

## 🚫 Blockers (Must Fix)
- found_secret_key in `app.py`
- raw_sql_query in `db.py`

## ⚠️ Warnings (Should Fix)
- left_over_print in `utils.py`

## ✅ Good to Go
- `models.py` looks clean.
```

## Auto-Fix
If `// turbo` mode is active, the agent may attempt to fix "Blockers" automatically (e.g., removing print statements).
