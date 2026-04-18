---
name: add-tests
description: Add or improve tests for changed or weakly covered behavior, including regression coverage.
---

# When to use
- After feature work
- For bug fixes
- When coverage is weak around risky logic

# Inputs
- changed behavior
- bug report or expected behavior
- existing test patterns

# Procedure
1. Identify observable behavior to verify.
2. Prefer the lowest-cost test level that gives confidence.
3. Add regression tests for bugs.
4. Add edge-case or failure-path coverage when practical.
5. Keep tests readable and deterministic.

# Quality bar
- Tests should fail for the old bug or missing behavior
- Avoid over-mocking
- Avoid brittle timing-dependent assertions

# Output format
- test scope
- new or updated tests
- known gaps

# Related skills
- implement-feature
- refactor-safely
- root-cause-analysis
