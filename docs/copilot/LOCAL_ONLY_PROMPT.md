
## Copilot Agent – Use MCP Server for RPI Commands
## Remote Device Access via SSH MCP Server

For all remote diagnostic actions, use the SSH MCP server as defined in `.vscode/mcp.json`.

**Example:**
- To run a diagnostic script remotely:
	- Use the `ipr-rpi-dev-ssh` profile.
	- Execute via MCP server (see Copilot agent or VS Code integration).

**Typical usage:**
```json
{
	"cmdString": "/usr/local/bin/dbg_stack_status.sh"
}
```
See `.vscode/mcp.json` for server details and allowed commands.

**Do not use direct SSH or SCP.** All remote actions should be performed via the MCP server for consistency and auditability.

---

Instructions:
- If a question or analysis requires determining status or taking further actions on the Raspberry Pi (RPI), use the MCP server (as defined in `.vscode/mcp.json`) to execute commands remotely on the RPI.
- Remote command execution, diagnostics, and status checks on the RPI are permitted whenever required for accurate analysis or next steps.
- Local-only reasoning is allowed when sufficient, but prefer remote execution if the answer depends on RPI state or files.

**Usage Instruction Update:**
This prompt should be used to enable Copilot agent actions via the MCP server for any RPI-related status, diagnostics, or command execution required by the question or analysis. If the MCP server is unavailable or remote actions are explicitly forbidden, revert to local-only reasoning and summarize what would be done.
