@echo off
REM =============================================================================
REM  Funnel Via Web App - Windows 一鍵啟動（production 模式）
REM  此工具由虎門科技資深技術工程師 Jeff Hong 洪敬傑提供。
REM
REM  用法：
REM    start.bat                    以預設埠 8010 啟動
REM    start.bat -Port 8020         指定其他連接埠
REM    start.bat -CheckOnly         只檢查環境，不啟動服務
REM =============================================================================
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*

echo.
pause
