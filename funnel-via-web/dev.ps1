<#
=============================================================================
 Funnel Via Web App － 開發模式啟動腳本（維護者專用）

 後端 uvicorn（127.0.0.1:8010）＋ 前端 Vite dev server（127.0.0.1:5180，
 具熱更新）。此模式需要 Node.js 18 以上，一般使用者請改用 start.bat。

=============================================================================
#>

[CmdletBinding()]
param(
    [int]$BackendPort  = 8010,
    [int]$FrontendPort = 5180
)

$ErrorActionPreference = "Stop"

$utf8 = New-Object System.Text.UTF8Encoding($false)
try {
    [Console]::InputEncoding  = $utf8
    [Console]::OutputEncoding = $utf8
} catch { }
$OutputEncoding = $utf8
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$root     = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend  = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$venv     = Join-Path $backend ".venv"
$py       = Join-Path $venv "Scripts\python.exe"

Write-Host "==== Funnel Via Web App（開發模式）====" -ForegroundColor Cyan

if (-not (Test-Path $py)) {
    Write-Host "尚未建立虛擬環境，請先執行一次 start.bat -CheckOnly。" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "[1/3] 安裝前端套件（npm ci）…" -ForegroundColor Yellow
    Push-Location $frontend
    try { npm ci } finally { Pop-Location }
} else {
    Write-Host "[1/3] 前端套件已安裝，略過。" -ForegroundColor Green
}

foreach ($pair in @(@($FrontendPort, "前端"), @($BackendPort, "後端"))) {
    $listening = Get-NetTCPConnection -LocalPort $pair[0] -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listening) {
        $ownerPid  = $listening.OwningProcess
        $ownerName = (Get-Process -Id $ownerPid -ErrorAction SilentlyContinue).ProcessName
        Write-Host "【警告】$($pair[1])埠 $($pair[0]) 已被 PID $ownerPid（$ownerName）佔用。" -ForegroundColor Red
        exit 1
    }
}

Write-Host "[2/3] 啟動後端 uvicorn（127.0.0.1:$BackendPort，另開視窗）…" -ForegroundColor Yellow
Start-Process powershell -WorkingDirectory $backend -ArgumentList @(
    "-NoLogo", "-NoProfile", "-NoExit", "-Command",
    "& '$py' -m uvicorn app.main:app --reload --host 127.0.0.1 --port $BackendPort"
)

Write-Host "[3/3] 啟動前端 Vite（http://localhost:$FrontendPort）…" -ForegroundColor Yellow
Push-Location $frontend
try { npm run dev } finally { Pop-Location }
