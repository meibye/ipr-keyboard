# AGENTS.md

Shared agent instructions for Codex in this repository.

## Canonical Source

Use `docs/copilot/*.md` as the canonical source for prompts and skills.

## Prompt Catalog

- `docs/copilot/ARCH_ALIGNMENT_PROMPT.md`
- `docs/copilot/DIAG_AGENT_PROMPT.md`
- `docs/copilot/LOCAL_ONLY_PROMPT.md`
- `docs/copilot/BT_PAIRING_PLAYBOOK.md`

Mirror copies for GitHub Copilot prompts:

- `.github/prompts/copilot/ARCH_ALIGNMENT_PROMPT.md`
- `.github/prompts/copilot/DIAG_AGENT_PROMPT.md`
- `.github/prompts/copilot/LOCAL_ONLY_PROMPT.md`
- `.github/prompts/copilot/BT_PAIRING_PLAYBOOK.md`

## Skills Catalog

Source file:

- `docs/copilot/PYTHON_AGENT_SKILLS.md`

Current installed skills list:

1. `doc`
2. `jupyter-notebook`
3. `playwright`
4. `gh-fix-ci`
5. `gh-address-comments`
6. `security-best-practices`
7. `openai-docs`

## Alignment Rule

When cleanup or refactor questions appear, compare findings against `ARCHITECTURE.md` and flag legacy/deprecated implementations as architectural dead code candidates.
