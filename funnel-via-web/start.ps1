<#
=============================================================================
 Funnel Via Web App － Windows 一鍵啟動腳本（production 模式）

 流程：start.bat → start.ps1 → backend\.venv\Scripts\python.exe → uvicorn
 使用者不需要 Node.js，前端已預先建置於 frontend\dist，由 FastAPI 以
 單一 localhost 埠一併服務。

=============================================================================
#>

[CmdletBinding()]
param(
    # 只做環境檢查與相依套件安裝，不啟動服務、不佔用連接埠（供封裝測試使用）
    [switch]$CheckOnly,
    # 服務埠，預設 8010
    [int]$Port = 8010,
    # 啟動後不要自動開啟瀏覽器
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

# --- 主控台編碼：一律 UTF-8，避免繁體中文 Windows 的 CP950 亂碼 -----------
$utf8 = New-Object System.Text.UTF8Encoding($false)
try {
    [Console]::InputEncoding  = $utf8
    [Console]::OutputEncoding = $utf8
} catch { }
$OutputEncoding = $utf8
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# --- 路徑 -----------------------------------------------------------------
$root      = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend   = Join-Path $root "backend"
$frontend  = Join-Path $root "frontend"
$venv      = Join-Path $backend ".venv"
$py        = Join-Path $venv "Scripts\python.exe"
$lockFile  = Join-Path $backend "requirements.lock.txt"
$distIndex = Join-Path $frontend "dist\index.html"
$stamp     = Join-Path $venv ".deps-installed"

# 實測相容的 64 位元 Python 版本（由左至右優先）
$SupportedPythonVersions = @("3.12", "3.11", "3.10")
$WinGetPackageId         = "Python.Python.3.12"
$PythonDownloadUrl       = "https://www.python.org/downloads/windows/"

function Write-Step([string]$text) {
    Write-Host $text -ForegroundColor Yellow
}
function Write-Ok([string]$text) {
    Write-Host $text -ForegroundColor Green
}
function Write-Fail([string]$text) {
    Write-Host $text -ForegroundColor Red
}

Write-Host "==== Funnel Via Web App 啟動中 ====" -ForegroundColor Cyan
Write-Host ""

# =============================================================================
# 1. 檢查發布內容是否完整
# =============================================================================
Write-Step "[1/5] 檢查發布內容…"

if (-not (Test-Path $lockFile)) {
    Write-Fail "找不到 $lockFile"
    Write-Fail "壓縮檔可能不完整，請重新下載後再解壓縮。"
    exit 1
}
Write-Ok "      相依套件清單：backend\requirements.lock.txt"

if (-not (Test-Path $distIndex)) {
    Write-Fail "找不到 production 前端 frontend\dist\index.html"
    Write-Fail "請重新下載完整壓縮檔；若您是開發者，請改執行 dev.bat 或先在 frontend 執行 npm ci 與 npm run build。"
    exit 1
}
Write-Ok "      production 前端：frontend\dist\index.html"

# =============================================================================
# 2. 尋找相容的 64 位元 Python
# =============================================================================

# 探測單一 Python 候選；回傳 "major.minor|bits"，失敗回傳 $null。
# 注意：對原生指令做 stderr 重導向時，Windows PowerShell 5.1 會在
# $ErrorActionPreference = "Stop" 之下先把 stderr 包成終止例外，2>$null
# 攔不住，因此整段必須放在 try/catch 內。
function Get-PythonSignature {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [string[]]$Prefix = @()
    )
    $probe = "import sys,struct;print(str(sys.version_info[0])+'.'+str(sys.version_info[1])+'|'+str(struct.calcsize('P')*8))"
    try {
        $arguments = @()
        if ($Prefix.Count -gt 0) { $arguments += $Prefix }
        $arguments += @("-c", $probe)
        $output = & $Exe @arguments 2>$null
        if ($LASTEXITCODE -ne 0) { return $null }
        $line = ($output | Where-Object { $_ -match "^\d+\.\d+\|\d+$" } | Select-Object -First 1)
        if (-not $line) { return $null }
        return [string]$line
    } catch {
        return $null
    }
}

