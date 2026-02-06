
## Copilot Agent – Use MCP Server for RPI Commands

Instructions:
- If a question or analysis requires determining status or taking further actions on the Raspberry Pi (RPI), use the MCP server (as defined in `.vscode/mcp.json`) to execute commands remotely on the RPI.
- Remote command execution, diagnostics, and status checks on the RPI are permitted whenever required for accurate analysis or next steps.
- Local-only reasoning is allowed when sufficient, but prefer remote execution if the answer depends on RPI state or files.

**Usage Instruction Update:**
This prompt should be used to enable Copilot agent actions via the MCP server for any RPI-related status, diagnostics, or command execution required by the question or analysis. If the MCP server is unavailable or remote actions are explicitly forbidden, revert to local-only reasoning and summarize what would be done.
