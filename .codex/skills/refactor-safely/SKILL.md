---
name: refactor-safely
description: Improve structure without changing intended behavior, while preserving tests and contracts.
---

# When to use
- Cleanup
- Decomposition
- Naming improvements
- Dead-code removal
- Non-behavioral design improvements

# Inputs
- target module
- refactor objective
- protected behavior or contracts

# Procedure
1. Confirm intended behavior and contracts.
2. Add tests if needed before refactoring.
3. Refactor in small steps.
4. Re-run targeted validation after each logical step.
5. Keep behavior unchanged unless explicitly requested.

# Quality bar
- No hidden behavior changes
- Preserve public contracts
- Avoid mixing refactor and feature work unless requested

# Output format
- structural changes
- preserved contracts
- tests run
- residual debt

# Related skills
- add-tests
- review-pr
- dependency-upgrade
