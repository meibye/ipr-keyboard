---
name: review-pr
description: Perform a code review focused on correctness, maintainability, risk, tests, and documentation completeness.
---

# When to use
- Pull requests
- Large diffs
- Risky changes
- Pre-merge review

# Inputs
- diff
- changed files
- test results if available

# Procedure
1. Review for correctness first.
2. Check architecture and maintainability.
3. Check tests and failure handling.
4. Check docs and config drift.
5. Identify risk level and concrete follow-ups.

# Quality bar
- Prioritize real issues over stylistic noise
- Separate blockers from suggestions
- Cite specific files and behaviors

# Output format
- blockers
- important suggestions
- minor suggestions
- risk summary

# Related skills
- security-review
- update-docs-from-code
- add-tests