function Find-CompatiblePython {
    $candidates = New-Object System.Collections.Generic.List[object]

    # (a) Python Launcher 版本選擇器
    foreach ($ver in $SupportedPythonVersions) {
        $candidates.Add([pscustomobject]@{ Exe = "py"; Prefix = @("-$ver-64") })
    }
    # (b) PATH 上的具名命令
    foreach ($ver in $SupportedPythonVersions) {
        $candidates.Add([pscustomobject]@{ Exe = "python$ver"; Prefix = @() })
    }
    $candidates.Add([pscustomobject]@{ Exe = "python"; Prefix = @() })
    $candidates.Add([pscustomobject]@{ Exe = "python3"; Prefix = @() })

    # (c) 常見的使用者安裝路徑
    foreach ($ver in $SupportedPythonVersions) {
        $tag = $ver.Replace(".", "")
        foreach ($base in @(
            (Join-Path $env:LOCALAPPDATA "Programs\Python\Python$tag\python.exe"),
            (Join-Path $env:ProgramFiles "Python$tag\python.exe"),
            "C:\Python$tag\python.exe"
        )) {
            if ($base -and (Test-Path $base)) {
                $candidates.Add([pscustomobject]@{ Exe = $base; Prefix = @() })
            }
        }
    }

    foreach ($candidate in $candidates) {
        $signature = Get-PythonSignature -Exe $candidate.Exe -Prefix $candidate.Prefix
        if (-not $signature) { continue }
        $parts   = $signature.Split("|")
        $version = $parts[0]
        $bits    = $parts[1]
        if ($bits -ne "64") { continue }
        if ($SupportedPythonVersions -notcontains $version) { continue }
        return [pscustomobject]@{
            Exe     = $candidate.Exe
            Prefix  = $candidate.Prefix
            Version = $version
        }
    }
    return $null
}

