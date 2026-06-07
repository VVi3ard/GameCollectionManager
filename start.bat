@echo off
setlocal
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0game_list_manager\run.ps1"
set "exitcode=%ERRORLEVEL%"
if not "%exitcode%"=="0" (
    echo.
    echo start failed with exit code %exitcode%.
    pause
)
exit /b %exitcode%
