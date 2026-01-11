param([string]$RepoRoot = (Get-Location).Path)
$mcp = Join-Path $RepoRoot ".vscode\mcp.json"
$off = Join-Path $RepoRoot ".vscode\mcp.json.disabled"
if (Test-Path $off) {
  Rename-Item $off $mcp -Force
  Write-Host "MCP enabled (restored mcp.json)"
} else {
  Write-Host "No .vscode\mcp.json.disabled found (already enabled?)"
}
