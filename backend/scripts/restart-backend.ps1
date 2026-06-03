# 重启 AI 法律顾问后端（127.0.0.1:8002）
$ErrorActionPreference = "SilentlyContinue"
$Port = 8002

foreach ($p in $Port, 8000, 8001) {
    Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object {
            $procId = $_.OwningProcess
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" -ErrorAction SilentlyContinue |
                ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        }
}

Start-Sleep -Seconds 2

$BackendDir = Split-Path -Parent $PSScriptRoot
Set-Location $BackendDir

$logDir = Join-Path $BackendDir "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# 单进程启动，不使用 --reload
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "python"
$psi.WorkingDirectory = $BackendDir
$psi.Arguments = "-m uvicorn app.main:app --host 127.0.0.1 --port $Port"
$psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$psi.CreateNoWindow = $true
[System.Diagnostics.Process]::Start($psi) | Out-Null

Start-Sleep -Seconds 4

try {
    $health = Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 10
    Write-Host "Backend restarted on http://127.0.0.1:$Port"
    Write-Host ($health | ConvertTo-Json -Compress)
    exit 0
} catch {
    Write-Host "Backend failed health check: $_"
    exit 1
}
