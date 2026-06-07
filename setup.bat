@echo off
setlocal
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0game_list_manager\setup.ps1"
set "exitcode=%ERRORLEVEL%"
if not "%exitcode%"=="0" (
    echo.
    echo setup failed with exit code %exitcode%.
    pause
)
exit /b %exitcode%
