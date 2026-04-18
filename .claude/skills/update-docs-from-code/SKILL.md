---
name: update-docs-from-code
description: Update developer, operational, API, and user-facing documentation after code, config, CLI, workflow, or architecture changes.
---

# When to use
- Public interface changes
- Command or flag changes
- Configuration changes
- Architecture changes
- Deployment or operational workflow changes
- User-visible behavior changes

# Inputs
- changed files
- diff summary
- impacted modules or services
- impacted commands, APIs, configs, or workflows

# Procedure
1. Inspect the diff and list behavior-level changes.
2. Map changes to affected docs.
3. Update only the affected sections.
4. Ensure claims match actual code paths, commands, flags, defaults, and behavior.
5. Update examples and usage notes as needed.
6. Report which docs were updated and why.

# Quality bar
- No invented behavior
- No stale examples
- No full-document rewrites unless structure is already broken
- Prefer concise deltas tied to changed code

# Output format
- impacted docs
- edits made
- unresolved doc gaps
- validation performed

# Related skills
- implement-feature
- review-pr
- prepare-release
- design-rfc
