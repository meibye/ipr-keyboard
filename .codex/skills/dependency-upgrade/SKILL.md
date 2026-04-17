---
name: dependency-upgrade
description: Upgrade dependencies with explicit compatibility, security, and rollout analysis.
---

# When to use
- Library upgrades
- Runtime upgrades
- Framework upgrades
- SDK upgrades
- Base image or toolchain upgrades

# Inputs
- dependency list
- target versions
- changelog or release-note references
- impacted areas

# Procedure
1. Inventory current and target versions.
2. Identify breaking changes and deprecated APIs.
3. Update code and configuration as needed.
4. Run targeted validation.
5. Update docs, build scripts, and release notes if needed.

# Quality bar
- No blind version bumps
- Note behavior and config changes explicitly
- Separate upgrade mechanics from unrelated cleanup

# Output format
- upgraded dependencies
- compatibility changes
- tests run
- migration notes

# Related skills
- prepare-release
- refactor-safely
- security-review
