# Common environment for Copilot diagnostic PowerShell scripts
# Import this file in all scripts in scripts/rpi-debug/tools/

$Global:RepoPath = "D:\Dev\ipr_keyboard"
$Global:RpiHost  = "ipr-dev-pi4"
$Global:RpiUser  = "copilotdiag"
$Global:RpiPort  = 22
$Global:KeyPath  = "$env:USERPROFILE\.ssh\copilotdiag_rpi"
$Global:McpRoot  = "D:\mcp"
$Global:McpHome  = "D:\mcp\ssh-mcp"
$Global:ServiceName = "bt_hid_ble.service"
$Global:Hci = "hci0"
$Global:RepoDirOnPi = "/home/meibye/dev/ipr_keyboard"

# Add more shared variables as needed
