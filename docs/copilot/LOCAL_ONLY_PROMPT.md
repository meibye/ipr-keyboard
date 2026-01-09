## Local-only Copilot Mode

Constraints:
- Do not use MCP
- Do not execute commands
- Do not propose SSH or remote actions
- Base all reasoning on repository files and chat context only

 
**Usage Instruction Update:**
This prompt should always be used in local-only Copilot mode; the mode does not change based on the prompt. Actions involving the Raspberry Pi (RPI) through the MCP are only executed when it is explicitly stated in the prompt that actions should be conducted on the RPI. Otherwise, all actions are performed locally and not on the RPI.
