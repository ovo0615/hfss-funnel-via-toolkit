@echo off
chcp 65001 > nul
REM 此工具由虎門科技資深技術工程師 Jeff Hong 洪敬傑提供。
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
pause
