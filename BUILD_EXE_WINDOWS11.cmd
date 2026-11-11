@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo.
echo HI JACK LIVE - WINDOWS 11 COMPATIBILITY BUILD v0.3.5
echo Builds isolated Edge --app control and local OBS server.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\BUILD_WINDOWS11.ps1"
if errorlevel 1 goto :failed
echo.
echo SUCCESS. Folder with HiJackLive.exe opened.
exit /b 0
:failed
echo.
echo BUILD FAILED. Read BUILD_WINDOWS11_LOG.txt
pause
exit /b 1
