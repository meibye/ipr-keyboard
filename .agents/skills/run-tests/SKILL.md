---
name: run-tests
description: Run the full test suite locally (or in the dev container) with coverage and report gaps.
---

# When to use
- Before committing to verify nothing broke
- After fixing a bug to confirm the regression test passes
- When coverage on a specific module needs to be assessed

# Inputs
- Optional: module or test path to scope the run (e.g. `tests/web/`, `tests/web/test_auth.py`)
- Optional: coverage flag (default: enabled)

# Procedure

1. Run ruff lint first; surface any errors before wasting time on a broken run.
   ```
   ruff check src/ tests/
   ```

2. Run the full test suite with coverage:
   ```
   pytest tests/ -v --tb=short --cov=src/ipr_keyboard --cov-report=term-missing
   ```
   If a path was specified, scope pytest to that path.

3. Identify failing tests. For each failure:
   - Read the test to understand what it asserts
   - Read the source module it exercises
   - Determine root cause before touching any code

4. Report:
   - Total pass / fail / skip counts
   - Coverage percentage per module
   - Any modules below 70% (flag as gaps)
   - Recommended next tests to add

# Quality bar
- All existing tests must continue to pass
- Coverage must not decrease from the baseline
- Skipped tests must be explained (hardware-only, env-gated, etc.)

# Output format
- Pass/fail/skip summary
- Coverage table (module → %)
- List of coverage gaps with suggested test additions

# Related skills
- add-tests
- root-cause-analysis
- implement-feature
