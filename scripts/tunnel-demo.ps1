# 临时演示：启动前后端 + 内网穿透（localtunnel）
# 用法：powershell -ExecutionPolicy Bypass -File scripts/tunnel-demo.ps1
# 将输出的公网 URL 发给朋友即可访问（演示期间请保持本窗口与电脑不休眠）

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Port = 5173
$BackendPort = 8003

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " AI 法律顾问助手 - 临时演示（内网穿透）" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Node / Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[错误] 未找到 python，请先安装 Python 3.10+" -ForegroundColor Red
    exit 1
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "[错误] 未找到 npm，请先安装 Node.js 18+" -ForegroundColor Red
    exit 1
}

# 释放端口（若被占用）
foreach ($p in @($BackendPort, $Port)) {
    Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}
Start-Sleep -Seconds 1

Write-Host "[1/3] 启动后端 http://127.0.0.1:$BackendPort ..." -ForegroundColor Yellow
$backendJob = Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort" `
    -WorkingDirectory $Backend `
    -PassThru -WindowStyle Hidden

Start-Sleep -Seconds 3
try {
    $health = Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/health" -UseBasicParsing -TimeoutSec 8
    if ($health.StatusCode -ne 200) { throw "health check failed" }
    Write-Host "      后端已就绪" -ForegroundColor Green
} catch {
    Write-Host "[错误] 后端启动失败，请检查 backend/.env 与依赖" -ForegroundColor Red
    Stop-Process -Id $backendJob.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

Write-Host "[2/3] 启动前端 http://0.0.0.0:$Port ..." -ForegroundColor Yellow
$frontendJob = Start-Process -FilePath "npm" `
    -ArgumentList "run", "dev", "--", "--host", "0.0.0.0", "--port", "$Port" `
    -WorkingDirectory $Frontend `
    -PassThru -WindowStyle Hidden

Start-Sleep -Seconds 5
try {
    $fe = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 10
    if ($fe.StatusCode -ne 200) { throw "frontend failed" }
    Write-Host "      前端已就绪" -ForegroundColor Green
} catch {
    Write-Host "[错误] 前端启动失败" -ForegroundColor Red
    Stop-Process -Id $backendJob.Id, $frontendJob.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

Write-Host "[3/3] 创建公网隧道（localtunnel）..." -ForegroundColor Yellow
Write-Host ""
Write-Host "----------------------------------------" -ForegroundColor Cyan
Write-Host " 将下面出现的 https://xxx.loca.lt 链接发给朋友" -ForegroundColor White
Write-Host " 首次打开 loca.lt 可能需点击 Continue 继续" -ForegroundColor Gray
Write-Host " 按 Ctrl+C 结束演示并关闭服务" -ForegroundColor Gray
Write-Host "----------------------------------------" -ForegroundColor Cyan
Write-Host ""

try {
    npx --yes localtunnel --port $Port
} finally {
    Write-Host ""
    Write-Host "正在关闭服务..." -ForegroundColor Yellow
    Stop-Process -Id $backendJob.Id, $frontendJob.Id -Force -ErrorAction SilentlyContinue
    Get-Process -Name "node" -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle -eq "" } |
        ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
    Write-Host "已结束。" -ForegroundColor Green
}
