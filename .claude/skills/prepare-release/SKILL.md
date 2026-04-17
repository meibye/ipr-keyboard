---
name: prepare-release
description: Prepare a release by verifying versioning, changelog content, documentation, compatibility notes, and rollout readiness.
---

# When to use
- Before tagging
- Before cutting a release branch
- Before publishing deployable artifacts

# Inputs
- release scope
- version target
- deployment target
- changed areas

# Procedure
1. Confirm versioning impact.
2. Build release notes from merged changes.
3. Verify upgrade and migration notes.
4. Verify docs and runbooks.
5. Confirm tests and quality gates.
6. Flag rollout risks and rollback considerations.

# Quality bar
- No missing migration notes
- No stale version references
- No undocumented operator-impacting change

# Output format
- release readiness summary
- release notes draft
- migration notes
- risks and blockers

# Related skills
- update-docs-from-code
- dependency-upgrade
- security-review
