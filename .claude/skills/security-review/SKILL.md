---
name: security-review
description: Review changes for security risks in authentication, authorization, input handling, secrets, encryption, and exposure boundaries.
---

# When to use
- Auth changes
- Network-facing features
- Infrastructure changes
- Data handling changes
- Secret management changes
- Any high-risk modification

# Inputs
- diff
- threat-sensitive components
- trust boundaries
- deployment context

# Procedure
1. Identify assets, actors, and trust boundaries.
2. Review input validation and output handling.
3. Review authentication and authorization implications.
4. Check secret handling and least privilege.
5. Check logging, data exposure, and unsafe defaults.
6. Recommend mitigations and tests.

# Quality bar
- Focus on concrete attack surfaces
- Prioritize high-severity findings
- Do not confuse style with security

# Output format
- findings by severity
- mitigations
- residual risks
- test recommendations

# Related skills
- review-pr
- dependency-upgrade
- prepare-release