function Install-CompatiblePython {
    Write-Step "      未找到相容版本，嘗試以 WinGet 安裝 $WinGetPackageId（使用者範圍，不影響既有 Python）…"
    $winget = (Get-Command winget -ErrorAction SilentlyContinue)
    if (-not $winget) {
        Write-Fail "      本機沒有 WinGet，無法自動安裝。"
        return $null
    }
    try {
        & winget install `
            --id $WinGetPackageId `
            --exact `
            --source winget `
            --scope user `
            --architecture x64 `
            --silent `
            --accept-package-agreements `
            --accept-source-agreements `
            --disable-interactivity
    } catch {
        Write-Fail "      WinGet 安裝失敗：$($_.Exception.Message)"
        return $null
    }
    # 安裝後重新偵測，不假設目前程序的 PATH 已更新
    return (Find-CompatiblePython)
}

if (-not (Test-Path $py)) {
    Write-Step "[2/5] 尋找相容的 64 位元 Python（$($SupportedPythonVersions -join ' / ')）…"
    $python = Find-CompatiblePython
    if (-not $python) {
        $python = Install-CompatiblePython
    }
    if (-not $python) {
        Write-Fail ""
        Write-Fail "找不到相容的 64 位元 Python（需要 $($SupportedPythonVersions -join ' / ')）。"
        Write-Fail "請手動安裝後再執行本工具：$PythonDownloadUrl"
        Write-Fail "安裝時請勾選 64-bit 版本；若公司政策限制安裝軟體，請洽 IT 部門協助。"
        Read-Host "按 Enter 結束"
        exit 1
    }
    $label = if ($python.Prefix.Count -gt 0) { "$($python.Exe) $($python.Prefix -join ' ')" } else { $python.Exe }
    Write-Ok "      使用 Python $($python.Version)（64 位元）：$label"

    Write-Step "      建立虛擬環境 backend\.venv…"
    $venvArguments = @()
    if ($python.Prefix.Count -gt 0) { $venvArguments += $python.Prefix }
    $venvArguments += @("-m", "venv", $venv)
    & $python.Exe @venvArguments
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $py)) {
        Write-Fail "虛擬環境建立失敗。"
        Read-Host "按 Enter 結束"
        exit 1
    }
    Write-Ok "      虛擬環境已建立。"
} else {
    Write-Step "[2/5] 已存在虛擬環境 backend\.venv，略過建立。"
}

# =============================================================================
# 3. 於虛擬環境安裝套件（僅在首次或 lock 檔更新後執行）
# =============================================================================
$needInstall = $true
if (Test-Path $stamp) {
    $stampTime = (Get-Item $stamp).LastWriteTimeUtc
    $lockTime  = (Get-Item $lockFile).LastWriteTimeUtc
    if ($stampTime -ge $lockTime) { $needInstall = $false }
}

if ($needInstall) {
    Write-Step "[3/5] 於 backend\.venv 安裝相依套件（首次啟動需要網路，約數分鐘）…"
    # 以 uv 建立的舊虛擬環境可能沒有 pip，先補上；失敗不視為致命錯誤。
    try {
        & $py -m ensurepip --upgrade | Out-Null
    } catch { }

    $installFailed = $false
    try {
        & $py -m pip install --upgrade pip
        & $py -m pip install -r $lockFile
        if ($LASTEXITCODE -ne 0) { $installFailed = $true }
    } catch {
        Write-Fail "      $($_.Exception.Message)"
        $installFailed = $true
    }
    if ($installFailed) {
        Write-Fail "套件安裝失敗，請確認網路連線或公司 Proxy 設定後重試。"
        Read-Host "按 Enter 結束"
        exit 1
    }
    Set-Content -LiteralPath $stamp -Value "installed" -Encoding ASCII
    Write-Ok "      套件安裝完成。"
} else {
    Write-Step "[3/5] 相依套件已安裝，略過。"
}

# =============================================================================
# 4. 連接埠檢查
# =============================================================================
Write-Step "[4/5] 檢查連接埠 $Port…"
$listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listening) {
    $ownerPid  = $listening.OwningProcess
    $ownerName = (Get-Process -Id $ownerPid -ErrorAction SilentlyContinue).ProcessName
    Write-Fail "【警告】連接埠 $Port 已被 PID $ownerPid（$ownerName）佔用。"
    Write-Fail "        請先關閉該程式，或以 start.bat -Port <其他埠> 指定不同連接埠。"
    Read-Host "按 Enter 結束"
    exit 1
}
Write-Ok "      連接埠 $Port 可用。"

$url = "http://127.0.0.1:$Port"

if ($CheckOnly) {
    Write-Host ""
    Write-Ok "[5/5] 檢查模式（-CheckOnly）：環境完整，未啟動服務。"
    Write-Host "      正式啟動請直接執行 start.bat。" -ForegroundColor DarkGray
    exit 0
}

# =============================================================================
# 5. 服務以子程序啟動；主程序輪詢就緒後才開啟瀏覽器
# =============================================================================
Write-Step "[5/5] 啟動服務 $url（關閉本視窗即停止服務）…"
Write-Host ""

# ---------------------------------------------------------------------------
# 為什麼不用 Start-Job 開瀏覽器（實際事故，勿改回去，詳見 ansys-gs-hub/start.ps1）
#
# 舊版用 Start-Job 開一個背景工作輪詢連接埠、就緒後呼叫 Start-Process 開瀏覽器。
# Start-Job 會另外啟動一個 PowerShell 子程序並在其中執行序列化的 script block，
# 這正是防毒軟體的行為偵測特徵。實測在裝有 WithSecure Client Security 的機器上，
# 該子程序被判定為 Trojan:AMSI/SuspiciousExecute.A 直接攔截，瀏覽器完全沒開，
# 使用者連一個錯誤訊息都看不到。
#
# 現在改成：uvicorn 以「子程序」執行（啟動的是 python.exe，不是 PowerShell），
# 主程序自己輪詢 /api/health、就緒後在完整互動 session 裡直接開瀏覽器。
# 全程不產生任何 PowerShell 子程序，開啟失敗時一律把網址明顯印出來。
# ---------------------------------------------------------------------------

Push-Location $backend
$server = $null
try {
    $server = Start-Process -FilePath $py `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port") `
        -NoNewWindow -PassThru

    $ready = $false
    for ($i = 0; $i -lt 120; $i++) {
        if ($server.HasExited) { break }
        Start-Sleep -Milliseconds 500
        try {
            $health = Invoke-WebRequest -Uri "$url/api/health" -UseBasicParsing -TimeoutSec 2
            if ($health.StatusCode -eq 200) { $ready = $true; break }
        } catch { }
    }

    if ($ready -and -not $NoBrowser) {
        $opened = $false
        try {
            Start-Process $url
            $opened = $true
        } catch { }
        Write-Host ""
        if ($opened) {
            Write-Ok "服務已就緒，已開啟瀏覽器：$url"
        } else {
            Write-Fail "服務已就緒，但無法自動開啟瀏覽器。"
            Write-Fail "請自行在瀏覽器輸入下列網址："
            Write-Host "    $url" -ForegroundColor Cyan
        }
    } elseif ($ready) {
        Write-Host ""
        Write-Ok "服務已就緒：$url"
    } elseif (-not $server.HasExited) {
        Write-Host ""
        Write-Fail "服務啟動逾時，仍未回應健康檢查。請自行在瀏覽器輸入下列網址確認："
        Write-Host "    $url" -ForegroundColor Cyan
    }
    Write-Host ""

    if (-not $server.HasExited) {
        Wait-Process -Id $server.Id
    }
} finally {
    Pop-Location

    if ($null -ne $server) {
        try {
            if (-not $server.HasExited) {
                & taskkill /PID $server.Id /T /F | Out-Null
                Start-Sleep -Milliseconds 500
            }
        } catch { }
        try {
            if (-not $server.HasExited) { $server.Kill() }
        } catch { }
    }

    Write-Host ""
    $leftover = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($leftover) {
        Write-Fail "服務已結束，但連接埠 $Port 仍被佔用（PID $($leftover[0].OwningProcess)）。"
        Write-Fail "下次啟動若顯示連接埠被佔用，請先結束該程序。"
    } else {
        Write-Ok "服務已結束，連接埠 $Port 已釋放。"
    }
}
