@echo off
REM =============================================================================
REM  Funnel Via Web App - 開發模式（維護者專用，需 Node.js 18+）
REM  一般使用者請改用 start.bat。
REM  此工具由虎門科技資深技術工程師 Jeff Hong 洪敬傑提供。
REM =============================================================================
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" %*

echo.
pause
