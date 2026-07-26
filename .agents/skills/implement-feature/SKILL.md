---
name: implement-feature
description: Implement a new feature with minimal, architecture-aligned changes, tests, and required docs updates.
---

# When to use
- New capabilities
- New endpoints or commands
- New configuration options
- Behavior extensions

# Inputs
- feature request
- impacted components
- constraints
- acceptance criteria

# Procedure
1. Read relevant code, tests, and docs first.
2. Identify affected boundaries and invariants.
3. Make the smallest coherent implementation.
4. Add or update tests.
5. Update docs if interfaces, config, or workflows changed.
6. Summarize behavior, validation, and tradeoffs.

# Quality bar
- No speculative extra refactors
- Respect existing architecture
- Validate edge cases and failure handling

# Output format
- implementation summary
- tests added or updated
- docs updated
- follow-ups

# Related skills
- add-tests
- update-docs-from-code
- design-rfc
- security-review
