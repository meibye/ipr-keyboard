# Local-Only Analysis Prompt

Use this when remote execution is unavailable or intentionally disallowed.

## Instruction

Analyze only repository files and local outputs. Do not assume live Raspberry Pi state.

## Required Output Shape

1. What is known from repository state
2. What is unknown without runtime access
3. Exact next remote commands that should be run when access is available
4. Risk/impact assessment for each recommendation

## Architecture Rule

Always align findings with `ARCHITECTURE.md` and explicitly flag any legacy/deprecated pattern touched by the issue.
