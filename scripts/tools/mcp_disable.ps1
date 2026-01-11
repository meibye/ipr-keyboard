param([string]$RepoRoot = (Get-Location).Path)
$mcp = Join-Path $RepoRoot ".vscode\mcp.json"
$off = Join-Path $RepoRoot ".vscode\mcp.json.disabled"
if (Test-Path $mcp) {
  Rename-Item $mcp $off -Force
  Write-Host "MCP disabled (renamed to mcp.json.disabled)"
} else {
  Write-Host "No .vscode\mcp.json found (already disabled?)"
}
