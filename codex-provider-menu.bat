@echo off
setlocal
cd /d "%~dp0"

:menu
echo.
echo Codex Provider Switcher
echo 1. Switch provider
echo 2. Show status
echo 3. Test provider connectivity
echo 4. Manage profiles
echo 5. Repair Desktop history list
echo 0. Exit
echo.
set /p choice=Choose:

if "%choice%"=="1" python "%~dp0codex_provider_switcher.py"
if "%choice%"=="2" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0switch-codex-provider.ps1" status
if "%choice%"=="3" python "%~dp0codex_provider_switcher.py" profile list
if "%choice%"=="4" python "%~dp0codex_provider_switcher.py" profile list
if "%choice%"=="5" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0switch-codex-provider.ps1" repair-history
if "%choice%"=="0" exit /b 0
goto menu
