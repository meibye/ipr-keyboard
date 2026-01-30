## Local-only Copilot Mode

Constraints:
- Do not use MCP (as defined in `.vscode/mcp.json`, which launches via `npx` or `node`)
- Do not execute commands
- Do not propose SSH or remote actions
- Do not use or reference any remote diagnostic scripts or profiles
- Base all reasoning on repository files and chat context only

**Usage Instruction Update:**
This prompt should always be used in local-only Copilot mode; the mode does not change based on the prompt. Actions involving the Raspberry Pi (RPI) through the MCP (as configured in `.vscode/mcp.json`) or any remote scripts are only executed when it is explicitly stated in the prompt that actions should be conducted on the RPI. Otherwise, all actions are performed locally and not on the RPI.
