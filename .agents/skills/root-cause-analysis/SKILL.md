---
name: root-cause-analysis
description: Investigate a defect or incident and produce a clear cause, evidence trail, mitigation, and prevention plan.
---

# When to use
- Bugs
- Regressions
- Incidents
- Flaky tests
- Performance failures
- Operational anomalies

# Inputs
- symptoms
- logs or traces
- failing tests
- recent changes

# Procedure
1. Define the observed failure precisely.
2. Gather evidence from code, logs, configs, and history.
3. Reproduce when possible.
4. Narrow to the minimal causal chain.
5. Propose fix, mitigation, and prevention.
6. Recommend tests or instrumentation to prevent recurrence.

# Quality bar
- Distinguish evidence from hypothesis
- Avoid blame language
- Prefer causal chains over vague summaries

# Output format
- symptom
- evidence
- root cause
- fix
- prevention

# Related skills
- add-tests
- review-pr
- security-review
