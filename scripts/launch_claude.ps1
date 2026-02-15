$free = (nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
if ([int]$free -lt 19000) {
    Write-Host '⚠️ ERROR: Insufficient VRAM!' -ForegroundColor Red
    Write-Host "Only $free MB free. Close other apps using the 3090." -ForegroundColor Yellow
    exit 1
} else {
    Write-Host "✅ 3090 Ready ($free MB free). Launching Claude..." -ForegroundColor Green
    claude --model claude-local
}
